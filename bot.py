import os
import time
import logging
import requests
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("xst-bot")

# --- Config (set these as environment variables on Railway) ---
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# The XST token address (Xsolu XST on Solana). Confirm/replace if needed.
TOKEN_ADDRESS = os.environ.get("XST_TOKEN_ADDRESS", "")
# Fallback: search by symbol+name if no address given
SEARCH_QUERY = os.environ.get("XST_SEARCH_QUERY", "XST Xsolu")

CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", "120"))  # 2 min
ALERT_THRESHOLD_LOW = float(os.environ.get("ALERT_THRESHOLD_LOW", "10"))   # %
ALERT_THRESHOLD_HIGH = float(os.environ.get("ALERT_THRESHOLD_HIGH", "15"))  # %
MIN_LIQUIDITY_USD = float(os.environ.get("MIN_LIQUIDITY_USD", "10000"))

# Optional: fixed price target alert (e.g. notify once price crosses $0.058)
PRICE_ALERT_TARGET = os.environ.get("PRICE_ALERT_TARGET")
PRICE_ALERT_TARGET = float(PRICE_ALERT_TARGET) if PRICE_ALERT_TARGET else None

DEXSCREENER_TOKEN_URL = "https://api.dexscreener.com/latest/dex/tokens/{address}"
DEXSCREE
