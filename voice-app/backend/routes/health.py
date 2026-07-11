"""Health and infrastructure endpoints."""

import asyncio
import os
import platform
import re
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import torch
from fastapi import APIRouter
from fastapi.responses import FileResponse

from .. import config, models
from ..utils.platform_detect import get_backend_type
from ..services import tts

router = APIRouter()

# Frontend build directory — present in Docker, absent in dev/API-only mode
_frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"


def _metric_status(percent: float | None) -> str:
    if percent is None:
        return "unknown"
    if percent >= 90:
        return "critical"
    if percent >= 75:
        return "warning"
    return "normal"


def _clamp_percent(value: float | None) -> float | None:
    if value is None:
        return None
    return round(max(0.0, min(100.0, value)), 1)


def _temperature_status(temperature_c: float | None) -> str:
    if temperature_c is None:
        return "unknown"
    if temperature_c >= 90:
        return "critical"
    if temperature_c >= 80:
        return "warning"
    return "normal"


def _temperature_percent(temperature_c: float | None) -> float | None:
    if temperature_c is None:
        return None
    return _clamp_percent(temperature_c)


def _run_command(args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            timeout=1.5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout


def _cpu_percent() -> float | None:
    try:
        import psutil

        return _clamp_percent(float(psutil.cpu_percent(interval=0.1)))
    except (ImportError, OSError, ValueError):
        pass

    cpu_count = os.cpu_count() or 1
    if platform.system() == "Darwin":
        output = _run_command(["ps", "-A", "-o", "%cpu="])
        if output:
            values: list[float] = []
            for line in output.splitlines():
                try:
                    values.append(float(line.strip()))
                except ValueError:
                    continue
            if values:
                return _clamp_percent(sum(values) / cpu_count)

    try:
        load_1m = os.getloadavg()[0]
    except (AttributeError, OSError):
        return None
    return _clamp_percent((load_1m / cpu_count) * 100)


def _linux_memory_stats() -> tuple[float, float, float] | None:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None
    values: dict[str, float] = {}
    try:
        for line in meminfo.read_text().splitlines():
            key, raw_value = line.split(":", 1)
            values[key] = float(raw_value.strip().split()[0]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if not total or available is None:
        return None
    used = max(0.0, total - available)
    percent = (used / total) * 100 if total else None
    return used, total, _clamp_percent(percent) or 0.0


def _mac_memory_stats() -> tuple[float, float, float] | None:
    total_output = _run_command(["sysctl", "-n", "hw.memsize"])
    vm_output = _run_command(["vm_stat"])
    page_output = _run_command(["pagesize"])
    if not total_output or not vm_output:
        return None
    try:
        total = float(total_output.strip())
        page_size = float(page_output.strip()) if page_output else 4096.0
    except ValueError:
        return None

    pages: dict[str, float] = {}
    for line in vm_output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        try:
            pages[key.strip()] = float(value.strip().rstrip("."))
        except ValueError:
            continue

    free_pages = pages.get("Pages free", 0.0) + pages.get("Pages speculative", 0.0)
    inactive_pages = pages.get("Pages inactive", 0.0)
    compressed_pages = pages.get("Pages occupied by compressor", 0.0)
    available = max(0.0, (free_pages + inactive_pages - compressed_pages) * page_size)
    used = max(0.0, min(total, total - available))
    percent = (used / total) * 100 if total else None
    return used, total, _clamp_percent(percent) or 0.0


def _memory_stats() -> tuple[float, float, float] | None:
    try:
        import psutil

        memory = psutil.virtual_memory()
        used = float(memory.used)
        total = float(memory.total)
        percent = _clamp_percent(float(memory.percent)) or 0.0
        return used, total, percent
    except (ImportError, OSError, ValueError):
        pass

    if platform.system() == "Darwin":
        return _mac_memory_stats()
    if platform.system() == "Linux":
        return _linux_memory_stats()
    return None


def _parse_mac_gpu_performance_stats(output: str) -> dict[str, float]:
    stats_match = re.search(r'"PerformanceStatistics"\s*=\s*\{([^}]*)\}', output, re.DOTALL)
    if not stats_match:
        return {}

    stats: dict[str, float] = {}
    for key, value in re.findall(r'"([^"]+)"\s*=\s*([-+]?\d+(?:\.\d+)?)', stats_match.group(1)):
        try:
            stats[key] = float(value)
        except ValueError:
            continue
    return stats


def _mac_gpu_resource_metric() -> models.SystemResourceMetric | None:
    output = _run_command(["ioreg", "-r", "-d", "1", "-w", "0", "-c", "AGXAccelerator"])
    if not output:
        output = _run_command(["ioreg", "-r", "-d", "1", "-w", "0", "-c", "IOGPU"])
    if not output:
        return None

    stats = _parse_mac_gpu_performance_stats(output)
    percent = _clamp_percent(stats.get("Device Utilization %"))
    used = stats.get("In use system memory")
    total = stats.get("Alloc system memory")
    used_mb = round(used / 1024 / 1024, 1) if used is not None else None
    total_mb = round(total / 1024 / 1024, 1) if total is not None else None
    renderer = stats.get("Renderer Utilization %")
    tiler = stats.get("Tiler Utilization %")
    label = "Metal GPU"
    if renderer is not None and tiler is not None:
        label = f"{label} · renderer {round(renderer)}%, tiler {round(tiler)}%"

    if percent is None and used_mb is None:
        return None

    return models.SystemResourceMetric(
        percent=percent,
        used=used_mb,
        total=total_mb,
        unit="MB",
        label=label,
        status=_metric_status(percent),
    )


def _parse_nvidia_smi_gpu_stats(output: str) -> list[tuple[float, float | None, float | None, str | None]]:
    stats: list[tuple[float, float | None, float | None, str | None]] = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",", 3)]
        if len(parts) < 3:
            continue
        try:
            percent = float(parts[0])
        except ValueError:
            continue

        used_mb = None
        total_mb = None
        try:
            used_mb = float(parts[1])
        except ValueError:
            pass
        try:
            total_mb = float(parts[2])
        except ValueError:
            pass

        name = parts[3] if len(parts) >= 4 and parts[3] else None
        stats.append((percent, used_mb, total_mb, name))
    return stats


