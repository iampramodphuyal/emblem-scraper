import os
import random
from logger.logger import get_logger
from settings import PLAYWRIGHT_SESSION_PATH, PROXY_URL, PROXY_USERNAME, PROXY_PASSWORD, PROXY_HOST, PROXY_PORT

logger = get_logger("Helpers")

sitekey = os.getenv('CAPTCHA_SITE_KEY', 'YOUR_SITE_KEY')
def two_cap():
    from twocaptcha import TwoCaptcha
    api_key = os.getenv('APIKEY_2CAPTCHA', 'YOUR_API_KEY')
    
    solver = TwoCaptcha(api_key)

    try:
        result = solver.recaptcha(
            sitekey=sitekey,
            # url='https://my.emblemhealth.com/member/s/find-care-plans',
            url='https://my.emblemhealth.com/member/s/find-care-search?action=findcaresearch&isPublic=true&publicPage=Plan&lobId=1012&lobMctrType=1001&grgrMctrType=NOT%20APPLICABLE&productDescription=NOT%20APPLICABLE&groupNum=NOT%20APPLICABLE&coverageType=M&networkCode=D013%2C%20D014%2C%20D004%2C%20D005%2C%20D006%2C%20D003&network=Enhanced%20Care%20Prime%20NYSOH%20Marketplace%20Network&planName=Essential%20Plan&fhn&category=Individual%20%26%20Family%20Plans&preferred=No&coe=No',
            # version='v2',
            invisible=1,
            # action="captchaValidation"
            )

    except Exception as e:
        logger.error(f"Error solving captcha: {e}")

    else:
        logger.info(f"Captcha solved: {result['code']}")
        return result['code']

def capsolver():
    import capsolver
    capsolver.api_key = os.getenv('CAPSOLVER_API_KEY', 'YOUR_CAPSOLVER_API_KEY')
    # print("CAPSOLVER API KEY:", capsolver.api_key)
    solution = capsolver.solve({
            # "type": "ReCaptchaV3Task",
            "type": "ReCaptchaV2TaskProxyless",
            # "type": "ReCaptchaV2Task",
            # "websiteURL": 'https://my.emblemhealth.com/member/s/find-care-plans',
            "websiteURL": 'https://my.emblemhealth.com/member/s/find-care-search?action=findcaresearch&isPublic=true&publicPage=Plan&lobId=1012&lobMctrType=1001&grgrMctrType=NOT%20APPLICABLE&productDescription=NOT%20APPLICABLE&groupNum=NOT%20APPLICABLE&coverageType=M&networkCode=D013%2C%20D014%2C%20D004%2C%20D005%2C%20D006%2C%20D003&network=Enhanced%20Care%20Prime%20NYSOH%20Marketplace%20Network&planName=Essential%20Plan&fhn&category=Individual%20%26%20Family%20Plans&preferred=No&coe=No',
            "websiteKey": sitekey,
            'isInvisible': True,
            'pageAction': 'captchaValidation',
            'minScore': 0.9,
            # 'proxy': f"{PROXY_URL}"
          })
          
    balance = capsolver.balance()
    logger.info(f"Capsolver balance: {balance['balance']}")

    return solution['gRecaptchaResponse']


