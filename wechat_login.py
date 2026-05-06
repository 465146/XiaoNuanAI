"""微信扫码登录 — 每个网站用户独立连接自己的微信 bot。"""
import io
import json
import time
import threading
import uuid
from datetime import datetime
from pathlib import Path

import httpx
import qrcode
from PIL import Image, ImageDraw

# WeChat ilink API
ILINK_BASE = "https://ilinkai.weixin.qq.com"
ILINK_APP_ID = "bot"
ILINK_CLIENT_VERSION = "131335"
BOT_TYPE = "3"
QR_POLL_TIMEOUT_MS = 35_000

COMMON_HEADERS = {
    "iLink-App-Id": ILINK_APP_ID,
    "iLink-App-ClientVersion": ILINK_CLIENT_VERSION,
}

_active_logins: dict[str, dict] = {}


def _fetch_qrcode() -> dict:
    """获取微信登录二维码"""
    resp = httpx.get(
        f"{ILINK_BASE}/ilink/bot/get_bot_qrcode?bot_type={BOT_TYPE}",
        headers=COMMON_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _poll_qrcode_status(qrcode_token: str) -> dict:
    """轮询扫码状态"""
    try:
        resp = httpx.get(
            f"{ILINK_BASE}/ilink/bot/get_qrcode_status?qrcode={qrcode_token}",
            headers=COMMON_HEADERS,
            timeout=QR_POLL_TIMEOUT_MS / 1000 + 5,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.ReadTimeout:
        return {"status": "wait"}
    except Exception:
        return {"status": "wait"}


def start_login() -> dict:
    """为用户启动微信扫码登录"""
    sid = str(uuid.uuid4())[:8]
    _active_logins[sid] = {
        "status": "starting",
        "qrcode_img_url": None,
        "qrcode_token": None,
        "message": "正在获取二维码...",
        "started_at": datetime.now().isoformat(),
    }

    try:
        qr_data = _fetch_qrcode()
        qrcode_img_url = qr_data.get("qrcode_img_content", "")
        qrcode_token = qr_data.get("qrcode", "")

        if not qrcode_img_url:
            _active_logins[sid]["status"] = "error"
            _active_logins[sid]["message"] = "获取二维码失败"
            return {"session_id": sid, "status": "error", "message": "获取二维码失败"}

        _active_logins[sid]["qrcode_img_url"] = qrcode_img_url
        _active_logins[sid]["qrcode_token"] = qrcode_token
        _active_logins[sid]["status"] = "waiting_scan"
        _active_logins[sid]["message"] = "请用微信扫描二维码"
    except Exception as e:
        _active_logins[sid]["status"] = "error"
        _active_logins[sid]["message"] = str(e)
        return {"session_id": sid, "status": "error", "message": str(e)}

    # 后台轮询
    def _poll():
        try:
            token = qrcode_token
            img_url = qrcode_img_url
            refresh_count = 0
            scanned = False

            while True:
                status_data = _poll_qrcode_status(token)
                status = status_data.get("status", "wait")

                if status == "scaned":
                    if not scanned:
                        _active_logins[sid]["status"] = "scanned"
                        _active_logins[sid]["message"] = "已扫码，请在微信中确认授权..."
                        scanned = True

                elif status == "confirmed":
                    bot_token = status_data.get("bot_token", "")
                    ilink_bot_id = status_data.get("ilink_bot_id", "")
                    ilink_user_id = status_data.get("ilink_user_id", "")
                    base_url = status_data.get("baseurl", ILINK_BASE)

                    _active_logins[sid].update({
                        "status": "connected",
                        "message": "微信连接成功！",
                        "bot_token": bot_token,
                        "bot_id": ilink_bot_id,
                        "user_id": ilink_user_id,
                        "base_url": base_url,
                    })
                    return

                elif status == "expired":
                    refresh_count += 1
                    if refresh_count > 3:
                        _active_logins[sid]["status"] = "expired"
                        _active_logins[sid]["message"] = "二维码多次过期，请重试"
                        return
                    qr_data = _fetch_qrcode()
                    img_url = qr_data.get("qrcode_img_content", "")
                    token = qr_data.get("qrcode", "")
                    _active_logins[sid]["qrcode_img_url"] = img_url
                    _active_logins[sid]["qrcode_token"] = token
                    _active_logins[sid]["status"] = "waiting_scan"
                    _active_logins[sid]["message"] = "二维码已刷新，请重新扫描"
                    scanned = False

                time.sleep(2)
        except Exception as e:
            _active_logins[sid]["status"] = "error"
            _active_logins[sid]["message"] = str(e)

    threading.Thread(target=_poll, daemon=True).start()
    return {"session_id": sid, "status": "waiting_scan", "message": "请用微信扫描二维码"}


def get_login_status(sid: str) -> dict:
    """查询登录状态"""
    login = _active_logins.get(sid)
    if not login:
        return {"status": "not_found", "message": "会话不存在或已过期"}
    return {
        "session_id": sid,
        "status": login["status"],
        "message": login.get("message", ""),
        "bot_token": login.get("bot_token"),
        "bot_id": login.get("bot_id"),
        "wechat_user_id": login.get("user_id"),
        "base_url": login.get("base_url"),
    }


def get_qrcode_image(sid: str) -> bytes | None:
    """生成二维码 PNG 图片（编码 liteapp 链接）"""
    login = _active_logins.get(sid)
    if not login or not login.get("qrcode_img_url"):
        return None
    # qrcode_img_url 是微信 liteapp 链接，需要编码为二维码
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(login["qrcode_img_url"])
    qr.make(fit=True)
    img = qr.make_image(fill_color="#FF8C42", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


# ── Gateway 账号持久化 ──

def _normalize_bot_id(ilink_bot_id: str) -> str:
    """ilink_bot_id: 'xxx@im.bot' → 文件名安全: 'xxx-im-bot'"""
    return ilink_bot_id.replace("@", "-")


def save_bot_to_gateway(bot_token: str, ilink_bot_id: str, ilink_user_id: str, base_url: str):
    """保存 bot 凭据到 Gateway 账号目录"""
    accounts_dir = Path.home() / ".openclaw" / "openclaw-weixin" / "accounts"
    accounts_dir.mkdir(parents=True, exist_ok=True)

    normalized_id = _normalize_bot_id(ilink_bot_id)

    # 写入账号文件
    account_file = accounts_dir / f"{normalized_id}.json"
    account_data = {
        "token": bot_token,
        "savedAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "baseUrl": base_url,
        "userId": ilink_user_id,
    }
    account_file.write_text(json.dumps(account_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # 更新索引
    index_file = accounts_dir / "accounts.json"
    existing = []
    if index_file.exists():
        try:
            existing = json.loads(index_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, KeyError):
            pass
    if normalized_id not in existing:
        existing.append(normalized_id)
    index_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    return normalized_id


def get_active_bot_info() -> dict | None:
    """检查是否有已连接的 Gateway bot"""
    accounts_dir = Path.home() / ".openclaw" / "openclaw-weixin" / "accounts"
    if not accounts_dir.exists():
        return None
    for f in accounts_dir.glob("*.json"):
        name = f.name
        if name == "accounts.json" or ".context-tokens" in name or ".sync" in name:
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("token"):
                return {
                    "connected": True,
                    "account_id": f.stem,
                    "user_id": data.get("userId", ""),
                    "connected_at": data.get("savedAt", ""),
                }
        except (json.JSONDecodeError, KeyError):
            pass
    return None