def _nvidia_gpu_resource_metric() -> tuple[models.SystemResourceMetric, bool, str | None] | None:
    output = _run_command([
        "nvidia-smi",
        "--query-gpu=utilization.gpu,memory.used,memory.total,name",
        "--format=csv,noheader,nounits",
    ])
    if not output:
        return None

    stats = _parse_nvidia_smi_gpu_stats(output)
    if not stats:
        return None

    percent, used_mb, total_mb, name = max(stats, key=lambda item: item[0])
    percent = _clamp_percent(percent) or 0.0
    gpu_type = f"NVIDIA ({name})" if name else "NVIDIA GPU"
    return (
        models.SystemResourceMetric(
            percent=percent,
            used=round(used_mb, 1) if used_mb is not None else None,
            total=round(total_mb, 1) if total_mb is not None else None,
            unit="MB",
            label="NVIDIA GPU utilization",
            status=_metric_status(percent),
        ),
        True,
        gpu_type,
    )


def _gpu_resource_metric() -> tuple[models.SystemResourceMetric, bool, str | None]:
    backend_type = get_backend_type()
    has_cuda = torch.cuda.is_available()
    has_mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    gpu_available = has_cuda or has_mps or backend_type == "mlx"
    gpu_type = None
    metric = models.SystemResourceMetric(
        percent=None,
        label="GPU utilization unavailable",
        status="unknown",
    )

    if has_cuda:
        gpu_type = f"CUDA ({torch.cuda.get_device_name(0)})"
        try:
            props = torch.cuda.get_device_properties(0)
            used_mb = torch.cuda.memory_allocated() / 1024 / 1024
            total_mb = props.total_memory / 1024 / 1024
            percent = _clamp_percent((used_mb / total_mb) * 100 if total_mb else None)
            metric = models.SystemResourceMetric(
                percent=percent,
                used=round(used_mb, 1),
                total=round(total_mb, 1),
                unit="MB",
                label="CUDA memory",
                status=_metric_status(percent),
            )
        except Exception:
            metric.label = "CUDA memory unavailable"
    else:
        nvidia_metric = _nvidia_gpu_resource_metric()
        if nvidia_metric is not None:
            return nvidia_metric

    if backend_type == "mlx":
        gpu_type = "Metal (Apple Silicon via MLX)"
        gpu_available = True
        metric = _mac_gpu_resource_metric() or metric
        if metric.label == "GPU utilization unavailable":
            metric.label = "Metal load unavailable"
    elif has_mps:
        gpu_type = "MPS (Apple Silicon)"
        metric = _mac_gpu_resource_metric() or metric
        if metric.label == "GPU utilization unavailable":
            metric.label = "MPS load unavailable"

    return metric, gpu_available, gpu_type


