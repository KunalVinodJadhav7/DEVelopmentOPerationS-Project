from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ARTIFACT_DIR = PROJECT_ROOT / "selenium_tests" / "artifacts"
SCREENSHOT_DIR = ARTIFACT_DIR / "screenshots"
LOG_DIR = ARTIFACT_DIR / "logs"
PAGE_DIR = ARTIFACT_DIR / "pages"

for directory in (SCREENSHOT_DIR, LOG_DIR, PAGE_DIR):
    directory.mkdir(parents=True, exist_ok=True)


BASE_URL = os.getenv("SELENIUM_BASE_URL","http://localhost/dashboard",)
HEADLESS = os.getenv("SELENIUM_HEADLESS", "false").lower() == "true"


def _safe_name(value: str) -> str:
    """Convert a pytest test name into a Windows-safe filename."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


@pytest.fixture
def base_url() -> str:
    return BASE_URL


@pytest.fixture
def driver(request):
    """Create and clean up a Chrome WebDriver for each test."""

    options = Options()

    if HEADLESS:
        options.add_argument("--headless=new")

    options.add_argument("--window-size=1440,1000")
    options.add_argument("--disable-notifications")
    options.add_argument("--start-maximized")

    # Capture browser console messages where the browser exposes them.
    options.set_capability(
        "goog:loggingPrefs",
        {
            "browser": "ALL",
        },
    )

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(0)

    yield driver

    test_name = _safe_name(request.node.nodeid)
    report = getattr(request.node, "rep_call", None)

    try:
        # Always save the current HTML page for evidence.
        page_file = PAGE_DIR / f"{test_name}.html"
        page_file.write_text(
            driver.page_source,
            encoding="utf-8",
        )

        # Capture browser console log.
        try:
            browser_logs = driver.get_log("browser")
        except Exception:
            browser_logs = []

        log_file = LOG_DIR / f"{test_name}.log"

        with log_file.open("w", encoding="utf-8") as log:
            log.write(f"Test: {request.node.nodeid}\n")
            log.write(f"URL: {driver.current_url}\n")
            log.write(f"Title: {driver.title}\n")
            log.write("\nBrowser console:\n")

            if browser_logs:
                for entry in browser_logs:
                    log.write(f"{entry}\n")
            else:
                log.write("No browser console entries captured.\n")

        # Screenshots are especially useful when a test fails.
        if report and report.failed:
            screenshot_file = SCREENSHOT_DIR / f"{test_name}.png"
            driver.save_screenshot(str(screenshot_file))

    finally:
        driver.quit()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Make the test result available to the WebDriver fixture."""

    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        item.rep_call = report