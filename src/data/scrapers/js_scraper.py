"""
js_scraper.py — Playwright-based JS renderer for LAGEMA JARG74
===============================================================
Fetches fully rendered HTML from JavaScript-heavy sports sites.
Falls back gracefully to requests if Playwright is not available.

Playwright is required: pip install playwright && playwright install chromium
"""
from typing import Optional
import re

# Try to import playwright — will fail gracefully if not installed
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass


def get_html_with_js(url: str, wait_for: str = "networkidle",
                     timeout_ms: int = 15000,
                     extra_wait_ms: int = 2000,
                     block_images: bool = True) -> Optional[str]:
    """
    Fetches fully JS-rendered HTML from a URL using Playwright Chromium.

    Args:
        url:           Target page URL
        wait_for:      Playwright wait state: "networkidle" | "domcontentloaded" | "load"
        timeout_ms:    Max time to wait for page load (ms)
        extra_wait_ms: Additional wait after load for dynamic content to settle
        block_images:  Block image/media downloads to speed up scraping

    Returns:
        Full rendered HTML string, or None if failed.
    """
    if not PLAYWRIGHT_AVAILABLE:
        print("    [JS] Playwright not available — run: pip install playwright && playwright install chromium")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ]
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                locale="es-ES",
                viewport={"width": 1280, "height": 800},
            )

            page = context.new_page()

            # Block images/fonts/media to speed up scraping
            if block_images:
                page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,mp4}", lambda r: r.abort())

            # Navigate with timeout
            try:
                page.goto(url, wait_until=wait_for, timeout=timeout_ms)
            except PlaywrightTimeout:
                # Partial load is often enough
                print(f"    [JS] Timeout on {url} — using partial content")

            # Small extra wait for dynamic data to render
            if extra_wait_ms > 0:
                page.wait_for_timeout(extra_wait_ms)

            html = page.content()
            browser.close()
            return html

    except Exception as e:
        print(f"    [JS] Playwright error for {url}: {e}")
        return None


def get_html_with_selector(url: str, wait_selector: str,
                            timeout_ms: int = 20000) -> Optional[str]:
    """
    Waits for a specific CSS selector to appear before returning HTML.
    More reliable than time-based waits for dynamic content.

    Args:
        url:            Target URL
        wait_selector:  CSS selector to wait for (e.g. '.lineup-player')
        timeout_ms:     Overall timeout in ms

    Returns:
        Rendered HTML or None.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36"
                ),
                locale="es-ES",
            )
            page = context.new_page()
            page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda r: r.abort())

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_selector(wait_selector, timeout=timeout_ms)
            except PlaywrightTimeout:
                print(f"    [JS] Selector '{wait_selector}' not found on {url}")

            html = page.content()
            browser.close()
            return html

    except Exception as e:
        print(f"    [JS] Playwright selector error: {e}")
        return None


def is_available() -> bool:
    """Returns True if Playwright is installed and Chromium is available."""
    return PLAYWRIGHT_AVAILABLE
