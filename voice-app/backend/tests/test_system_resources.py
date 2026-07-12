from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import models
from backend.routes import health


def test_parse_mac_gpu_performance_stats():
    output = '''
    "PerformanceStatistics" = {"In use system memory (driver)"=0,"Alloc system memory"=1368244224,"Tiler Utilization %"=64,"Renderer Utilization %"=63,"Device Utilization %"=64,"In use system memory"=449363968}
    '''

    stats = health._parse_mac_gpu_performance_stats(output)

    assert stats["Device Utilization %"] == 64
    assert stats["Renderer Utilization %"] == 63
    assert stats["Tiler Utilization %"] == 64
    assert stats["In use system memory"] == 449363968
    assert stats["Alloc system memory"] == 1368244224


def test_mac_gpu_resource_metric_uses_ioreg_performance_stats(monkeypatch):
    output = '''
    "PerformanceStatistics" = {"Alloc system memory"=1073741824,"Tiler Utilization %"=52,"Renderer Utilization %"=48,"Device Utilization %"=50,"In use system memory"=536870912}
    '''
    monkeypatch.setattr(health, "_run_command", lambda _args: output)

    metric = health._mac_gpu_resource_metric()

    assert metric is not None
    assert metric.percent == 50
    assert metric.used == 512
    assert metric.total == 1024
    assert metric.unit == "MB"
    assert metric.status == "normal"
    assert metric.label == "Metal GPU · renderer 48%, tiler 52%"


def test_parse_nvidia_smi_temperatures_uses_valid_values():
    temperatures = health._parse_nvidia_smi_temperatures("71\n84\nN/A\n")

    assert temperatures == [71.0, 84.0]


def test_linux_temperature_metric_uses_hottest_hwmon_sensor(tmp_path):
    sensor = tmp_path / "hwmon0"
    sensor.mkdir()
    (sensor / "name").write_text("soc_thermal", encoding="utf-8")
    (sensor / "temp1_input").write_text("51250", encoding="utf-8")
    (sensor / "temp2_input").write_text("82500", encoding="utf-8")

    metric = health._linux_temperature_metric(tmp_path)

    assert metric is not None
    assert metric.used == 82.5
    assert metric.unit == "C"
    assert metric.percent == 82.5
    assert metric.status == "warning"
    assert metric.label == "soc_thermal temperature"


def test_system_resources_endpoint_returns_monitor_payload(monkeypatch):
    app = FastAPI()
    app.include_router(health.router)

    monkeypatch.setattr(health, "_cpu_percent", lambda: 42.5)
    monkeypatch.setattr(health, "_memory_stats", lambda: (6 * 1024 * 1024, 16 * 1024 * 1024, 37.5))
    monkeypatch.setattr(
        health,
        "_gpu_resource_metric",
        lambda: (
            models.SystemResourceMetric(
                percent=18.0,
                used=900.0,
                total=5000.0,
                unit="MB",
                label="CUDA memory",
                status="normal",
            ),
            True,
            "CUDA (Test GPU)",
        ),
    )
    monkeypatch.setattr(
        health,
        "_thermal_resource_metric",
        lambda: models.SystemResourceMetric(
            percent=72.0,
            used=72.0,
            unit="C",
            label="NVIDIA GPU temperature",
            status="normal",
        ),
    )
    monkeypatch.setattr(health, "get_backend_type", lambda: "pytorch")

    response = TestClient(app).get("/health/system")

    assert response.status_code == 200
    data = response.json()
    assert data["cpu"]["percent"] == 42.5
    assert data["cpu"]["status"] == "normal"
    assert data["memory"]["percent"] == 37.5
    assert data["memory"]["unit"] == "MB"
    assert data["gpu"]["percent"] == 18.0
    assert data["gpu_available"] is True
    assert data["gpu_type"] == "CUDA (Test GPU)"
    assert data["thermal"]["used"] == 72.0
    assert data["thermal"]["unit"] == "C"
    assert data["thermal"]["label"] == "NVIDIA GPU temperature"
    assert data["sampled_at"]

def test_health_ready_endpoint_is_lightweight(monkeypatch):
    app = FastAPI()
    app.include_router(health.router)

    def fail_if_model_status_is_checked():
        raise AssertionError("readiness check should not inspect TTS model state")

    monkeypatch.setattr(health.tts, "get_tts_model", fail_if_model_status_is_checked)

    response = TestClient(app).get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
