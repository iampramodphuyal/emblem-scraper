from dotenv import load_dotenv
import os

# Load .env once — globally for your app
load_dotenv()

# Access variables safely
API_KEY = os.getenv("API_KEY", "default_key")
DB_URL = os.getenv("DB_URL", "sqlite:///db.sqlite3")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Proxy
PROXY_URL = os.getenv("HTTP_PROXY")
PROXY_HOST = os.getenv("PROXY_HOST")
PROXY_PORT=os.getenv("PROXY_PORT")
PROXY_USERNAME= os.getenv("PROXY_USERNAME")
PROXY_PASSWORD= os.getenv("PROXY_PASSWORD")

# Browser
HEADLESS=os.getenv("HEADLESS")

# Outputs file path
OUTPUT_PATH=os.getenv("OUTPUT_PATH", "outputs/raw")
STATIC_FILE_PATH=os.getenv("STATIC_FILE_PATH", "outputs/static")
TMP_PATH=os.getenv("TMP_PATH", "outputs/tmp")

# Browser session path
PLAYWRIGHT_SESSION_PATH=os.getenv("PLAYWRIGHT_SESSION_PATH", "sessions/recaptcha_profile")

# Crawler Flow
SEQUENTIAL_FLOW=os.getenv("SEQUENTIAL_FLOW", "True").lower() == "true"

# Concurrency Control
SEMAPHORE=int(os.getenv("SEMAPHORE", 5))
BATCH_SIZE=int(os.getenv("BATCH_SIZE", 50))