async def fake_solve_captcha(page_url: str = "https://my.emblemhealth.com/member/s/find-care-plans"):
    """
    Load a page that contains reCAPTCHA v3 and call grecaptcha.execute(..., { action: "captchaValidation" })
    Returns the captcha token string.
    """
    from playwright.async_api import async_playwright, Page, Error
    from settings import PROXY_URL, PROXY_USERNAME, PROXY_PASSWORD, PROXY_HOST, PROXY_PORT
    import asyncio
    
    logger.info("Starting fake_solve_captcha : Proxy URL: %s", PROXY_URL)

    js_code = """
    async (args) => {
        const { siteKey, action } = args;
        
        // Check if grecaptcha is already loaded
        if (typeof grecaptcha === 'undefined') {
            // Load the reCAPTCHA script
            const script = document.createElement('script');
            // script.src = `https://www.google.com/recaptcha/api.js?render=${siteKey}`;
            script.src = `https://www.google.com/recaptcha/api2/reload?k=${siteKey}`;
            document.head.appendChild(script);
            
            // Wait for script to load
            await new Promise((resolve) => {
                script.onload = resolve;
            });
            
            // Wait a bit more for grecaptcha to initialize
            await new Promise(resolve => setTimeout(resolve, 2000));
        }
        
        // Execute reCAPTCHA
        return new Promise((resolve) => {
            grecaptcha.ready(function() {
                grecaptcha.execute(siteKey, {action: action}).then(function(token) {
                    console.log('Token:', token);
                    resolve(token);
                });
            });
        });
    }
    """

    attempt = 0
    while attempt < 5:
        try:
            async with async_playwright() as p:
                # Launch browser
                # browser = await p.chromium.launch(
                context = await p.chromium.launch_persistent_context(
                    headless=False, 
                    proxy = {
                                "server": f"http://{PROXY_HOST}:{PROXY_PORT}",  # Example: http://123.45.67.89:8080
                                "username": f"{PROXY_USERNAME}",  # optional
                                "password": f"{PROXY_PASSWORD}",  # optional
                        },
                    channel="chrome",
                    user_data_dir=PLAYWRIGHT_SESSION_PATH,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                    viewport={"width": 1366, "height": 768},
                    device_scale_factor=1,
                    executable_path="/usr/bin/google-chrome-stable",
                    )
                # context = await browser.new_context()
                page = await context.new_page()
                await page.goto("https://google.com")
                await page.wait_for_timeout(3000)

                # Human-like scroll
                await page.mouse.wheel(0, 300)
                await page.wait_for_timeout(1500)

                # Navigate to a real site before target
                await page.goto("https://news.ycombinator.com")
                await page.wait_for_timeout(2000)
                
                print(f"Navigating to: {page_url}")
                await page.goto(page_url, timeout=30000)  # 30s timeout
                await page.wait_for_load_state("networkidle")

                await human_curve(page, (100, 100), (500, 380), steps=50)
                await page.mouse.wheel(0, 500);
                await page.wait_for_timeout(5000)
                
                # Execute your JS code in the page context
                site_key = '6LcNq-wpAAAAAPupbdPcNjDpmhx4_HbfSmRW2ME4'
                result = await page.evaluate(js_code, {"siteKey": site_key, "action": "captchaValidation"})
                print("✅ JS execution result:", result)

                # await browser.close()
                await context.close()
                return result

        except Error as e:
            print(f"❌ Playwright error: {e}")
            attempt += 1
            await asyncio.sleep(2)  # wait before retrying

        except Exception as e:
            print(f"⚠️ Unexpected error: {e}")
            attempt += 1
            await asyncio.sleep(2)  # wait before retrying
    logger.error("Failed to solve captcha after multiple attempts.")
    return None  # or raise an exception if preferred

async def human_curve(page, start, end, steps=30):
    x1, y1 = start
    x2, y2 = end

    # Random control points
    cx1 = x1 + (x2 - x1) * random.random()
    cy1 = y1 + (y2 - y1) * random.random()
    cx2 = x1 + (x2 - x1) * random.random()
    cy2 = y1 + (y2 - y1) * random.random()

    for i in range(steps + 1):
        t = i / steps
        x = (1 - t)**3 * x1 + 3 * (1 - t)**2 * t * cx1 + 3 * (1 - t) * t**2 * cx2 + t**3 * x2
        y = (1 - t)**3 * y1 + 3 * (1 - t)**2 * t * cy1 + 3 * (1 - t) * t**2 * cy2 + t**3 * y2

        await page.mouse.move(x, y)
        await page.wait_for_timeout(random.randint(5, 25))



def make_fwuid(length=64):
        """
        Generate a random string similar to the example fwuid.
        Produces a URL-safe base64-like core and appends a dot-separated numeric suffix
        so the overall form resembles the example. The total length is `length`.
        """
        import secrets
        import base64
        import random

        # produce enough random bytes, base64-url encode and strip '='
        b = secrets.token_bytes((length * 3) // 4 + 6)
        core = base64.urlsafe_b64encode(b).decode('ascii').rstrip('=')

        # numeric suffix with three dot-separated segments (mimics "...11.32768.0")
        suffix = '.'.join(str(random.randint(0, 99999)) for _ in range(3))

        # if suffix is longer than available space, just truncate the core
        if len(suffix) + 1 >= length:
            return core[:length]

        core_len = length - len(suffix) - 1
        return core[:core_len] + '.' + suffix

def generate_request_ids():
    import uuid
    import random
    return {
        "pageScope": str(uuid.uuid4()),
        "requestId": str(random.random())[2:17] + "00000965559",
        "spanId": f"{random.random():.16f}".split(".")[1][:16],
        "traceId": f"{random.random():.16f}".split(".")[1][:16],
    }

def save_content_as_json(content, path):
    """
    Save the provided content as a JSON file at the specified path.
    
    :param content: The content to save (must be serializable to JSON).
    :param path: The file path where the JSON should be saved.
    """
    import json
    
    try:
        with open(path, 'w') as json_file:
            json.dump(content, json_file, indent=4)
        logger.info(f"Content successfully saved to {path}")
    except Exception as e:
        logger.error(f"Error saving content to JSON: {e}")


def ensure_dir_exists(path: str) -> bool:
    """
    Ensure the directory at `path` exists. Create it (including parents) if missing.
    Returns True if the directory exists or was created successfully, False on error.
    """
    try:
        if os.path.exists(path):
            if os.path.isdir(path):
                logger.info("Directory exists: %s", path)
                return True
            else:
                logger.error("Path exists but is not a directory: %s", path)
                return False
        os.makedirs(path, exist_ok=True)
        logger.info("Created directory: %s", path)
        return True
    except Exception as e:
        logger.error("Failed to ensure directory %s: %s", path, e)
        return False



