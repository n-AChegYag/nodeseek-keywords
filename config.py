import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_USER_ID: int = int(os.environ["ALLOWED_USER_ID"])

# How often to poll the RSS feed, in seconds (default: 60, matching feed TTL)
POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "60"))

RSS_BASE_URL: str = "https://rss.nodeseek.com/"
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/keywords.db")

# Flood protection: max individual notifications sent per poll cycle (overflow is summarised)
MAX_NOTIFICATIONS_PER_POLL: int = int(os.getenv("MAX_NOTIFICATIONS_PER_POLL", "10"))

# RSS health: alert user after this many consecutive fetch failures
RSS_FAIL_ALERT_THRESHOLD: int = int(os.getenv("RSS_FAIL_ALERT_THRESHOLD", "3"))
