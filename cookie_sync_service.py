# cookie_sync_service.py
import asyncio
import os
import logging
from flask import Flask, request, jsonify
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
    """Lấy cookie YouTube bằng Playwright"""
    async with async_playwright() as p:
        # CHẠY HEADLESS (không cần X Server)
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        try:
            context = await browser.new_context()
            page = await context.new_page()
            
            # Đi đến YouTube và đăng nhập
            await page.goto('https://www.youtube.com/')
            await page.click('text="Sign in"')
            await page.wait_for_timeout(1000)
            
            # Nhập email
            await page.fill('input[type="email"]', EMAIL)
            await page.click('text="Next"')
            await page.wait_for_timeout(1000)
            
            # Nhập password
            await page.fill('input[type="password"]', PASSWORD)
            await page.click('text="Next"')
            
            # Chờ đăng nhập thành công
            await page.wait_for_timeout(5000)
            
            # Lấy cookie
            cookies = await context.cookies()
            
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
            logger.error(f"❌ Error: {e}")
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
    loop = asyncio.new_event loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(get_cookies())
    loop.close()
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
