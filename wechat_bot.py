"""每个用户独立的微信 bot 管理。直连 ilink API 收发消息。"""
import json
import time
import threading
import uuid
import httpx
from datetime import datetime

import database as db
import cbt_agent as agent

ILINK_BASE = "https://ilinkai.weixin.qq.com"
COMMON_HEADERS = {"iLink-App-Id": "bot", "iLink-App-ClientVersion": "131335"}
CHANNEL_VERSION = "2.1.7"

_running_bots: dict[int, threading.Thread] = {}


def _build_headers(bot_token: str) -> dict:
    return {
        **COMMON_HEADERS,
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
    }


def _post(route: str, body: dict, bot_token: str, timeout: int = 30) -> dict | None:
    try:
        h = _build_headers(bot_token)
        h["Authorization"] = f"Bearer {bot_token}"
        r = httpx.post(
            f"{ILINK_BASE}/{route}",
            headers=h,
            json=body,
            timeout=timeout,
        )
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def _long_poll_getupdates(bot_token: str, buf: str, timeout: int = 35000) -> dict:
    """长轮询获取新消息"""
    return _post(
        "ilink/bot/getupdates",
        {"get_updates_buf": buf, "base_info": {"channel_version": CHANNEL_VERSION}},
        bot_token,
        timeout=timeout // 1000 + 5,
    ) or {"ret": -1, "msgs": []}


def _send_text_message(to_user: str, text: str, bot_token: str, context_token: str = ""):
    """发送文本消息"""
    client_id = f"openclaw-xiaonuan-{uuid.uuid4().hex[:8]}"
    return _post(
        "ilink/bot/sendmessage",
        {
            "msg": {
                "from_user_id": "",
                "to_user_id": to_user,
                "client_id": client_id,
                "message_type": 2,  # BOT
                "message_state": 2,  # FINISH
                "item_list": [{"type": 1, "text_item": {"text": text}}],
                "context_token": context_token or "",
            },
            "base_info": {"channel_version": CHANNEL_VERSION},
        },
        bot_token,
        timeout=15,
    )


def _poll_bot(user_id: int):
    """后台轮询单个 bot 的消息"""
    bot = db.get_wechat_bot(user_id)
    if not bot:
        return
    bot_token = bot["bot_token"]
    buf = ""
    poll_timeout = 35000

    while True:
        # 检查是否仍活跃
        current = db.get_wechat_bot(user_id)
        if not current or current["bot_token"] != bot_token:
            break

        try:
            resp = _long_poll_getupdates(bot_token, buf, poll_timeout)
            if resp.get("ret", 0) != 0 or resp.get("errcode", 0) != 0:
                time.sleep(2)
                continue

            buf = resp.get("get_updates_buf", buf)
            msgs = resp.get("msgs", [])
            poll_timeout = resp.get("longpolling_timeout_ms", 35000)

            for msg in msgs:
                from_user = msg.get("from_user_id", "")
                context_token = msg.get("context_token", "")
                item_list = msg.get("item_list", [])

                # 提取文本
                text = ""
                for item in item_list:
                    if item.get("type") == 1:  # TEXT
                        text = (item.get("text_item") or {}).get("text", "")
                        break
                if not text:
                    continue

                # 获取用户对话历史
                history = db.get_messages(user_id, 50)
                messages = [{"role": m["role"], "content": m["content"]} for m in history]
                messages.append({"role": "user", "content": text})

                # 调用 AI（同步，非流式）
                try:
                    reply = agent.chat_stream(messages)
                except Exception:
                    reply = "小暖现在有点忙，请稍后再发一条消息～"

                # 保存消息
                db.save_message(user_id, "user", text)
                db.save_message(user_id, "assistant", reply)

                # 回复
                _send_text_message(from_user, reply, bot_token, context_token)

        except Exception:
            time.sleep(5)


def start_bot_polling(user_id: int):
    """为指定用户启动 bot 消息轮询"""
    bot = db.get_wechat_bot(user_id)
    if not bot:
        return

    # 停止旧线程
    stop_bot_polling(user_id)

    t = threading.Thread(target=_poll_bot, args=(user_id,), daemon=True)
    t.start()
    _running_bots[user_id] = t


def stop_bot_polling(user_id: int):
    t = _running_bots.pop(user_id, None)
    if t:
        # daemon thread will die when main process exits
        pass


def start_all_bots():
    """启动时恢复所有已连接 bot 的轮询"""
    import database as _db
    try:
        with _db.get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM wechat_bots WHERE bot_token IS NOT NULL AND bot_token != ''")
                rows = cur.fetchall()
    except Exception:
        return
    for row in rows:
        start_bot_polling(row["user_id"])
