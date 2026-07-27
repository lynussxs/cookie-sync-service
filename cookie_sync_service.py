import asyncio
import os
import logging
import random
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

# Danh sách User-Agent thật
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

def random_delay(min_ms=500, max_ms=2000):
    """Tạo delay ngẫu nhiên để giống người thật"""
    return random.randint(min_ms, max_ms) / 1000

async def human_type(page, selector, text):
    """Gõ chữ giống người thật (có delay ngẫu nhiên)"""
    await page.click(selector)
    await page.wait_for_timeout(random_delay(200, 500))
    await page.fill(selector, text)

async def get_cookies():
    """Lấy cookie YouTube với nhiều kỹ thuật vượt chặn"""
    async with async_playwright() as p:
        # 1. CHỌN USER-AGENT NGẪU NHIÊN
        user_agent = random.choice(USER_AGENTS)
        
        # 2. LAUNCH VỚI NHIỀU ARGS ĐỂ BYPASS
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials',
                '--disable-features=BlockInsecurePrivateNetworkRequests',
                '--disable-features=OutOfBlinkCors',
                '--window-size=1920,1080',
                '--start-maximized'
            ]
        )
        try:
            # 3. CONTEXT GIỐNG NGƯỜI THẬT
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='America/New_York',
                permissions=['geolocation'],
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            )
            
            page = await context.new_page()
            
            # 4. STEALTH: XÓA DẤU VẾT WEBDRIVER
            await page.add_init_script("""
                // Xóa dấu vết webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Xóa dấu vết Chrome automation
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Xóa dấu vết languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Thêm dấu vết của Chrome thật
                window.chrome = {
                    runtime: {}
                };
                
                // Xóa dấu vết của Playwright
                delete window.__playwright__;
                delete window.__pw_manual;
                delete window.__PW_inspect;
            """)
            
            logger.info("📤 Đang truy cập YouTube...")
            await page.goto('https://www.youtube.com/', wait_until='networkidle')
            await page.wait_for_timeout(3000)
            
            # 5. TÌM NÚT SIGN IN BẰNG NHIỀU CÁCH
            logger.info("🔍 Tìm nút Sign in...")
            try:
                await page.click('text="Sign in"')
            except:
                try:
                    await page.click('a[aria-label="Sign in"]')
                except:
                    try:
                        await page.click('a[href*="accounts.google.com"]')
                    except:
                        await page.goto('https://accounts.google.com/login')
            
            await page.wait_for_timeout(3000)
            
            # 6. NHẬP EMAIL (NHIỀU SELECTOR)
            logger.info("📧 Đang nhập email...")
            email_selectors = [
                'input[type="email"]',
                'input[name="identifier"]',
                'input[aria-label*="Email"]',
                'input[aria-label*="email"]',
                '#identifierId'
            ]
            
            email_found = False
            for selector in email_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    await human_type(page, selector, EMAIL)
                    email_found = True
                    logger.info(f"✅ Đã nhập email với selector: {selector}")
                    break
                except:
                    continue
            
            if not email_found:
                raise Exception("Không tìm thấy ô nhập email")
            
            await page.wait_for_timeout(1000)
            
            # 7. CLICK NEXT (NHIỀU CÁCH)
            try:
                await page.click('text="Next"')
            except:
                try:
                    await page.click('button[type="button"]:has-text("Next")')
                except:
                    try:
                        await page.click('#identifierNext')
                    except:
                        await page.press('input[type="email"]', 'Enter')
            
            await page.wait_for_timeout(3000)
            
            # 8. NHẬP PASSWORD
            logger.info("🔑 Đang nhập password...")
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[aria-label*="Password"]',
                'input[aria-label*="password"]'
            ]
            
            pwd_found = False
            for selector in password_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    await human_type(page, selector, PASSWORD)
                    pwd_found = True
                    logger.info(f"✅ Đã nhập password với selector: {selector}")
                    break
                except:
                    continue
            
            if not pwd_found:
                raise Exception("Không tìm thấy ô nhập password")
            
            await page.wait_for_timeout(1000)
            
            # 9. CLICK NEXT CHO PASSWORD
            try:
                await page.click('text="Next"')
            except:
                try:
                    await page.click('button[type="button"]:has-text("Next")')
                except:
                    try:
                        await page.click('#passwordNext')
                    except:
                        await page.press('input[type="password"]', 'Enter')
            
            logger.info("⏳ Chờ đăng nhập...")
            await page.wait_for_timeout(10000)
            
            # 10. XỬ LÝ POPUP NẾU CÓ
            try:
                await page.click('text="I agree"')
            except:
                pass
            try:
                await page.click('text="Accept all"')
            except:
                pass
            
            # 11. CHUYỂN VỀ YOUTUBE
            await page.goto('https://www.youtube.com/', wait_until='networkidle')
            await page.wait_for_timeout(3000)
            
            # 12. LẤY COOKIE
            cookies = await context.cookies()
            logger.info(f"🍪 Lấy được {len(cookies)} cookies")
            
            if not cookies:
                await page.screenshot(path="error.png")
                return {'status': 'error', 'message': 'No cookies found'}
            
            # 13. CHUYỂN SANG NETSCAPE
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
            
            with open(COOKIE_FILE, 'w') as f:
                f.write(netscape)
            
            logger.info(f"✅ Cookie updated: {len(cookies)} cookies")
            return {'status': 'success', 'count': len(cookies), 'cookies': cookies}
            
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
