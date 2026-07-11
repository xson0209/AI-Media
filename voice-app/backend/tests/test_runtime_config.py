from pathlib import Path

from backend import config as compat_config
from backend.core import config


def test_runtime_config_defaults():
    settings = config.load_runtime_config({})

    assert settings.backend_host == "127.0.0.1"
    assert settings.backend_port == 17493
    assert settings.frontend_port == 5173
    assert "http://localhost:5173" in settings.cors_origins
    assert "http://127.0.0.1:5173" in settings.cors_origins
    assert "http://localhost:17493" in settings.cors_origins
    assert settings.backend_url == "http://127.0.0.1:17493"


def test_runtime_config_env_overrides(tmp_path):
    data_dir = tmp_path / "data-root"
    models_dir = tmp_path / "models-root"
    cache_dir = tmp_path / "cache-root"

    settings = config.load_runtime_config(
        {
            "VOICEBOX_BACKEND_HOST": "0.0.0.0",
            "VOICEBOX_BACKEND_PORT": "19090",
            "VOICEBOX_FRONTEND_PORT": "5300",
            "VOICEBOX_PUBLIC_BACKEND_URL": "https://voicebox.example.test/api/",
            "VOICEBOX_CORS_ORIGINS": "https://custom.example.test, https://other.example.test ",
            "VOICEBOX_DATA_DIR": str(data_dir),
            "VOICEBOX_MODELS_DIR": str(models_dir),
            "VOICEBOX_CACHE_DIR": str(cache_dir),
            "VOICEBOX_FEATURE_EXAMPLE": "true",
        }
    )

    assert settings.backend_host == "0.0.0.0"
    assert settings.backend_port == 19090
    assert settings.frontend_port == 5300
    assert settings.backend_url == "https://voicebox.example.test/api"
    assert "http://localhost:5300" in settings.cors_origins
    assert "http://127.0.0.1:5300" in settings.cors_origins
    assert "http://localhost:19090" in settings.cors_origins
    assert "https://custom.example.test" in settings.cors_origins
    assert settings.data_dir == data_dir.resolve()
    assert settings.models_dir == models_dir.resolve()
    assert settings.cache_dir == cache_dir.resolve()
    assert settings.feature_flags["example"] == "true"


def test_legacy_port_env_is_supported():
    settings = config.load_runtime_config({"VOICEBOX_PORT": "18000"})

    assert settings.backend_port == 18000
    assert "http://localhost:18000" in settings.cors_origins


def test_path_helpers_and_compat_wrapper(tmp_path):
    previous_data_dir = config.get_data_dir()
    try:
        config.set_data_dir(tmp_path)
        profile_path = config.get_profiles_dir() / "sample.wav"

        assert config.to_storage_path(profile_path) == str(Path("profiles") / "sample.wav")
        assert config.resolve_storage_path("profiles/sample.wav") == profile_path.resolve()
        assert compat_config.get_data_dir() == tmp_path.resolve()
    finally:
        config.set_data_dir(previous_data_dir)
