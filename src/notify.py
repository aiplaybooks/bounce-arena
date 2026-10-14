"""Telegram notifications to the owner. Silently no-ops when TELEGRAM_TOKEN/TELEGRAM_CHAT_ID are missing."""
import os

import requests


def _api(method):
    return f"https://api.telegram.org/bot{os.environ['TELEGRAM_TOKEN']}/{method}"


def enabled():
    return bool(os.environ.get("TELEGRAM_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def text(msg):
    if not enabled():
        return
    try:
        requests.post(_api("sendMessage"), data={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": msg[:4000],
                                                  "disable_web_page_preview": "true"}, timeout=30)
    except requests.RequestException as e:
        print("telegram:", e)


def video(path, caption):
    if not enabled():
        return
    try:
        with open(path, "rb") as f:
            r = requests.post(_api("sendVideo"), data={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "caption": caption[:1024],
                                                       "supports_streaming": "true"}, files={"video": f}, timeout=180)
        if r.status_code >= 400:
            print("telegram:", r.text[:200])
            text(caption)
    except requests.RequestException as e:
        print("telegram:", e)
