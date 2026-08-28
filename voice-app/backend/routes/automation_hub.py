"""Independent Automation Hub API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.automation_hub import assets, config, connections, jobs, roxy, security, sidecar
from ..services.automation_hub.schemas import (
    AutomationAssetResponse,
    AutomationConnectionCreate,
    AutomationConnectionResponse,
    AutomationConnectionUpdate,
    AutomationHubStatusResponse,
    AutomationPublishJobCreate,
    AutomationPublishJobResponse,
    AutomationRenderAssetImportRequest,
    RoxyProfileCloseRequest,
    RoxyProfileOpenRequest,
)

router = APIRouter(prefix="/automation-hub", tags=["automation-hub"])


def _error(status: int, message: str, error_code: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"message": message, "error_code": error_code})


def _require_enabled() -> None:
    try:
        config.require_enabled()
    except config.AutomationHubDisabledError as exc:
        raise _error(503, str(exc), exc.error_code) from exc


def _roxy_client(connection_id: str, db: Session) -> roxy.RoxyLocalApiClient:
    row = connections.get_connection(connection_id, db)
    if row is None or row.platform != "roxy" or row.kind != "roxy":
        raise _error(404, "Không tìm thấy RoxyBrowser connection.", "ROXY_CONNECTION_NOT_FOUND")
    try:
        secret = security.decrypt_secret(row.secret_ciphertext)
        public = dict(row.public_config_json or {})
        return roxy.RoxyLocalApiClient(
            api_key=str(secret.get("api_key") or ""),
            api_host=str(public.get("api_host") or config.get_config().roxy_api_host),
        )
    except (security.SecretStoreError, roxy.RoxyApiError) as exc:
        raise _error(422, str(exc), getattr(exc, "error_code", "ROXY_CONNECTION_INVALID")) from exc


@router.get("/status", response_model=AutomationHubStatusResponse)
async def get_automation_hub_status():
    cfg = config.get_config()
    secret_status = security.secret_store_status()
    sidecar_status = await sidecar.status()
    prerequisites: list[str] = []
    if not cfg.enabled:
        prerequisites.append("Đặt VOICEBOX_FEATURE_AUTOMATION_HUB=true và khởi động lại backend.")
    if not secret_status.get("ready"):
        prerequisites.append("Khắc phục secret store trước khi lưu API key hoặc token.")
    if not cfg.sidecar_entry_path.is_file():
        prerequisites.append("Chạy scripts/setup-roxybrowser-automation.ps1 để build Playwright MCP sidecar.")
    return AutomationHubStatusResponse(
        enabled=cfg.enabled,
        direct_post_enabled=cfg.direct_post_enabled,
        secret_store=secret_status,
        worker=jobs.worker_snapshot(),
        sidecar=sidecar_status,
        prerequisites=prerequisites,
    )


@router.get("/connections", response_model=list[AutomationConnectionResponse])
async def list_automation_connections(db: Session = Depends(get_db)):
    return connections.list_connections(db)


@router.post("/connections", response_model=AutomationConnectionResponse)
async def create_automation_connection(data: AutomationConnectionCreate, db: Session = Depends(get_db)):
    _require_enabled()
    try:
        return connections.create_connection(data, db)
    except (connections.ConnectionError, security.SecretStoreError) as exc:
        raise _error(422, str(exc), getattr(exc, "error_code", "AUTOMATION_CONNECTION_INVALID")) from exc


@router.put("/connections/{connection_id}", response_model=AutomationConnectionResponse)
async def update_automation_connection(
    connection_id: str,
    data: AutomationConnectionUpdate,
    db: Session = Depends(get_db),
):
    _require_enabled()
    try:
        response = connections.update_connection(connection_id, data, db)
    except (connections.ConnectionError, security.SecretStoreError) as exc:
        raise _error(422, str(exc), getattr(exc, "error_code", "AUTOMATION_CONNECTION_INVALID")) from exc
    if response is None:
        raise _error(404, "Không tìm thấy connection.", "AUTOMATION_CONNECTION_NOT_FOUND")
    return response


@router.post("/connections/{connection_id}/check", response_model=AutomationConnectionResponse)
async def check_automation_connection(connection_id: str, db: Session = Depends(get_db)):
    _require_enabled()
    response = await connections.check_connection(connection_id, db)
    if response is None:
        raise _error(404, "Không tìm thấy connection.", "AUTOMATION_CONNECTION_NOT_FOUND")
    return response


@router.delete("/connections/{connection_id}")
async def delete_automation_connection(connection_id: str, db: Session = Depends(get_db)):
    _require_enabled()
    try:
        deleted = connections.delete_connection(connection_id, db)
    except connections.ConnectionError as exc:
        raise _error(409, str(exc), exc.error_code) from exc
    if not deleted:
        raise _error(404, "Không tìm thấy connection.", "AUTOMATION_CONNECTION_NOT_FOUND")
    return {"deleted": True}


@router.get("/roxy/health")
async def roxy_health(connection_id: str = Query(...), db: Session = Depends(get_db)):
    _require_enabled()
    try:
        return await _roxy_client(connection_id, db).health()
    except roxy.RoxyApiError as exc:
        raise _error(502, str(exc), exc.error_code) from exc


@router.get("/roxy/workspaces")
async def roxy_workspaces(connection_id: str = Query(...), db: Session = Depends(get_db)):
    _require_enabled()
    try:
        return await _roxy_client(connection_id, db).workspaces()
    except roxy.RoxyApiError as exc:
        raise _error(502, str(exc), exc.error_code) from exc


@router.get("/roxy/profiles")
async def roxy_profiles(
    connection_id: str = Query(...),
    workspace_id: int = Query(..., ge=1),
    project_ids: str | None = Query(None),
    db: Session = Depends(get_db),
):
    _require_enabled()
    try:
        payload = await _roxy_client(connection_id, db).profiles(workspace_id, project_ids=project_ids)
    except roxy.RoxyApiError as exc:
        raise _error(502, str(exc), exc.error_code) from exc
    rows = []
    for row in payload.get("rows", []) if isinstance(payload, dict) else []:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "dir_id": row.get("dirId"),
                "window_name": row.get("windowName"),
                "window_remark": row.get("windowRemark"),
                "window_sort_num": row.get("windowSortNum"),
                "workspace_name": row.get("workspaceName"),
                "core_type": row.get("coreType"),
                "core_version": row.get("coreVersion"),
                "os": row.get("os"),
            }
        )
    return {"rows": rows, "total": payload.get("total", len(rows)) if isinstance(payload, dict) else len(rows)}


@router.post("/roxy/profiles/open")
async def roxy_open_profile(data: RoxyProfileOpenRequest, db: Session = Depends(get_db)):
    _require_enabled()
    try:
        return await _roxy_client(data.connection_id, db).open_profile(
            data.workspace_id,
            data.dir_id,
            force_open=data.force_open,
            args=data.args,
        )
    except roxy.RoxyApiError as exc:
        raise _error(502, str(exc), exc.error_code) from exc


@router.post("/roxy/profiles/close")
async def roxy_close_profiles(data: RoxyProfileCloseRequest, db: Session = Depends(get_db)):
    _require_enabled()
    try:
        return await _roxy_client(data.connection_id, db).close_profiles(data.dir_ids)
    except roxy.RoxyApiError as exc:
        raise _error(502, str(exc), exc.error_code) from exc


@router.get("/roxy/connection-info")
async def roxy_connection_info(
    connection_id: str = Query(...),
    dir_ids: list[str] | None = Query(None),
    db: Session = Depends(get_db),
):
    _require_enabled()
    try:
        return {"connections": await _roxy_client(connection_id, db).connection_info(dir_ids)}
    except roxy.RoxyApiError as exc:
        raise _error(502, str(exc), exc.error_code) from exc


@router.get("/sidecar/status")
async def get_sidecar_status():
    return await sidecar.status()


@router.post("/sidecar/start")
async def start_sidecar():
    _require_enabled()
    try:
        return await sidecar.start()
    except sidecar.SidecarError as exc:
        raise _error(422, str(exc), exc.error_code) from exc


@router.post("/sidecar/stop")
async def stop_sidecar():
    _require_enabled()
    return await sidecar.stop()


@router.get("/assets", response_model=list[AutomationAssetResponse])
async def list_automation_assets(db: Session = Depends(get_db)):
    return assets.list_assets(db)


@router.post("/assets/upload", response_model=AutomationAssetResponse)
async def upload_automation_asset(file: UploadFile = File(...), db: Session = Depends(get_db)):
    _require_enabled()
    try:
        return await assets.create_from_upload(file, db)
    except assets.AssetError as exc:
        raise _error(422, str(exc), exc.error_code) from exc


@router.post("/assets/import-render", response_model=AutomationAssetResponse)
async def import_render_asset(data: AutomationRenderAssetImportRequest, db: Session = Depends(get_db)):
    _require_enabled()
    try:
        return assets.import_render_output(data.render_job_id, db)
    except assets.AssetError as exc:
        raise _error(422, str(exc), exc.error_code) from exc


@router.delete("/assets/{asset_id}")
async def delete_automation_asset(asset_id: str, db: Session = Depends(get_db)):
    _require_enabled()
    try:
        deleted = assets.delete_asset(asset_id, db)
    except assets.AssetError as exc:
        raise _error(409, str(exc), exc.error_code) from exc
    if not deleted:
        raise _error(404, "Không tìm thấy asset.", "AUTOMATION_ASSET_NOT_FOUND")
    return {"deleted": True}


@router.get("/jobs", response_model=list[AutomationPublishJobResponse])
async def list_publish_jobs(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return jobs.list_jobs(db, limit=limit)


@router.post("/jobs", response_model=AutomationPublishJobResponse)
async def create_publish_job(data: AutomationPublishJobCreate, db: Session = Depends(get_db)):
    _require_enabled()
    try:
        return jobs.create_job(data, db)
    except jobs.JobError as exc:
        raise _error(422, str(exc), exc.error_code) from exc


@router.get("/jobs/{job_id}", response_model=AutomationPublishJobResponse)
async def get_publish_job(job_id: str, db: Session = Depends(get_db)):
    row = jobs.get_job(job_id, db)
    if row is None:
        raise _error(404, "Không tìm thấy publishing job.", "AUTOMATION_JOB_NOT_FOUND")
    return jobs.to_response(row, db)


@router.post("/jobs/{job_id}/cancel", response_model=AutomationPublishJobResponse)
async def cancel_publish_job(job_id: str, db: Session = Depends(get_db)):
    _require_enabled()
    response = jobs.cancel_job(job_id, db)
    if response is None:
        raise _error(404, "Không tìm thấy publishing job.", "AUTOMATION_JOB_NOT_FOUND")
    return response


@router.post("/jobs/{job_id}/retry", response_model=AutomationPublishJobResponse)
async def retry_publish_job(job_id: str, db: Session = Depends(get_db)):
    _require_enabled()
    try:
        response = jobs.retry_job(job_id, db)
    except jobs.JobError as exc:
        raise _error(409, str(exc), exc.error_code) from exc
    if response is None:
        raise _error(404, "Không tìm thấy publishing job.", "AUTOMATION_JOB_NOT_FOUND")
    return response


@router.delete("/jobs/{job_id}")
async def delete_publish_job(job_id: str, db: Session = Depends(get_db)):
    _require_enabled()
    try:
        deleted = jobs.delete_job(job_id, db)
    except jobs.JobError as exc:
        raise _error(409, str(exc), exc.error_code) from exc
    if not deleted:
        raise _error(404, "Không tìm thấy publishing job.", "AUTOMATION_JOB_NOT_FOUND")
    return {"deleted": True}
