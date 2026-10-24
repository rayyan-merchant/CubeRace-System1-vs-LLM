"""Drive only an isolated, credential-free localhost app; retain real screenshots."""
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import httpx
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import uvicorn  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.main import create_app  # noqa: E402


def main():
    evidence = ROOT / "docs/evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory() as tmp:
        # Dummy credentials + an exhaustive MockTransport: live UI paths never reach OpenRouter.
        inference = []
        def fixture(request):
            inference.append(json.loads(request.content))
            return httpx.Response(400, json={"error": {"message": "offline route fixture"},
                                            "usage": {"cost": 0.0001}})
        with (evidence / "browser-server.log").open("w", encoding="utf-8") as log:
            log.write("Isolated credential-free in-process Uvicorn test server\n")
            server = uvicorn.Server(uvicorn.Config(
                create_app(Settings(database=str(Path(tmp) / "browser.db"), key="offline-fixture",
                                    allow_live=True, mock_mode=False), httpx.MockTransport(fixture)),
                host="127.0.0.1", port=port, log_level="warning"))
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{port}"
                for _ in range(100):
                    try:
                        with urlopen(base + "/api/health", timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError("Browser test server did not start")
                errors, console_errors, checks = [], [], []
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(channel="msedge" if os.name == "nt" else None,
                                                 headless=True)
                    page = browser.new_page(viewport={"width": 1366, "height": 768},
                                            reduced_motion="reduce")
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
                    page.goto(base)
                    page.locator("#scramble").filter(has_text=" ").wait_for()
                    assert page.locator(".race-card").count() == 4
                    assert page.locator("svg polygon").count() == 108
                    assert "SET STUDENT_NAME" in page.locator(".identity").inner_text()
                    assert page.locator("#mode").input_value() == "simulated"
                    assert inference == []
                    for width, height in ((1366, 768), (1920, 1080)):
                        page.set_viewport_size({"width": width, "height": height})
                        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                        page.screenshot(path=str(evidence / f"arena-{width}x{height}.png"), full_page=True)
                        bounds = page.locator("#cards").bounding_box()
                        assert bounds["y"] + bounds["height"] <= height, "Arena exceeds desktop viewport"
                        checks.append({"viewport": [width, height], "horizontal_overflow": False,
                                       "arena_bottom_px": bounds["y"] + bounds["height"]})
                    page.set_viewport_size({"width": 1366, "height": 768})
                    page.locator("#start").click()
                    expect(page.locator("#status-0")).not_to_have_text("READY TO RACE")
                    page.screenshot(path=str(evidence / "race-in-progress.png"), full_page=True)
                    expect(page.locator("#start")).to_be_enabled(timeout=30000)
                    assert page.locator("#status-0").inner_text() == "SOLVED"
                    assert page.locator("#status-2").inner_text() == "MOVE LIMIT"
                    assert page.locator("#moves-2").inner_text().replace("\n", "") == "30/30"
                    page.screenshot(path=str(evidence / "race-completed.png"), full_page=True)
                    page.locator("#speed").select_option("100")
                    page.locator('[data-tab="analysis"]').click()
                    expect(page.locator("#stats-rows tr")).to_have_count(4)
                    assert "0/0 solved" in page.locator("#stats-rows").inner_text()
                    page.locator("#suite").click()
                    expect(page.locator("#start")).to_be_enabled(timeout=45000)
                    page.locator('[data-tab="analysis"]').click()
                    page.locator("#stats-mode").select_option("simulated")
                    expect(page.locator("#summary")).to_contain_text("20")
                    with page.expect_download() as downloaded:
                        page.locator("#history a").filter(has_text="JSON").first.click()
                    downloaded.value.save_as(str(Path(tmp) / "download.json"))
                    assert json.loads((Path(tmp) / "download.json").read_text())["mode"] == "simulated"
                    page.locator("body").press("Control+Home")
                    page.screenshot(path=str(evidence / "analysis-1366x768.png"), full_page=True)
                    # Replay fetch is asynchronous; an already-enabled Start is not proof
                    # that replay finished. Its final config read happens after playback.
                    with page.expect_response(lambda r: r.url.endswith("/api/config")):
                        page.locator(".replay").first.click()
                    expect(page.locator("#start")).to_be_enabled(timeout=30000)
                    page.locator('[data-tab="analysis"]').click()
                    page.locator('[data-tab="presentation"]').click()
                    page.locator("#slide-provenance").filter(has_text="SIMULATED").wait_for()
                    expect(page.locator("#presentation")).to_be_visible()
                    assert page.locator(".identity").is_visible()
                    page.locator("body").press("Control+Home")
                    page.screenshot(path=str(evidence / "results-slide.png"), full_page=True)
                    page.locator('[data-tab="arena"]').click()
                    page.locator("#speed").select_option("1")
                    page.locator("#start").click()
                    page.locator("#abort").click()
                    expect(page.locator("#start")).to_be_enabled(timeout=10000)
                    assert any(s in page.locator("#progress").inner_text() for s in ("ABORTED", "COMPLETED"))
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    page.screenshot(path=str(evidence / "arena-mobile.png"), full_page=True)
                    assert inference == []  # All existing rendering, exports and replay were free.
                    page.set_viewport_size({"width": 1366, "height": 768})
                    page.locator("#mode").select_option("live")
                    page.locator("#start").click()
                    expect(page.locator("#notice")).to_contain_text("paid-call authorization")
                    assert inference == []
                    page.locator("#call-cap").fill("4")
                    page.locator("#paid-confirm").check()
                    page.locator("#start").click()
                    expect(page.locator("#start")).to_be_enabled(timeout=30000)
                    assert len(inference) == 4
                    assert not page.locator("#paid-confirm").is_checked()
                    expect(page.locator("#persistent-billing")).to_contain_text("Known $0.000400")
                    page.locator('[data-tab="analysis"]').click()
                    expect(page.locator(".replay").first).to_be_enabled()
                    with page.expect_response(lambda r: r.url.endswith("/api/config")):
                        page.locator(".replay").first.click()
                    expect(page.locator("#start")).to_be_enabled(timeout=30000)
                    page.reload()
                    expect(page.locator("#mode")).to_have_value("simulated")
                    page.locator('[data-tab="analysis"]').click()
                    page.locator("#refresh").click()
                    assert len(inference) == 4
                    browser.close()
                report = {"mode": "simulated", "source": "actual headless browser on isolated localhost",
                    "checks": checks, "flows": ["initial arena", "race", "30 cap", "five-puzzle suite",
                        "analysis", "raw download", "replay", "presentation identity", "abort", "mobile",
                        "paid consent with offline transport", "billing display", "live-mode replay without inference"],
                    "offline_fixture_inference_requests": len(inference),
                    "real_openrouter_inference_requests": 0,
                    "page_errors": errors, "console_errors": console_errors}
                (evidence / "browser-verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                assert not errors and not console_errors, report
                print("PASS: browser race, suite, analysis, slide, abort and responsive checks; no console errors.")
            finally:
                server.should_exit = True
                thread.join(timeout=15)
                assert not thread.is_alive(), "Test server did not shut down"


if __name__ == "__main__":
    main()
