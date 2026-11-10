import os
import requests

def send_telegram(message: str) -> bool:
    """Send message to Telegram. Returns True on success."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("未配置 Telegram Secrets，跳过推送")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200 and resp.json().get("ok"):
            print("Telegram 推送成功")
            return True
        else:
            print(f"Telegram 推送失败: status={resp.status_code}, body={resp.text[:200]}")
            return False
    except Exception as e:
        print(f"Telegram 推送异常: {e}")
        return False
