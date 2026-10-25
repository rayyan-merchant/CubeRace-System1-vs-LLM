"""Drive only an isolated, credential-free localhost app; retain real screenshots."""
import json
import os
import re
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
        fixture_mode = {"value": "error"}
        def fixture(request):
            body = json.loads(request.content)
            inference.append(body)
            if fixture_mode["value"] == "valid":
                effective = {"typesafe/jev-1.13": "typesafe/jev-1.13-20260917",
                             "openai/gpt-6-luna-decisions": "openai/gpt-6-luna-decisions-20261006"}.get(body["model"], body["model"])
                result = {"model": effective, "usage": {"input_tokens": 12, "output_tokens": 2, "cost": 0.0001}}
                if "messages" in body:
                    assert body["max_tokens"] == 1024 and body["reasoning"] == {"effort": "low"}
                    result["choices"] = [{"message": {"content": '{"move":"R"}'}, "finish_reason": "stop"}]
                else:
                    result["answers"] = {"next_move": {"type": "choice", "choice": "R"}}
                return httpx.Response(200, json=result)
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
                identity = "Rayyan Merchant · 23K-0073"
                # Mark test-only live-mode captures without changing application UI or evidence.
                fixture_style = """body::after{content:'OFFLINE UI FIXTURE · No OpenRouter calls';
                    position:fixed;bottom:8px;right:12px;z-index:1000;padding:6px 10px;
                    background:#fff2cb;color:#614b13;border:1px solid #cfb45f;
                    border-radius:4px;font:600 12px Arial,sans-serif}"""
                def check_identity(page):
                    expect(page.locator("#identity")).to_have_text(identity)
                    bounds = page.locator(".identity").bounding_box()
                    assert bounds and bounds["y"] == 0 and bounds["height"] > 0

                def capture_views(page, prefix=""):
                    for width, height in ((1366, 768), (1920, 1080)):
                        page.set_viewport_size({"width": width, "height": height})
                        for tab in ("analysis", "presentation"):
                            page.locator(f'[data-tab="{tab}"]').click()
                            expect(page.locator(f"#{tab}")).to_be_visible()
                            page.locator("body").press("Control+Home")
                            check_identity(page)
                            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                            table = page.locator(f"#{tab} .table-wrap").first
                            assert table.evaluate("el => el.scrollWidth <= el.clientWidth"), "Desktop table clipped"
                            assert page.locator(f"#{tab} tbody tr").count() == 4
                            assert page.locator("#answers li" if tab == "analysis" else "#slide-answers li").count() == 5
                            for label in ("Jev", "Luna", "Clef", "Claude Opus 5.5"):
                                expect(table).to_contain_text(label)
                            page.screenshot(path=str(evidence / f"{prefix}{tab}-{width}x{height}.png"))
                            if tab == "analysis":
                                page.screenshot(path=str(evidence / f"{prefix}{tab}-full-{width}x{height}.png"),
                                                full_page=True)
                                page.locator("body").press("Control+End")
                                check_identity(page)  # Sticky identity survives dashboard scrolling.
                            else:
                                expect(page.locator("#live-plan")).to_be_hidden()
                                bounds = page.locator(".slide").bounding_box()
                                assert bounds["y"] + bounds["height"] <= height, "Results exceed viewport"
                                page.locator("#fullscreen").click()
                                assert page.evaluate("document.fullscreenElement === document.documentElement")
                                check_identity(page)
                                page.screenshot(path=str(evidence / f"{prefix}fullscreen-{width}x{height}.png"))
                                page.locator("#fullscreen").click()
                        checks.append({"views": ["analysis", "presentation", "fullscreen"],
                                       "viewport": [width, height], "identity_visible": True,
                                       "desktop_tables_unclipped": True, "prefix": prefix})

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
                    check_identity(page)
                    expect(page.locator("h1")).to_have_text("Rubik's Cube Benchmark")
                    expect(page.locator("#notice")).to_be_hidden()
                    assert page.locator("#mode").input_value() == "simulated"
                    assert inference == []
                    # Scramble controls and cube nets remain interactive without inference.
                    page.locator("#tier").select_option("warmup")
                    page.wait_for_load_state("networkidle")
                    page.locator("#seed").fill("3000")
                    page.locator("#seed").press("Tab")
                    page.wait_for_load_state("networkidle")
                    page.locator("#generate").click()
                    page.wait_for_load_state("networkidle")
                    expect(page.locator("#seed")).to_have_value("3001")
                    page.locator("#tier").select_option("primary")
                    page.wait_for_load_state("networkidle")
                    page.locator(".card-net summary").first.click()
                    expect(page.locator(".card-net").first).to_have_attribute("open", "")
                    expect(page.locator("#net-0")).to_be_visible()
                    assert page.locator("#net-0 .net span").count() == 54
                    page.locator(".card-net summary").first.click()
                    expect(page.locator(".card-net").first).not_to_have_attribute("open", "")
                    for width, height in ((1366, 768), (1920, 1080)):
                        page.set_viewport_size({"width": width, "height": height})
                        check_identity(page)
                        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                        page.screenshot(path=str(evidence / f"arena-{width}x{height}.png"), full_page=True)
                        bounds = page.locator("#cards").bounding_box()
                        assert bounds["y"] + bounds["height"] <= height, "Arena exceeds desktop viewport"
                        checks.append({"viewport": [width, height], "horizontal_overflow": False,
                                       "arena_bottom_px": bounds["y"] + bounds["height"]})
                    page.set_viewport_size({"width": 1366, "height": 768})
                    page.locator("#start").click()
                    expect(page.locator("#status-0")).not_to_have_text("READY")
                    expect(page.locator("#start")).to_be_disabled()
                    expect(page.locator("#abort")).to_be_enabled()
                    page.screenshot(path=str(evidence / "race-in-progress.png"), full_page=True)
                    expect(page.locator("#start")).to_be_enabled(timeout=30000)
                    assert page.locator("#status-0").inner_text() == "SOLVED"
                    assert page.locator("#status-2").inner_text() == "MOVE LIMIT"
                    assert page.locator("#moves-2").inner_text().replace("\n", "") == "30/30"
                    bounds = page.locator("#cards").bounding_box()
                    assert bounds["y"] + bounds["height"] <= 768, "Completed cards exceed laptop viewport"
                    page.screenshot(path=str(evidence / "race-completed.png"), full_page=True)
                    page.locator("#speed").select_option("100")
                    page.locator('[data-tab="analysis"]').click()
                    expect(page.locator("#stats-rows tr")).to_have_count(4)
                    assert "0/0 solved" in page.locator("#stats-rows").inner_text()
                    expect(page.locator("#stats-rows")).not_to_contain_text("N/A%")
                    expect(page.locator("#slide-provenance")).to_have_text("LIVE · Primary Benchmark · 0 Puzzles")
                    page.screenshot(path=str(evidence / "analysis-empty-1366x768.png"))
                    page.locator("#stats-tier").select_option("warmup")
                    expect(page.locator("#table-caption")).to_contain_text("Warm-up")
                    page.locator("#stats-tier").select_option("primary")
                    page.locator("#suite").click()
                    expect(page.locator("#start")).to_be_enabled(timeout=45000)
                    page.locator('[data-tab="analysis"]').click()
                    page.locator("#stats-mode").select_option("simulated")
                    expect(page.locator("#summary")).to_contain_text("20")
                    expect(page.locator("#slide-provenance")).to_have_text("SIMULATED · Primary Benchmark · 5 Puzzles")
                    capture_views(page)
                    page.locator('[data-tab="analysis"]').click()
                    with page.expect_download() as downloaded:
                        page.locator("#history a").filter(has_text="JSON").first.click()
                    downloaded.value.save_as(str(Path(tmp) / "download.json"))
                    assert json.loads((Path(tmp) / "download.json").read_text())["mode"] == "simulated"
                    page.locator("body").press("Control+Home")
                    # Replay fetch is asynchronous; an already-enabled Start is not proof
                    # that replay finished. Its final config read happens after playback.
                    with page.expect_response(lambda r: r.url.endswith("/api/config")):
                        page.locator(".replay").first.click()
                    expect(page.locator("#start")).to_be_enabled(timeout=30000)
                    page.locator('[data-tab="analysis"]').click()
                    page.locator('[data-tab="presentation"]').click()
                    page.locator("#slide-provenance").filter(has_text="SIMULATED").wait_for()
                    expect(page.locator("#presentation")).to_be_visible()
                    check_identity(page)
                    page.locator("body").press("Control+Home")
                    page.screenshot(path=str(evidence / "results-slide.png"), full_page=True)
                    page.locator('[data-tab="arena"]').click()
                    page.locator("#speed").select_option("1")
                    page.locator("#start").click()
                    page.locator("#abort").click()
                    expect(page.locator("#start")).to_be_enabled(timeout=10000)
                    expect(page.locator("#progress")).to_have_text(re.compile("ABORTED|COMPLETED"))
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
                    expect(page.locator("#status-0")).to_have_text("UNAVAILABLE")
                    expect(page.locator("#error-0")).not_to_be_empty()
                    # Same-origin intercepted CSS respects the application's CSP. Do not
                    # bypass security or change production styles for test evidence labels.
                    page.route(base + "/static/browser-fixture.css", lambda route: route.fulfill(
                        status=200, content_type="text/css", body=fixture_style))
                    page.add_style_tag(url=base + "/static/browser-fixture.css")
                    assert "OFFLINE UI FIXTURE" in page.locator("body").evaluate(
                        "el => getComputedStyle(el, '::after').content")
                    page.screenshot(path=str(evidence / "live-error-offline-1366x768.png"),
                                    full_page=True)
                    # A live-mode suite is intercepted too: permanent errors make four
                    # requests, remaining puzzles are NOT_RUN. No fabricated successful data.
                    page.locator('[data-tab="analysis"]').click()
                    page.locator("#call-cap").fill("4")
                    page.locator("#paid-confirm").check()
                    page.locator("#suite").click()
                    expect(page.locator("#start")).to_be_enabled(timeout=30000)
                    assert len(inference) == 8
                    page.locator('[data-tab="analysis"]').click()
                    page.locator("#stats-mode").select_option("live")
                    expect(page.locator("#stats-rows")).to_contain_text("NOT_RUN: 4")
                    expect(page.locator("#slide-provenance")).to_have_text("LIVE · Primary Benchmark · 5 Puzzles")
                    capture_views(page, "offline-live-errors-")
                    page.set_viewport_size({"width": 1366, "height": 768})
                    page.locator('[data-tab="analysis"]').click()
                    expect(page.locator(".replay").first).to_be_enabled()
                    with page.expect_response(lambda r: r.url.endswith("/api/config")):
                        page.locator(".replay").first.click()
                    expect(page.locator("#start")).to_be_enabled(timeout=30000)
                    page.reload()
                    expect(page.locator("#mode")).to_have_value("simulated")
                    page.locator('[data-tab="analysis"]').click()
                    page.locator("#refresh").click()
                    assert len(inference) == 8
                    # The same browser Start/stream/replay path now accepts dated IDs.
                    # Constant R is deliberately a test fixture, not a solving policy.
                    fixture_mode["value"] = "valid"
                    page.locator('[data-tab="arena"]').click()
                    page.locator("#mode").select_option("live")
                    page.locator("#speed").select_option("100")
                    page.locator("#call-cap").fill("120")
                    page.locator("#paid-confirm").check()
                    page.locator("#start").click()
                    expect(page.locator("#start")).to_be_enabled(timeout=45000)
                    for i in range(4):
                        expect(page.locator(f"#status-{i}")).to_have_text("MOVE LIMIT")
                        expect(page.locator(f"#moves-{i}")).to_have_text("30/30")
                    assert len(inference) == 128
                    page.add_style_tag(url=base + "/static/browser-fixture.css")
                    page.screenshot(path=str(evidence / "offline-live-dated-ids-completed.png"), full_page=True)
                    page.locator('[data-tab="analysis"]').click()
                    with page.expect_response(lambda r: r.url.endswith("/api/config")):
                        page.locator(".replay").first.click()
                    expect(page.locator("#start")).to_be_enabled(timeout=30000)
                    assert len(inference) == 128
                    browser.close()
                report = {"mode": "simulated", "source": "actual headless browser on isolated localhost",
                    "checks": checks, "flows": ["initial arena", "race", "30 cap", "five-puzzle suite",
                        "analysis", "raw download", "replay", "all-view sticky identity", "fullscreen identity",
                        "empty results", "dynamic slide context", "four assigned names", "unclipped desktop tables",
                        "scramble controls", "six-face expansion", "running controls", "abort", "mobile",
                        "paid consent with offline transport", "API failure states", "NOT_RUN denominators",
                        "billing display", "live-mode replay without inference",
                        "dated IDs through browser Start", "four independent 30-action trials",
                        "completed live fixture replay without inference"],
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
