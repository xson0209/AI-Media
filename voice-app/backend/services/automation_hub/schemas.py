"""Pydantic contracts for Automation Hub routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Platform = Literal["roxy", "youtube", "facebook", "tiktok"]


class AutomationHubStatusResponse(BaseModel):
    enabled: bool
    direct_post_enabled: bool
    secret_store: dict[str, Any]
    worker: dict[str, Any]
    sidecar: dict[str, Any]
    prerequisites: list[str]


class AutomationConnectionCreate(BaseModel):
    kind: Literal["roxy", "publisher"] = "publisher"
    platform: Platform
    label: str = Field(min_length=1, max_length=160)
    public_config: dict[str, Any] = Field(default_factory=dict)
    secret: dict[str, Any]
    scopes: list[str] = Field(default_factory=list)


class AutomationConnectionUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=160)
    public_config: dict[str, Any] | None = None
    secret: dict[str, Any] | None = None
    scopes: list[str] | None = None


class AutomationConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    platform: str
    label: str
    status: str
    public_config: dict[str, Any] = Field(default_factory=dict)
    has_secret: bool = False
    secret_fingerprint: str | None = None
    scopes: list[str] = Field(default_factory=list)
    last_checked_at: datetime | None = None
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class AutomationAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_type: str
    source_ref: str | None = None
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


class AutomationRenderAssetImportRequest(BaseModel):
    render_job_id: str


class AutomationPublishJobCreate(BaseModel):
    asset_id: str
    connection_id: str
    platform: Literal["youtube", "facebook", "tiktok"]
    publish_mode: str = "standard"
    title: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=10000)
    tags: list[str] = Field(default_factory=list, max_length=100)
    privacy: str | None = None
    scheduled_at: datetime | None = None
    idempotency_key: str = Field(min_length=8, max_length=200)


class AutomationPublishAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    attempt_number: int
    status: str
    request_meta: dict[str, Any] = Field(default_factory=dict)
    response_meta: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    failure_reason: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class AutomationPublishJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_id: str
    connection_id: str
    platform: str
    publish_mode: str
    status: str
    title: str
    description: str
    tags: list[str] = Field(default_factory=list)
    privacy: str | None = None
    scheduled_at: datetime | None = None
    idempotency_key: str
    attempt_count: int
    cancel_requested: bool
    provider_post_id: str | None = None
    provider_url: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    failure_reason: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    attempts: list[AutomationPublishAttemptResponse] = Field(default_factory=list)


class RoxyProfileOpenRequest(BaseModel):
    connection_id: str
    workspace_id: int
    dir_id: str
    force_open: bool = True
    args: list[str] = Field(default_factory=list, max_length=20)


class RoxyProfileCloseRequest(BaseModel):
    connection_id: str
    dir_ids: list[str] = Field(min_length=1, max_length=20)
