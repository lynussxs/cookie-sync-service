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

async def get_cookies():
    """Lấy cookie YouTube bằng Playwright với user-agent thật"""
    async with async_playwright() as p:
        # 1. Bắt chước trình duyệt thật hơn
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage'
            ]
        )
        try:
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            logger.info("📤 Đang truy cập YouTube...")
            await page.goto('https://www.youtube.com/')
            await page.wait_for_timeout(3000)
            
            # 2. Click Sign In
            try:
                await page.click('text="Sign in"')
                logger.info("✅ Đã click Sign in")
            except:
                try:
                    await page.click('a[aria-label="Sign in"]')
                except:
                    logger.warning("⚠️ Không tìm thấy nút Sign in")
            
            await page.wait_for_timeout(2000)
            
            # 3. Nhập email
            logger.info("📧 Đang nhập email...")
            await page.fill('input[type="email"]', EMAIL)
            await page.wait_for_timeout(1000)
            await page.click('text="Next"')
            await page.wait_for_timeout(3000)
            
            # 4. Nhập password
            logger.info("🔑 Đang nhập password...")
            await page.fill('input[type="password"]', PASSWORD)
            await page.wait_for_timeout(1000)
            await page.click('text="Next"')
            
            # 5. Chờ đăng nhập thành công
            logger.info("⏳ Chờ đăng nhập...")
            await page.wait_for_timeout(8000)
            
            # 6. Chuyển sang YouTube (nếu chuyển hướng)
            try:
                await page.goto('https://www.youtube.com/')
                await page.wait_for_timeout(3000)
            except:
                pass
            
            # Lấy cookies
            cookies = await context.cookies()
            logger.info(f"🍪 Lấy được {len(cookies)} cookies")
            
            if not cookies:
                logger.error("❌ Không lấy được cookie nào!")
                await page.screenshot(path="error.png")
                return {'status': 'error', 'message': 'No cookies found'}
            
            # Chuyển sang format Netscape
            netscape = "# Netscape HTTP Cookie File\n"
            for c in cookies:
                domain = c.get('domain', '')
                flag = 'TRUE' if domain.startswith('.') else 'FALSE'
                path = c.get('path', '/')
                secure = 'TRUE' if c.get('secure', False) else 'FALSE'
                expires = str(int(c.get('expires', 0)))
                name = c.get('name', '')
                value = c.get('value', '')
                netscape += f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n"
            
            # Ghi file
            with open(COOKIE_FILE, 'w') as f:
                f.write(netscape)
            
            logger.info(f"✅ Cookie updated: {len(cookies)} cookies")
            return {'status': 'success', 'count': len(cookies)}
            
        except Exception as e:
            logger.error(f"❌ Lỗi: {e}")
            try:
                await page.screenshot(path="error.png")
                logger.info("📸 Đã lưu screenshot")
            except:
                pass
            return {'status': 'error', 'message': str(e)}
        finally:
            await browser.close()

@app.route('/')
def index():
    return "Cookie Sync Service is running!", 200

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

@app.route('/run_container', methods=['POST'])
def run():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(get_cookies())
    loop.close()
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
