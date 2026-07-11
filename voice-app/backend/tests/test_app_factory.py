from backend.app import create_app


def test_app_factory_registers_core_routes():
    app = create_app()
    paths = set(app.openapi()["paths"])
    mounted_paths = {getattr(route, "path", "") for route in app.routes}

    assert "/health" in paths
    assert "/ai-video/projects" in paths
    assert "/mcp" in mounted_paths
