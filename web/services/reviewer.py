from __future__ import annotations

import os
import hashlib
import hmac
import time
from threading import Lock

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
_review_lock = Lock()


def _visit_reports() -> None:
    site_url = os.getenv("BFC_URL", "http://bfc:3000").rstrip("/")
    options = Options()
    options.binary_location = "/usr/bin/chromium"
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-extensions")
    options.add_argument("--window-size=1280,900")
    driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=options)
    try:
        driver.set_page_load_timeout(12)
        secret = os.environ["LAB_REVIEW_SECRET"]
        driver.execute_cdp_cmd("Network.setCookie", {
            "name": "relay_staff_review",
            "value": hmac.new(secret.encode(), b"relay-staff-review", hashlib.sha256).hexdigest(),
            "url": f"{site_url}/returns",
            "path": "/",
            "httpOnly": True,
            "sameSite": "Strict",
        })
        driver.get(f"{site_url}/returns?staff=1")
        WebDriverWait(driver, 10).until(ec.text_to_be_present_in_element((By.CLASS_NAME, "workflow-result-head"), "Staff print view"))
        time.sleep(3)
    finally:
        driver.quit()


@app.get("/health")
def health():
    return {"status": "ready"}


@app.post("/review")
def review():
    if not _review_lock.acquire(blocking=False):
        return JSONResponse({"error": "A staff review is already in progress."}, status_code=429)
    try:
        _visit_reports()
        return {"status": "completed"}
    except Exception:
        return JSONResponse({"error": "The staff reviewer could not open the reports."}, status_code=502)
    finally:
        _review_lock.release()
