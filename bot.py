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
DEXSCREENER_SEARCH_URL = "https://api.dexscreener.com/latest/dex/search"

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# --- State (in-memory; resets if the bot restarts) ---
state = {
    "last_alert_direction": None,  # "up" or "down" or None
    "last_alert_pct": None,
    "price_target_alerted": False,  # whether we've already alerted for PRICE_ALERT_TARGET
    "market_alert_direction": None,  # "up" or "down" or None, for the restart-proof h6/h24 alert
    "market_alert_time": None,
}

ALERT_COOLDOWN_MINUTES = int(os.environ.get("ALERT_COOLDOWN_MINUTES", "60"))


def send_telegram(text: str):
    try:
        resp = requests.post(
            TELEGRAM_API,
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=15,
        )
        if resp.status_code != 200:
            log.error("Telegram send failed: %s %s", resp.status_code, resp.text)
    except Exception as e:
        log.error("Telegram send exception: %s", e)


def fetch_pair():
    """Fetch the best-liquidity XST/USDC-ish pair from DexScreener."""
    try:
        if TOKEN_ADDRESS:
            r = requests.get(DEXSCREENER_TOKEN_URL.format(address=TOKEN_ADDRESS), timeout=15)
        else:
            r = requests.get(DEXSCREENER_SEARCH_URL, params={"q": SEARCH_QUERY}, timeout=15)
        r.raise_for_status()
        data = r.json()
        pairs = data.get("pairs") or []
        if not pairs:
            log.warning("No pairs returned from DexScreener")
            return None

        # Filter to Solana XST pairs with decent liquidity, pick highest liquidity
        candidates = [
            p for p in pairs
            if p.get("chainId") == "solana"
            and p.get("baseToken", {}).get("symbol", "").upper() == "XST"
            and (p.get("liquidity", {}) or {}).get("usd", 0) >= MIN_LIQUIDITY_USD
        ]
        if not candidates:
            candidates = [p for p in pairs if p.get("baseToken", {}).get("symbol", "").upper() == "XST"]
        if not candidates:
            log.warning("No matching XST pairs found")
            return None

        best = max(candidates, key=lambda p: (p.get("liquidity", {}) or {}).get("usd", 0))
        return best
    except Exception as e:
        log.error("Fetch error: %s", e)
        return None


def check_once():
    pair = fetch_pair()
    if not pair:
        return

    price = float(pair.get("priceUsd", 0) or 0)
    price_change = pair.get("priceChange", {}) or {}
    change_1h_pct = float(price_change.get("h1", 0) or 0)
    change_6h_pct = float(price_change.get("h6", 0) or 0)
    change_24h_pct = float(price_change.get("h24", 0) or 0)  # % change vs 24h ago (not high/low)
    pair_url = pair.get("url", "")
    pair_name = f"{pair.get('baseToken', {}).get('symbol')}/{pair.get('quoteToken', {}).get('symbol')}"

    # DexScreener doesn't give 24h high/low directly in this endpoint,
    # so we approximate: derive high/low from current price and % change,
    # then track our own rolling high/low across checks for accuracy.
    now = datetime.now(timezone.utc)

    if "session_high" not in state or state.get("session_reset_date") != now.date():
        state["session_high"] = price
        state["session_low"] = price
        state["session_reset_date"] = now.date()
        log.info("Session high/low reset for new day: %.6f", price)

    if price > state["session_high"]:
        state["session_high"] = price
    if price < state["session_low"]:
        state["session_low"] = price

    session_high = state["session_high"]
    session_low = state["session_low"]

    drop_from_high_pct = (session_high - price) / session_high * 100 if session_high else 0
    rise_from_low_pct = (price - session_low) / session_low * 100 if session_low else 0

    log.info(
        "%s price=$%.6f | 24h%%=%.2f%% | drop_from_high=%.2f%% | rise_from_low=%.2f%%",
        pair_name, price, change_24h_pct, drop_from_high_pct, rise_from_low_pct,
    )

    # --- Alert on fixed price target crossed upward ---
    if PRICE_ALERT_TARGET is not None:
        if price >= PRICE_ALERT_TARGET and not state["price_target_alerted"]:
            send_telegram(
                f"🎯 KAINOS RIBA PASIEKTA\n\n"
                f"<b>{pair_name}</b>\n"
                f"Kaina: ${price:.6f}\n"
                f"Pasiekė/viršijo tikslą ${PRICE_ALERT_TARGET:.6f}\n\n"
                f"{pair_url}"
            )
            state["price_target_alerted"] = True
        elif price < PRICE_ALERT_TARGET and state["price_target_alerted"]:
            # Price dropped back below target; re-arm so a future cross alerts again
            state["price_target_alerted"] = False

    # --- Restart-proof alert based on DexScreener's own h6 change ---
    # This doesn't depend on the bot's own uptime/memory, so it still works
    # even if the process restarts (unlike the session high/low tracking below).
    now_ts = now.timestamp()
    cooldown_ok = (
        state["market_alert_time"] is None
        or (now_ts - state["market_alert_time"]) >= ALERT_COOLDOWN_MINUTES * 60
    )
    if abs(change_6h_pct) >= ALERT_THRESHOLD_LOW and cooldown_ok:
        direction = "down" if change_6h_pct < 0 else "up"
        is_strong = abs(change_6h_pct) >= ALERT_THRESHOLD_HIGH
        if direction == "down":
            severity = "🔴🔴 STIPRUS KRITIMAS (6h)" if is_strong else "🔴 KRITIMAS (6h)"
        else:
            severity = "🟢🟢 STIPRUS KILIMAS (6h)" if is_strong else "🟢 KILIMAS (6h)"
        send_telegram(
            f"{severity}\n\n"
            f"<b>{pair_name}</b>\n"
            f"Kaina: ${price:.6f}\n"
            f"Pokytis per 6h: {change_6h_pct:+.1f}%\n"
            f"Pokytis per 24h: {change_24h_pct:+.1f}%\n\n"
            f"{pair_url}"
        )
        state["market_alert_direction"] = direction
        state["market_alert_time"] = now_ts

    # --- Alert on drop from session high ---
    if drop_from_high_pct >= ALERT_THRESHOLD_LOW:
        if state["last_alert_direction"] != "down" or (
            drop_from_high_pct - (state["last_alert_pct"] or 0) >= 5
        ):
            severity = "🔴🔴 STIPRUS KRITIMAS" if drop_from_high_pct >= ALERT_THRESHOLD_HIGH else "🔴 KRITIMAS"
            send_telegram(
                f"{severity}\n\n"
                f"<b>{pair_name}</b>\n"
                f"Kaina: ${price:.6f}\n"
                f"Krito {drop_from_high_pct:.1f}% nuo dienos aukščio (${session_high:.6f})\n\n"
                f"{pair_url}"
            )
            state["last_alert_direction"] = "down"
            state["last_alert_pct"] = drop_from_high_pct

    # --- Alert on rise from session low ---
    elif rise_from_low_pct >= ALERT_THRESHOLD_LOW:
        if state["last_alert_direction"] != "up" or (
            rise_from_low_pct - (state["last_alert_pct"] or 0) >= 5
        ):
            severity = "🟢🟢 STIPRUS KILIMAS" if rise_from_low_pct >= ALERT_THRESHOLD_HIGH else "🟢 KILIMAS"
