import os
from urllib.parse import quote

import requests
from flask import Flask, jsonify, request

from scrape_borsa import format_stock_message, get_stock


app = Flask(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "telegram-webhook")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None


def send_telegram_message(chat_id, text: str, reply_markup=None):
    if not TELEGRAM_API_URL:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is missing.")

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    if reply_markup:
        payload["reply_markup"] = reply_markup

    response = requests.post(
        f"{TELEGRAM_API_URL}/sendMessage",
        json=payload,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def stock_detail_keyboard(stock: dict):
    detail_link = stock.get("detail_link", "")
    symbol = stock.get("symbol", "").strip().upper()

    buttons = []

    if detail_link.startswith("http"):
        buttons.append(
            {
                "text": "Detay sayfasini ac",
                "url": detail_link,
            }
        )

    if symbol:
        tradingview_symbol = quote(f"BIST:{symbol}", safe="")
        buttons.append(
            {
                "text": "TradingView grafigi",
                "url": f"https://www.tradingview.com/chart/?symbol={tradingview_symbol}",
            }
        )

    if not buttons:
        return None

    return {
        "inline_keyboard": [
            buttons
        ]
    }


def help_message() -> str:
    return (
        "Borsa botuna hos geldin.\n\n"
        "Hisse sorgulamak icin:\n"
        "/hisse THYAO\n"
        "/hisse ASELS\n\n"
        "Komut yerine sadece hisse kodu da yazabilirsin."
    )


def extract_symbol(text: str):
    text = (text or "").strip()
    if not text:
        return None

    parts = text.split()
    command = parts[0].split("@", 1)[0].lower()

    if command in ["/start", "/help", "yardim", "help"]:
        return "HELP"

    if command in ["/hisse", "/stock"]:
        return parts[1].upper() if len(parts) > 1 else None

    if len(parts) == 1:
        return parts[0].upper()

    return None


def handle_message(message: dict):
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "")

    if not chat_id:
        return

    symbol = extract_symbol(text)

    if symbol == "HELP":
        send_telegram_message(chat_id, help_message())
        return

    if not symbol:
        send_telegram_message(chat_id, "Lutfen /hisse THYAO formatinda bir hisse kodu gonder.")
        return

    stock = get_stock(symbol)
    if not stock:
        send_telegram_message(chat_id, f"{symbol} icin veri bulunamadi.")
        return

    send_telegram_message(chat_id, format_stock_message(stock), stock_detail_keyboard(stock))


@app.get("/")
def health_check():
    return jsonify({"status": "ok"})


@app.post(f"/telegram/{WEBHOOK_SECRET}")
def telegram_webhook():
    update = request.get_json(silent=True) or {}
    message = update.get("message") or update.get("edited_message")

    if message:
        handle_message(message)

    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
