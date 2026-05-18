"""Lightweight browser automation wrapper using Playwright."""
import os
import datetime
import re


def _save_dir():
    d = os.path.join(os.path.expanduser("~"), ".claudy", "browser")
    os.makedirs(d, exist_ok=True)
    return d


def fetch(url, screenshot=True, extract_text=True, wait_ms=2000):
    """
    Open URL headless, return dict with title, text, screenshot path.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return {"error": f"Playwright no disponible: {e}"}
    out = {"url": url, "title": "", "text": "", "screenshot": ""}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent="Mozilla/5.0 Claudy/1.0")
            page = ctx.new_page()
            page.set_default_timeout(30000)
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(wait_ms)
            out["title"] = page.title() or ""
            if extract_text:
                txt = page.evaluate("() => document.body ? document.body.innerText : ''")
                txt = re.sub(r"\n{3,}", "\n\n", (txt or "").strip())
                if len(txt) > 8000:
                    txt = txt[:8000] + "\n...[truncado]"
                out["text"] = txt
            if screenshot:
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(_save_dir(), f"{ts}.png")
                page.screenshot(path=path, full_page=False)
                out["screenshot"] = path
            browser.close()
    except Exception as e:
        out["error"] = str(e)
    return out


def extract(url, selector):
    """Extract text from elements matching CSS selector."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return {"error": f"Playwright no disponible: {e}"}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_context().new_page()
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            items = page.locator(selector).all_inner_texts()
            browser.close()
            return {"url": url, "selector": selector, "items": items[:50]}
    except Exception as e:
        return {"error": str(e)}
