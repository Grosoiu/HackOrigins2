import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

CONFIG_NAME = "config.json"


def _load_config() -> dict:
    config_path = Path(__file__).resolve().parents[1] / CONFIG_NAME
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False


def send_telegram_message(
    text: str,
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    timeout: float = 5.0,
    debug: bool = False,
) -> bool:
    cfg = _load_config()
    if token is None:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
    if chat_id is None:
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        if not token:
            token = cfg.get("telegram_bot_token") or cfg.get("TELEGRAM_BOT_TOKEN")
        if not chat_id:
            chat_id = cfg.get("telegram_chat_id") or cfg.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        if debug:
            print("[TG] Missing token or chat_id. Check config.json or env vars.")
        return False

    insecure = _parse_bool(cfg.get("telegram_insecure_ssl"))
    ca_bundle = cfg.get("telegram_ca_bundle")
    if not insecure:
        env_insecure = os.getenv("TELEGRAM_INSECURE_SSL")
        insecure = _parse_bool(env_insecure)
    if not ca_bundle:
        ca_bundle = os.getenv("TELEGRAM_CA_BUNDLE")

    context = None
    if insecure:
        context = ssl._create_unverified_context()
        if debug:
            print("[TG] WARNING: SSL verification disabled.")
    elif ca_bundle:
        ca_path = Path(ca_bundle)
        if not ca_path.is_absolute():
            ca_path = (Path(__file__).resolve().parents[1] / ca_path).resolve()
        if ca_path.exists():
            context = ssl.create_default_context(cafile=str(ca_path))
        elif debug:
            print(f"[TG] CA bundle not found: {ca_path}")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            body = response.read()
    except urllib.error.HTTPError as e:
        if debug:
            try:
                error_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                error_body = ""
            print(f"[TG] HTTP error {e.code}. Body={error_body}")
        return False
    except Exception as e:
        if debug:
            print(f"[TG] Request failed: {e}")
        return False

    try:
        data = json.loads(body.decode("utf-8"))
    except Exception as e:
        if debug:
            print(f"[TG] Invalid JSON response: {e}")
        return False

    ok = bool(data.get("ok"))
    if not ok and debug:
        print(f"[TG] API error: {data}")
    return ok