def _parse_nvidia_smi_temperatures(output: str) -> list[float]:
    temperatures: list[float] = []
    for raw_value in re.findall(r"[-+]?\d+(?:\.\d+)?", output):
        try:
            temperature = float(raw_value)
        except ValueError:
            continue
        if 0 <= temperature <= 130:
            temperatures.append(temperature)
    return temperatures


def _nvidia_temperature_metric() -> models.SystemResourceMetric | None:
    output = _run_command([
        "nvidia-smi",
        "--query-gpu=temperature.gpu",
        "--format=csv,noheader,nounits",
    ])
    if not output:
        return None

    temperatures = _parse_nvidia_smi_temperatures(output)
    if not temperatures:
        return None

    temperature = max(temperatures)
    return models.SystemResourceMetric(
        percent=_temperature_percent(temperature),
        used=round(temperature, 1),
        unit="C",
        label="NVIDIA GPU temperature",
        status=_temperature_status(temperature),
    )


def _linux_temperature_metric(
    hwmon_root: Path = Path("/sys/class/hwmon"),
) -> models.SystemResourceMetric | None:
    if not hwmon_root.exists():
        return None

    readings: list[tuple[float, str]] = []
    for sensor_dir in sorted(hwmon_root.glob("hwmon*")):
        sensor_name = "System"
        try:
            name_path = sensor_dir / "name"
            if name_path.exists():
                sensor_name = name_path.read_text(encoding="utf-8").strip() or sensor_name
        except OSError:
            pass

        for input_path in sorted(sensor_dir.glob("temp*_input")):
            try:
                raw_value = float(input_path.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                continue
            temperature = raw_value / 1000.0 if raw_value > 1000 else raw_value
            if 0 <= temperature <= 130:
                readings.append((temperature, sensor_name))

    if not readings:
        return None

    temperature, sensor_name = max(readings, key=lambda item: item[0])
    return models.SystemResourceMetric(
        percent=_temperature_percent(temperature),
        used=round(temperature, 1),
        unit="C",
        label=f"{sensor_name} temperature",
        status=_temperature_status(temperature),
    )


def _mac_thermal_pressure_metric() -> models.SystemResourceMetric | None:
    output = _run_command(["pmset", "-g", "therm"])
    if not output:
        return None

    lower_output = output.lower()
    if "no thermal warning level" in lower_output:
        return models.SystemResourceMetric(
            percent=0,
            label="Thermal pressure normal",
            status="normal",
        )

    level_match = re.search(r"thermal\s+warning\s+level\D+(\d+)", lower_output)
    level = int(level_match.group(1)) if level_match else None
    if level is None:
        return models.SystemResourceMetric(
            label="Thermal pressure available",
            status="unknown",
        )

    status = "critical" if level >= 2 else ("warning" if level >= 1 else "normal")
    percent = 95 if status == "critical" else (80 if status == "warning" else 0)
    return models.SystemResourceMetric(
        percent=percent,
        label=f"Thermal pressure level {level}",
        status=status,
    )


def _thermal_resource_metric() -> models.SystemResourceMetric:
    nvidia_metric = _nvidia_temperature_metric()
    if nvidia_metric is not None:
        return nvidia_metric

    if platform.system() == "Linux":
        linux_metric = _linux_temperature_metric()
        if linux_metric is not None:
            return linux_metric

    if platform.system() == "Darwin":
        mac_metric = _mac_thermal_pressure_metric()
        if mac_metric is not None:
            return mac_metric

    return models.SystemResourceMetric(label="Temperature unavailable", status="unknown")


@router.get("/")
async def root():
    """Root endpoint — serves SPA index.html in Docker, JSON otherwise."""
    from .. import __version__

    index = _frontend_dir / "index.html"
    if index.is_file():
        return FileResponse(index, media_type="text/html")
    return {"message": "voicebox API", "version": __version__}


@router.post("/shutdown")
async def shutdown():
    """Gracefully shutdown the server."""

    async def shutdown_async():
        await asyncio.sleep(0.1)
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(shutdown_async())
    return {"message": "Shutting down..."}


@router.post("/watchdog/disable")
async def watchdog_disable():
    """Disable the parent process watchdog so the server keeps running."""
    from backend.server import disable_watchdog

    disable_watchdog()
    return {"message": "Watchdog disabled"}


@router.get("/health", response_model=models.HealthResponse)
async def health():
    """Health check endpoint."""
    from huggingface_hub import constants as hf_constants
    from pathlib import Path

    tts_model = tts.get_tts_model()
    backend_type = get_backend_type()

    has_cuda = torch.cuda.is_available()
    has_mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()

    has_xpu = False
    xpu_name = None
    try:
        import intel_extension_for_pytorch as ipex  # noqa: F401 -- side-effect import enables XPU

        if hasattr(torch, "xpu") and torch.xpu.is_available():
            has_xpu = True
            try:
                xpu_name = torch.xpu.get_device_name(0)
            except Exception:
                xpu_name = "Intel GPU"
    except ImportError:
        pass

    has_directml = False
    directml_name = None
    try:
        import torch_directml

        if torch_directml.device_count() > 0:
            has_directml = True
            try:
                directml_name = torch_directml.device_name(0)
            except Exception:
                directml_name = "DirectML GPU"
    except ImportError:
        pass

    gpu_compat_warning = None
    if has_cuda:
        from ..backends.base import check_cuda_compatibility

        _compatible, gpu_compat_warning = check_cuda_compatibility()

    gpu_available = has_cuda or has_mps or has_xpu or has_directml or backend_type == "mlx"

    gpu_type = None
    if has_cuda:
        gpu_type = f"CUDA ({torch.cuda.get_device_name(0)})"
    elif has_mps:
        gpu_type = "MPS (Apple Silicon)"
    elif backend_type == "mlx":
        gpu_type = "Metal (Apple Silicon via MLX)"
    elif has_xpu:
        gpu_type = f"XPU ({xpu_name})"
    elif has_directml:
        gpu_type = f"DirectML ({directml_name})"

    vram_used = None
    if has_cuda:
        vram_used = torch.cuda.memory_allocated() / 1024 / 1024
    elif has_xpu:
        try:
            vram_used = torch.xpu.memory_allocated() / 1024 / 1024
        except Exception:
            pass  # memory_allocated() may not be available on all IPEX versions

    model_loaded = False
    model_size = None
    try:
        if tts_model.is_loaded():
            model_loaded = True
            model_size = getattr(tts_model, "_current_model_size", None)
            if not model_size:
                model_size = getattr(tts_model, "model_size", None)
    except Exception:
        model_loaded = False
        model_size = None

    model_downloaded = None
    try:
        from ..backends import get_model_config

        default_config = get_model_config("qwen-tts-1.7B")
        default_model_id = default_config.hf_repo_id if default_config else "Qwen/Qwen3-TTS-12Hz-1.7B-Base"

        try:
            from huggingface_hub import scan_cache_dir

            cache_info = scan_cache_dir()
            for repo in cache_info.repos:
                if repo.repo_id == default_model_id:
                    model_downloaded = True
                    break
        except (ImportError, Exception):
            cache_dir = hf_constants.HF_HUB_CACHE
            repo_cache = Path(cache_dir) / ("models--" + default_model_id.replace("/", "--"))
            if repo_cache.exists():
                has_model_files = (
                    any(repo_cache.rglob("*.bin"))
                    or any(repo_cache.rglob("*.safetensors"))
                    or any(repo_cache.rglob("*.pt"))
                    or any(repo_cache.rglob("*.pth"))
                    or any(repo_cache.rglob("*.npz"))
                )
                model_downloaded = has_model_files
    except Exception:
        pass

    return models.HealthResponse(
        status="healthy",
        model_loaded=model_loaded,
        model_downloaded=model_downloaded,
        model_size=model_size,
        gpu_available=gpu_available,
        gpu_type=gpu_type,
        vram_used_mb=vram_used,
        backend_type=backend_type,
        backend_variant=os.environ.get(
            "VOICEBOX_BACKEND_VARIANT",
            "cuda" if torch.cuda.is_available() else ("xpu" if has_xpu else "cpu"),
        ),
        gpu_compatibility_warning=gpu_compat_warning,
    )


@router.get("/health/system", response_model=models.SystemResourcesResponse)
async def system_resources():
    """Live host resource usage for the local dashboard."""
    cpu_percent = _cpu_percent()
    memory = _memory_stats()
    gpu_metric, gpu_available, gpu_type = _gpu_resource_metric()
    thermal_metric = _thermal_resource_metric()
    memory_metric = (
        models.SystemResourceMetric(
            percent=memory[2],
            used=round(memory[0] / 1024 / 1024, 1),
            total=round(memory[1] / 1024 / 1024, 1),
            unit="MB",
            label="System memory",
            status=_metric_status(memory[2]),
        )
        if memory
        else models.SystemResourceMetric(label="Memory unavailable", status="unknown")
    )

    return models.SystemResourcesResponse(
        sampled_at=datetime.now(timezone.utc),
        cpu=models.SystemResourceMetric(
            percent=cpu_percent,
            label="System CPU",
            status=_metric_status(cpu_percent),
        ),
        memory=memory_metric,
        gpu=gpu_metric,
        thermal=thermal_metric,
        cpu_count=os.cpu_count(),
        gpu_available=gpu_available,
        gpu_type=gpu_type,
        backend_type=get_backend_type(),
        backend_variant=os.environ.get(
            "VOICEBOX_BACKEND_VARIANT",
            "cuda" if torch.cuda.is_available() else "cpu",
        ),
    )


@router.get("/health/filesystem", response_model=models.FilesystemHealthResponse)
async def filesystem_health():
    """Check filesystem health: directory existence, write permissions, and disk space."""
    import shutil

    dirs_to_check = {
        "generations": config.get_generations_dir(),
        "captures": config.get_captures_dir(),
        "profiles": config.get_profiles_dir(),
        "data": config.get_data_dir(),
    }

    checks: list[models.DirectoryCheck] = []
    all_ok = True

    for _label, dir_path in dirs_to_check.items():
        exists = dir_path.exists()
        writable = False
        error = None
        if exists:
            probe = dir_path / ".voicebox_probe"
            try:
                probe.write_text("ok")
                probe.unlink()
                writable = True
            except PermissionError:
                error = "Permission denied"
            except OSError as e:
                error = str(e)
            finally:
                try:
                    probe.unlink(missing_ok=True)
                except Exception:
                    pass
        else:
            error = "Directory does not exist"

        if not exists or not writable:
            all_ok = False

        checks.append(
            models.DirectoryCheck(
                path=str(dir_path.resolve()),
                exists=exists,
                writable=writable,
                error=error,
            )
        )

    disk_free_mb = None
    disk_total_mb = None
    try:
        usage = shutil.disk_usage(str(config.get_data_dir()))
        disk_free_mb = round(usage.free / (1024 * 1024), 1)
        disk_total_mb = round(usage.total / (1024 * 1024), 1)
        if disk_free_mb < 500:
            all_ok = False
    except OSError:
        all_ok = False

    return models.FilesystemHealthResponse(
        healthy=all_ok,
        disk_free_mb=disk_free_mb,
        disk_total_mb=disk_total_mb,
        directories=checks,
    )
