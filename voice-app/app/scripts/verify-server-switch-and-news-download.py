"""Browser regression coverage; all server requests are intercepted locally."""

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

base = sys.argv[1]
checks = []
held = []
requests = []
hold_a_health = False
hold_b_data = False
hold_download = False
fail_download = False
prompt_text = "Prompt tiếng Việt: nhân vật nói đúng lời.\nGiữ nguyên UTF-8."


def check(name, condition=True):
    assert condition, name
    checks.append(name)


def fulfill_json(route, value):
    route.fulfill(status=200, content_type="application/json", body=json.dumps(value))


def route_api(route):
    path = urlparse(route.request.url).path
    server, endpoint = path.split("/", 2)[1:]
    requests.append((server, endpoint))
    if endpoint == "health":
        if server == "server-a" and hold_a_health or server == "server-b" and hold_b_data:
            held.append((server, endpoint, route))
        else:
            fulfill_json(route, {"status": "A-current" if server == "server-a" else "B-current"})
    elif endpoint == "news-video/projects":
        if server == "server-b" and hold_b_data:
            held.append((server, endpoint, route))
        else:
            fulfill_json(route, [{"id": "news-id", "title": "Project A" if server == "server-a" else "Project B", "status": "ready"}])
    elif endpoint.endswith("/prompt-pack"):
        if hold_download:
            held.append((server, endpoint, route))
        elif fail_download:
            route.fulfill(status=500, content_type="application/json", body=json.dumps({"detail": "Pack unavailable"}))
        else:
            route.fulfill(status=200, content_type="text/plain; charset=utf-8", body=prompt_text.encode("utf-8"),
                          headers={"Content-Disposition": "attachment; filename*=UTF-8''prompt-tieng-viet.txt"})
    elif endpoint == "news-video/projects/news-id":
        fulfill_json(route, {"id": "news-id", "title": "News", "aspect_ratio": "9:16", "target_language": "vi", "speech_source": "veo_dialogue", "shots": []})
    elif endpoint.endswith("/render/sfx-assets"):
        fulfill_json(route, [])
    else:
        fulfill_json(route, None)


def browser_executable(pw):
    configured = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    if configured:
        return configured
    default = Path(pw.chromium.executable_path)
    if default.exists():
        return str(default)
    cache = Path(os.environ["LOCALAPPDATA"]) / "ms-playwright" if os.name == "nt" else Path.home() / ".cache/ms-playwright"
    choices = sorted(cache.glob("chromium-*/chrome-win*/chrome.exe")) + sorted(cache.glob("chromium-*/chrome-linux*/chrome"))
    return str(choices[-1]) if choices else None


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, executable_path=browser_executable(pw))
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("**/server-*/**", route_api)
    page.goto(base)
    expect(page.locator("#health")).to_have_text("A-current")
    expect(page.get_by_role("button", name="Project A", exact=False)).to_be_visible()
    page.get_by_role("button", name="Seed inactive cache").click()
    expect(page.locator("#inactive")).to_have_text("cached-A")
    expect(page.locator("#seeded")).to_have_text("A-current")
    page.get_by_role("button", name="Same server", exact=True).click()
    expect(page.locator("#inactive")).to_have_text("cached-A")
    check("Selecting the same server preserves its cache")

    hold_a_health = hold_b_data = True
    page.get_by_role("button", name="Refetch health").click()
    page.wait_for_function("() => true")
    page.get_by_role("button", name="Server B", exact=True).click()
    expect(page.locator("#health")).to_have_text("empty")
    expect(page.locator("#inactive")).to_have_text("empty")
    expect(page.locator("#seeded")).to_have_text("empty")
    expect(page.get_by_role("button", name="Project A", exact=False)).to_have_count(0)
    check("Switching server immediately removes active and inactive data from A")

    # Resolve the previous request after the switch while B is still loading.
    assert any(server == "server-a" and endpoint == "health" for server, endpoint, _route in held)
    for server, endpoint, route in held.copy():
        if server == "server-a":
            with page.expect_response(lambda response: "/server-a/health" in response.url):
                fulfill_json(route, {"status": "A-late"})
            held.remove((server, endpoint, route))
    expect(page.locator("#health")).to_have_text("empty")
    check("A late response from the previous server cannot restore its data")
    for server, endpoint, route in held.copy():
        if server == "server-b":
            fulfill_json(route, {"status": "B-current"} if endpoint == "health" else [{"id": "news-id", "title": "Project B", "status": "ready"}])
            held.remove((server, endpoint, route))
    hold_b_data = False
    expect(page.locator("#health")).to_have_text("B-current")
    expect(page.locator("#seeded")).to_have_text("B-current")
    expect(page.get_by_role("button", name="Project B", exact=False)).to_be_visible()
    check("Observed queries refetch against B without remounting the screen")
    page.get_by_role("button", name="Project B", exact=False).click()

    hold_download = True
    download = page.get_by_role("button", name="Tải prompt pack UTF-8", exact=True)
    download.click()
    pending = page.get_by_role("button", name="Đang tải prompt pack…", exact=True)
    expect(pending).to_be_disabled()
    check("Prompt download stays disabled while its request is pending")
    page.evaluate("window.workflowFixture.holdSave = true")
    for server, endpoint, route in held.copy():
        if endpoint.endswith("/prompt-pack"):
            route.fulfill(status=200, content_type="text/plain; charset=utf-8", body=prompt_text.encode("utf-8"),
                          headers={"Content-Disposition": "attachment; filename*=UTF-8''prompt-tieng-viet.txt"})
            held.remove((server, endpoint, route))
    hold_download = False
    expect(pending).to_be_disabled()
    page.wait_for_function("window.workflowFixture.finishSave.toString() !== '() => {}'")
    page.evaluate("window.workflowFixture.finishSave()")
    expect(download).to_be_enabled()
    saved = page.evaluate("window.workflowFixture.savedFiles")
    check("Downloaded filename, UTF-8 content and file filter reach the save adapter",
          saved == [{"filename": "prompt-tieng-viet.txt", "text": prompt_text, "extensions": ["txt"]}])
    check("The download targets the current server and selected project", ("server-b", "news-video/projects/news-id/prompt-pack") in requests)

    page.evaluate("window.workflowFixture.holdSave = false; window.workflowFixture.failSave = true")
    download.click()
    expect(page.get_by_text("Không tải được prompt pack: Disk unavailable", exact=True)).to_be_visible()
    expect(download).to_be_enabled()
    check("Save errors are visible and allow retry")
    page.evaluate("window.workflowFixture.failSave = false")
    fail_download = True
    download.click()
    expect(page.get_by_text("Không tải được prompt pack: Pack unavailable", exact=True)).to_be_visible()
    check("HTTP download errors are visible without invoking the save adapter", len(page.evaluate("window.workflowFixture.savedFiles")) == 1)
    fail_download = False
    download.click()
    expect(download).to_be_enabled()
    expect(page.get_by_text("Không tải được prompt pack: Pack unavailable", exact=True)).to_have_count(0)
    check("Retry clears the previous error and saves successfully", len(page.evaluate("window.workflowFixture.savedFiles")) == 2)
    check("The workflow has no unhandled browser errors", not errors)
    browser.close()

print(f"{len(checks)} workflow browser checks passed")
for name in checks:
    print(f"  PASS {name}")
