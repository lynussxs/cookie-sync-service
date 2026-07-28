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
    browser = None
    page = None
    try:
        async with async_playwright() as p:
            # QUAN TRỌNG: headless=True — container server (Railway) KHÔNG có
            # display/GUI, headless=False sẽ crash launch() ngay lập tức.
            # Đây là nguyên nhân chính khiến service fail hoàn toàn trước đây.
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
            # Xoá dấu vết webdriver — giảm khả năng bị Google chặn ngay từ vòng đầu
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
            page = await context.new_page()

            if not EMAIL or not PASSWORD:
                return {"status": "error", "message": "Thiếu EMAIL hoặc PASSWORD trong env vars"}

            # ── Đăng nhập ────────────────────────────────────────────────────
            await page.goto("https://www.youtube.com/", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(1500)

            # Nút "Sign in" — thử vài selector, không dừng cứng nếu 1 cái fail
            signed_in_button_found = False
            for sel in ('text="Sign in"', 'a[aria-label="Sign in"]', 'a[href*="accounts.google.com"]'):
                try:
                    await page.click(sel, timeout=5000)
                    signed_in_button_found = True
                    break
                except Exception:
                    continue
            if not signed_in_button_found:
                await page.goto("https://accounts.google.com/login", timeout=30000)
            await page.wait_for_timeout(1500)

            # Nhập email
            try:
                await page.wait_for_selector('input[type="email"]', timeout=10000)
                await page.fill('input[type="email"]', EMAIL)
            except Exception:
                return {"status": "error", "message": "Không tìm thấy ô nhập email — Google có thể đã đổi giao diện"}

            for sel in ('text="Next"', "#identifierNext"):
                try:
                    await page.click(sel, timeout=5000)
                    break
                except Exception:
                    continue
            await page.wait_for_timeout(2000)

            # Nhập password
            try:
                await page.wait_for_selector('input[type="password"]', timeout=10000)
                await page.fill('input[type="password"]', PASSWORD)
            except Exception:
                return {
                    "status": "error",
                    "message": "Không tìm thấy ô nhập password — có thể Google yêu cầu xác minh bổ sung (2FA/CAPTCHA)",
                }

            for sel in ('text="Next"', "#passwordNext"):
                try:
                    await page.click(sel, timeout=5000)
                    break
                except Exception:
                    continue

            await page.wait_for_timeout(5000)

            # ── Phát hiện 2FA/CAPTCHA/xác minh bổ sung ──────────────────────
            # QUAN TRỌNG: nếu Google yêu cầu xác minh mà script cứ lấy cookie
            # bừa, cookie đó chỉ là session ẨN DANH (chưa đăng nhập thật) —
            # dùng để bypass bot-check YouTube sẽ KHÔNG có tác dụng gì, và
            # lỗi "Sign in to confirm you're not a bot" trên bot nhạc sẽ vẫn
            # tiếp diễn y hệt dù cookie "sync thành công".
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
                logger.warning("⚠️ Google yêu cầu xác minh bổ sung (2FA/CAPTCHA) — cookie sẽ KHÔNG hợp lệ")
                return {
                    "status": "error",
                    "message": (
                        "Google yêu cầu xác minh bổ sung (2FA/CAPTCHA/unusual activity). "
                        "Tài khoản này có thể đã bị Google đánh dấu do đăng nhập tự động lặp lại. "
                        "Cần đăng nhập thủ công 1 lần trên trình duyệt thật để gỡ cảnh báo trước khi thử lại."
                    ),
                }

            # Xử lý popup đồng ý (nếu có) — không bắt buộc phải thành công
            for sel in ('text="I agree"', 'text="Accept all"'):
                try:
                    await page.click(sel, timeout=3000)
                except Exception:
                    pass

            await page.goto("https://www.youtube.com/", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            # ── Lấy cookie ───────────────────────────────────────────────────
            cookies = await context.cookies()
            if not cookies:
                return {"status": "error", "message": "Không lấy được cookie nào (danh sách rỗng)"}

            # Kiểm tra có cookie đăng nhập thật không (vd SID/SAPISID là dấu
            # hiệu đã login) — tránh lưu cookie ẩn danh tưởng là thành công.
            cookie_names = {c.get("name", "") for c in cookies}
            if not ({"SID", "SAPISID", "__Secure-3PSID"} & cookie_names):
                logger.warning("⚠️ Không thấy cookie đăng nhập (SID/SAPISID) — có thể login chưa thành công")

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
        # Chụp ảnh màn hình để debug nếu có thể (không chặn response)
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
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(get_cookies())
    except Exception as e:
        # Bọc thêm 1 lớp phòng hờ — đảm bảo route LUÔN trả JSON, không bao giờ
        # để lộ lỗi 500 thô ra ngoài (bot gọi service này cần parse JSON được).
        logger.error(f"❌ Unhandled error in /run_container: {e}")
        result = {"status": "error", "message": str(e)}
    finally:
        loop.close()
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
