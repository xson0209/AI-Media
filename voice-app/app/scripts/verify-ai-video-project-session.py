"""Browser regression checks through the actual project-session hook and router."""

import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import expect, sync_playwright

base = sys.argv[1]
storage_key = "voicebox.aiVideoDraft.v1"
checks = []


def check(name, condition):
    assert condition, name
    checks.append(name)


def draft(title="Incoming draft", **values):
    return {
        "source": "video-inspiration",
        "createdAt": "2026-10-02T00:00:00.000Z",
        "title": title,
        "targetLanguage": "vi",
        "sources": [{"block_type": "idea", "content": "Source material"}],
        **values,
    }


def saved(page):
    return page.evaluate("key => sessionStorage.getItem(key)", storage_key)


def set_raw(page, value):
    page.evaluate("([key, value]) => sessionStorage.setItem(key, value)", [storage_key, value])


def selected(page, value):
    expect(page.locator("#selected")).to_have_text(value)


def browser_executable(pw):
    configured = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    if configured:
        return configured
    default = Path(pw.chromium.executable_path)
    if default.exists():
        return str(default)
    cache = Path(os.environ["LOCALAPPDATA"]) / "ms-playwright" if os.name == "nt" else Path.home() / ".cache/ms-playwright"
    choices = sorted(cache.glob("chromium-*/chrome-win*/chrome.exe"))
    choices += sorted(cache.glob("chromium-*/chrome-linux*/chrome"))
    if choices:
        return str(choices[-1])
    return None


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, executable_path=browser_executable(pw))
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    page.goto(base + "/ai-video?projectId=A&context=handoff")
    selected(page, "A")
    page.get_by_role("button", name="Select B").click()
    selected(page, "B")
    check("Picker selection updates the project URL", parse_qs(urlparse(page.url).query).get("projectId") == ["B"])
    check("Selection keeps unrelated search values", parse_qs(urlparse(page.url).query).get("context") == ["handoff"])
    page.get_by_role("button", name="Refresh workspace").click()
    selected(page, "B")
    checks.append("Rerender cannot restore the original handoff project")

    page.go_back()
    selected(page, "A")
    page.go_forward()
    selected(page, "B")
    checks.append("Back and Forward restore the corresponding project")
    page.get_by_role("button", name="Created C").click()
    selected(page, "C")
    page.reload()
    selected(page, "C")
    checks.append("A newly created project survives reload")
    page.get_by_role("button", name="Clear selection").click()
    selected(page, "none")
    check("Clearing selection removes projectId", "projectId" not in parse_qs(urlparse(page.url).query))

    page.goto(base + "/ai-video?projectId=outside-the-list")
    selected(page, "outside-the-list")
    checks.append("Deep links remain available for fetching even outside the project list")

    first = draft()
    raw = json.dumps(first)
    set_raw(page, raw)
    page.goto(base + "/ai-video?draft=video-inspiration&projectId=A")
    selected(page, "none")
    expect(page.get_by_role("textbox", name="Draft title")).to_have_value(first["title"])
    expect(page.locator("#language")).to_have_text("vi")
    check("Receiving a draft retains the original material", saved(page) == raw)
    hydration_count = page.locator("#hydrations").text_content()
    page.get_by_role("textbox", name="Draft title").fill("Edited form title")
    page.get_by_role("button", name="Refresh workspace").click()
    expect(page.get_by_role("textbox", name="Draft title")).to_have_value("Edited form title")
    check("Draft is hydrated once per receipt", page.locator("#hydrations").text_content() == hydration_count)
    page.reload()
    expect(page.get_by_role("textbox", name="Draft title")).to_have_value(first["title"])
    check("Reload recovers the incoming handoff material", saved(page) == raw)
    page.get_by_role("button", name="Created C").click()
    selected(page, "C")
    page.wait_for_function("key => sessionStorage.getItem(key) === null", arg=storage_key)
    check("Successful selection consumes the received draft", saved(page) is None)
    check("Project selection removes the draft intent", "draft" not in parse_qs(urlparse(page.url).query))

    page.evaluate("value => window.sessionFixture.openDraft(value)", draft("First visit"))
    expect(page.get_by_role("textbox", name="Draft title")).to_have_value("First visit")
    page.evaluate("value => window.sessionFixture.openDraft(value)", draft("Next handoff"))
    expect(page.get_by_role("textbox", name="Draft title")).to_have_value("Next handoff")
    checks.append("A new handoff is received even at the same draft URL")

    replacement = draft("Concurrent handoff")
    page.evaluate("value => window.sessionFixture.replaceDraftAndSelect(value, 'B')", replacement)
    selected(page, "B")
    check("Selection does not delete a newer handoff", json.loads(saved(page))["title"] == replacement["title"])

    legacy = draft("Legacy draft")
    del legacy["targetLanguage"]
    set_raw(page, json.dumps(legacy))
    page.goto(base + "/ai-video?draft=video-inspiration")
    expect(page.get_by_role("textbox", name="Draft title")).to_have_value("Legacy draft")
    expect(page.locator("#language")).to_have_text("en")
    checks.append("Legacy drafts keep current output configuration")

    for bad in ["{broken", json.dumps(draft(sources=[{"content": 12}])), json.dumps(draft(title=12))]:
        set_raw(page, bad)
        page.reload()
        expect(page.locator("#notice")).to_contain_text("không hợp lệ")
        check("Invalid drafts remain recoverable without crashing", saved(page) == bad)

    page.evaluate("key => sessionStorage.removeItem(key)", storage_key)
    page.reload()
    expect(page.locator("#notice")).to_contain_text("Không còn bản nháp")
    checks.append("Missing draft links explain how to recover")

    blocked = browser.new_page()
    blocked.on("pageerror", lambda error: errors.append(str(error)))
    blocked.add_init_script("Object.defineProperty(window, 'sessionStorage', { get() { throw new Error('storage blocked'); } });")
    blocked.goto(base + "/ai-video?draft=video-inspiration")
    expect(blocked.locator("#notice")).to_contain_text("Chưa đọc được bản nháp")
    blocked.get_by_role("button", name="Select B").click()
    selected(blocked, "B")
    checks.append("Blocked storage does not prevent selecting a project")
    check("No browser runtime errors", not errors)
    browser.close()

print(f"AI Video project-session verifier passed: {len(checks)} browser behavior checks.")
