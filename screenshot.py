"""Capture an above-the-fold screenshot of a URL using Playwright."""


def capture_screenshot(url: str, output_path: str, timeout: int = 30000) -> bool:
    """
    Navigate to url and save a 1280×800 viewport screenshot to output_path.
    Returns True on success, False on any failure (missing dep, timeout, etc.).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            page.wait_for_timeout(2000)
            page.screenshot(path=output_path, full_page=False)
            browser.close()
        return True
    except Exception:
        return False
