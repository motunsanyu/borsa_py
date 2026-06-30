import requests
import os
from urllib.parse import urljoin,urlencode

def telegram_bot_sendtext(bot_mesaj, id: str):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is missing.")

    bot_chatID = id
    url = "https://api.telegram.org/bot"
    send_text = url + bot_token + '/sendMessage?chat_id=' + str(bot_chatID) + '&parse_mode=Markdown&text=' + bot_mesaj

    response = requests.get(send_text)


"""baseUrl = "https://api.telegram.org/bot"

def send_message(bot_token:str,bot_mesaj:str,chat_id:str):
    params = {"chat_id":chat_id,
    "parse_mode":"Markdown",
    "text":bot_mesaj}

    url = urljoin(baseUrl,"bot" + bot_token + "/sendMessage?")
    response = requests(url,params = params)"""
