"""微信扫码登录管理。使用 Gateway 已有 weixin 插件的 bot token 认证，
确保二维码关联到 Gateway 的 bot，而非创建新的冲突会话。"""
import io
import json
import time
import threading
import uuid
from datetime import datetime
from pathlib import Path

import httpx
import qrcode

# WeChat ilink API 配置
ILINK_BASE = "https://ilinkai.weixin.qq.com"
ILINK_APP_ID = "bot"
ILINK_CLIENT_VERSION = "131335"
BOT_TYPE = "3"

COMMON_HEADERS = {
    "iLink-App-Id": ILINK_APP_ID,
    "iLink-App-ClientVersion": ILINK_CLIENT_VERSION,
}

_active_logins: dict[str, dict] = {}


def _find_bot_token() -> str | None:
    """从 Gateway weixin 插件目录读取已有 bot 的 token"""
    accounts_dir = Path.home() / ".openclaw" / "openclaw-weixin" / "accounts"
    if not accounts_dir.exists():
        return None
    for f in accounts_dir.glob("*.json"):
        name = f.name
        if name == "accounts.json" or ".context-tokens" in name or ".sync" in name:
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            token = data.get("token", "")
            if token:
                return token
        except (json.JSONDecodeError, KeyError):
            pass
    return None


def _bot_auth_headers() -> dict:
    """构建带 bot 认证的请求头"""
    token = _find_bot_token()
    headers = dict(COMMON_HEADERS)
    if token:
        # 格式: {account_id}@im.bot:{secret}
        headers["Authorization"] = f"Bot {token}"
    return headers


def _fetch_qrcode() -> dict:
    """从 WeChat API 获取二维码（带 bot 认证，关联到已有 bot）"""
    headers = _bot_auth_headers()
    resp = httpx.get(
        f"{ILINK_BASE}/ilink/bot/get_bot_qrcode?bot_type={BOT_TYPE}",
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _poll_qrcode_status(qrcode_token: str, timeout_ms: int = 35000) -> dict:
    """轮询二维码扫码状态（带 bot 认证）"""
    headers = _bot_auth_headers()
    try:
        resp = httpx.get(
            f"{ILINK_BASE}/ilink/bot/get_qrcode_status?qrcode={qrcode_token}",
            headers=headers,
            timeout=timeout_ms / 1000 + 5,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.ReadTimeout:
        return {"status": "wait"}
    except Exception:
        return {"status": "wait"}


def start_login() -> dict:
    """开始微信登录流程。使用 Gateway 已有 bot 的 token 认证，
    二维码将关联到 Gateway 的 weixin bot（而非创建新 bot）。"""
    sid = str(uuid.uuid4())[:8]
    _active_logins[sid] = {
        "status": "starting",
        "qrcode_url": None,
        "qrcode_token": None,
        "message": "正在获取二维码...",
        "started_at": datetime.now().isoformat(),
    }

    bot_token = _find_bot_token()
    if not bot_token:
        _active_logins[sid]["status"] = "error"
        _active_logins[sid]["message"] = "未检测到 Gateway weixin bot，请先启动 OpenClaw Gateway"
        return {"session_id": sid, "status": "error", "message": "未检测到 Gateway weixin bot"}

    try:
        qr_data = _fetch_qrcode()
        qrcode_url = qr_data.get("qrcode_img_content", "")
        qrcode_token = qr_data.get("qrcode", "")

        if not qrcode_url:
            _active_logins[sid]["status"] = "error"
            _active_logins[sid]["message"] = "获取二维码失败，请重试"
            return {"session_id": sid, "status": "error", "message": "获取二维码失败"}

        _active_logins[sid]["qrcode_url"] = qrcode_url
        _active_logins[sid]["qrcode_token"] = qrcode_token
        _active_logins[sid]["status"] = "waiting_scan"
        _active_logins[sid]["message"] = "请用微信扫描二维码"
    except Exception as e:
        _active_logins[sid]["status"] = "error"
        _active_logins[sid]["message"] = str(e)
        return {"session_id": sid, "status": "error", "message": str(e)}

    def _poll():
        try:
            token = qrcode_token
            url = qrcode_url
            refresh_count = 0
            max_refresh = 3
            scanned_printed = False

            while True:
                status_data = _poll_qrcode_status(token)
                status = status_data.get("status", "wait")

                if status == "scaned":
                    if not scanned_printed:
                        _active_logins[sid]["status"] = "scanned"
                        _active_logins[sid]["message"] = "已扫码，请在微信中确认授权..."
                        scanned_printed = True

                elif status == "confirmed":
                    _active_logins[sid]["status"] = "connected"
                    _active_logins[sid]["message"] = "微信连接成功！"
                    return

                elif status == "expired":
                    refresh_count += 1
                    if refresh_count > max_refresh:
                        _active_logins[sid]["status"] = "expired"
                        _active_logins[sid]["message"] = "二维码多次过期，请重试"
                        return
                    qr_data = _fetch_qrcode()
                    url = qr_data.get("qrcode_img_content", "")
                    token = qr_data.get("qrcode", "")
                    _active_logins[sid]["qrcode_url"] = url
                    _active_logins[sid]["qrcode_token"] = token
                    _active_logins[sid]["status"] = "waiting_scan"
                    _active_logins[sid]["message"] = "二维码已刷新，请重新扫描"
                    scanned_printed = False

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
        "qrcode_url": login.get("qrcode_url"),
        "message": login.get("message", ""),
    }


def get_qrcode_image(sid: str) -> bytes | None:
    """生成二维码 PNG 图片"""
    login = _active_logins.get(sid)
    if not login or not login.get("qrcode_url"):
        return None

    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(login["qrcode_url"])
    qr.make(fit=True)
    img = qr.make_image(fill_color="#FF8C42", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def get_active_bot_info() -> dict | None:
    """获取当前 Gateway weixin bot 的状态"""
    token = _find_bot_token()
    if not token:
        return None
    return {
        "connected": True,
        "account_id": token.split("@")[0] if "@" in token else "",
    }
