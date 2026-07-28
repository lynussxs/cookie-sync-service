# cookie_sync_service.py
import asyncio
import os
import logging
from flask import Flask, jsonify
from playwright.async_api import async_playwright
import dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
dotenv.load_dotenv()

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
COOKIE_FILE = os.getenv("COOKIE_FILE", "/app/cookies.txt")


async def get_cookies() -> dict:
    """Lấy cookie YouTube bằng Playwright."""
    logger.info("🚀 Bắt đầu lấy cookie")
    logger.info(f"📧 EMAIL: {EMAIL}")
    logger.info(f"📁 COOKIE_FILE: {COOKIE_FILE}")
    
    browser = None
    page = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
            page = await context.new_page()

            if not EMAIL or not PASSWORD:
                return {"status": "error", "message": "Thiếu EMAIL hoặc PASSWORD trong env vars"}

            logger.info("📤 Đang truy cập YouTube...")
            await page.goto("https://www.youtube.com/", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(1500)

            # Nút "Sign in"
            signed_in_button_found = False
            for sel in ('text="Sign in"', 'a[aria-label="Sign in"]', 'a[href*="accounts.google.com"]'):
                try:
                    await page.click(sel, timeout=5000)
                    signed_in_button_found = True
                    logger.info(f"✅ Đã click Sign in với selector: {sel}")
                    break
                except Exception:
                    continue
            if not signed_in_button_found:
                logger.warning("⚠️ Không tìm thấy nút Sign in, chuyển sang accounts.google.com")
                await page.goto("https://accounts.google.com/login", timeout=30000)
            await page.wait_for_timeout(1500)

            # Nhập email - nhiều selector
            logger.info("📧 Đang nhập email...")
            email_selectors = [
                'input[type="email"]',
                'input[name="identifier"]',
                'input[aria-label*="Email"]',
                'input[aria-label*="email"]',
                '#identifierId'
            ]
            email_found = False
            for sel in email_selectors:
                try:
                    await page.wait_for_selector(sel, timeout=3000)
                    await page.fill(sel, EMAIL)
                    email_found = True
                    logger.info(f"✅ Đã nhập email với selector: {sel}")
                    break
                except:
                    continue
            if not email_found:
                return {"status": "error", "message": "Không tìm thấy ô nhập email"}

            for sel in ('text="Next"', "#identifierNext"):
                try:
                    await page.click(sel, timeout=5000)
                    logger.info(f"✅ Đã click Next email với selector: {sel}")
                    break
                except Exception:
                    continue
            await page.wait_for_timeout(2000)

            # Nhập password - nhiều selector
            logger.info("🔑 Đang nhập password...")
            pwd_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[aria-label*="Password"]'
            ]
            pwd_found = False
            for sel in pwd_selectors:
                try:
                    await page.wait_for_selector(sel, timeout=3000)
                    await page.fill(sel, PASSWORD)
                    pwd_found = True
                    logger.info(f"✅ Đã nhập password với selector: {sel}")
                    break
                except:
                    continue
            if not pwd_found:
                return {"status": "error", "message": "Không tìm thấy ô nhập password"}

            for sel in ('text="Next"', "#passwordNext"):
                try:
                    await page.click(sel, timeout=5000)
                    logger.info(f"✅ Đã click Next password với selector: {sel}")
                    break
                except Exception:
                    continue

            logger.info("⏳ Chờ đăng nhập...")
            await page.wait_for_timeout(5000)

            # Phát hiện 2FA/CAPTCHA
            current_url = page.url
            page_text = ""
            try:
                page_text = (await page.content())[:3000].lower()
            except Exception:
                pass
            verification_signals = [
                "accounts.google.com/signin/v2/challenge",
                "accounts.google.com/speedbump",
                "verify it's you",
                "confirm your recovery",
                "unusual activity",
                "captcha",
            ]
            if any(sig in current_url.lower() or sig in page_text for sig in verification_signals):
                logger.warning("⚠️ Google yêu cầu xác minh bổ sung (2FA/CAPTCHA)")
                return {
                    "status": "error",
                    "message": "Google yêu cầu xác minh bổ sung (2FA/CAPTCHA/unusual activity)"
                }

            # Xử lý popup
            for sel in ('text="I agree"', 'text="Accept all"'):
                try:
                    await page.click(sel, timeout=3000)
                    logger.info(f"✅ Đã click popup: {sel}")
                except Exception:
                    pass

            await page.goto("https://www.youtube.com/", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            # Lấy cookie
            cookies = await context.cookies()
            logger.info(f"🍪 Lấy được {len(cookies)} cookies")
            
            if not cookies:
                return {"status": "error", "message": "Không lấy được cookie nào"}

            # Kiểm tra cookie đăng nhập
            cookie_names = {c.get("name", "") for c in cookies}
            if not ({"SID", "SAPISID", "__Secure-3PSID"} & cookie_names):
                logger.warning("⚠️ Không thấy cookie đăng nhập (SID/SAPISID)")

            netscape = "# Netscape HTTP Cookie File\n"
            for c in cookies:
                domain = c.get("domain", "")
                flag = "TRUE" if domain.startswith(".") else "FALSE"
                path = c.get("path", "/")
                secure = "TRUE" if c.get("secure", False) else "FALSE"
                expires = str(int(c.get("expires", 0)))
                name = c.get("name", "")
                value = c.get("value", "")
                netscape += f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n"

            with open(COOKIE_FILE, "w") as f:
                f.write(netscape)

            logger.info(f"✅ Cookie updated: {len(cookies)} cookies")
            return {"status": "success", "count": len(cookies)}

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        if page is not None:
            try:
                await page.screenshot(path="/tmp/cookie_sync_error.png")
                logger.info("📸 Đã lưu screenshot lỗi tại /tmp/cookie_sync_error.png")
            except Exception:
                pass
        return {"status": "error", "message": str(e)}
    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass


@app.route("/")
def index():
    return "Cookie Sync Service is running!", 200


@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


@app.route("/run_container", methods=["POST"])
def run():
    logger.info("📨 Nhận request POST /run_container")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(get_cookies())
    except Exception as e:
        logger.error(f"❌ Unhandled error: {e}")
        result = {"status": "error", "message": str(e)}
    finally:
        loop.close()
    logger.info(f"📤 Response: {result}")
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
