import io
import json
import random
import time
import sys
from datetime import datetime, date

from fastapi import FastAPI, Request, HTTPException, Query, Depends
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import database as db
import cbt_agent as agent
from auth import hash_password, verify_password, create_token, get_current_user

# 以下模块在 Railway 上可能缺依赖，安全导入
try:
    import qrcode
except ImportError:
    qrcode = None

try:
    import preferences as prefs
except ImportError:
    prefs = None

try:
    import verification as verify
except ImportError:
    verify = None

try:
    import wechat_login as wxlogin
except ImportError:
    wxlogin = None

try:
    import wechat_bot
except ImportError:
    wechat_bot = None

app = FastAPI(title="小暖 CBT 心理陪伴", version="1.1.0")


@app.on_event("startup")
async def startup_event():
    """后台任务：恢复微信 bot 轮询 + 记忆摘要"""
    import threading
    if wechat_bot:
        t = threading.Thread(target=wechat_bot.start_all_bots, daemon=True)
        t.start()
    t2 = threading.Thread(target=_memory_summary_loop, daemon=True)
    t2.start()


# ── 后台记忆摘要 ──

_last_summary_check: dict[int, int] = {}  # user_id -> last summarized max message id


def _memory_summary_loop():
    """每 5 分钟检查是否有足够新消息需要摘要，然后同步到 Gateway 记忆系统"""
    import asyncio
    SUMMARY_INTERVAL = 300  # 5 分钟
    MIN_NEW_MSG = 15        # 至少 15 条新消息才触发摘要

    async def _do_summary(uid: int, username: str):
        try:
            history = db.get_messages(uid, 60)
            if len(history) < MIN_NEW_MSG:
                return
            user_prefs = prefs.get_preferences(username) if prefs else {}
            api_key = user_prefs.get("api_key") or agent.DEEPSEEK_API_KEY
            base_url = user_prefs.get("api_base_url") or agent.DEEPSEEK_BASE_URL
            messages = [{"role": m["role"], "content": m["content"]} for m in history[-30:]]
            summary = await agent.generate_conversation_summary(messages, api_key, base_url)
            today = date.today().isoformat()
            agent.sync_memory_to_gateway(uid, summary, today)
            last_id = db.get_last_message_id(uid)
            _last_summary_check[uid] = last_id
        except Exception:
            pass

    while True:
        time.sleep(SUMMARY_INTERVAL)
        try:
            # 检查所有有消息的用户
            with db.get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT DISTINCT u.id, u.username FROM users u "
                        "JOIN messages m ON m.user_id = u.id"
                    )
                    users = cur.fetchall()
            for u in users:
                uid = u["id"]
                last_id = db.get_last_message_id(uid)
                prev = _last_summary_check.get(uid, 0)
                if last_id - prev >= MIN_NEW_MSG:
                    asyncio.run(_do_summary(uid, u["username"]))
        except Exception:
            pass

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# PHQ-9 题目
phq9_questions = [
    "做事时提不起劲或没有兴趣",
    "感到心情低落、沮丧或绝望",
    "入睡困难、睡不安稳或睡得太多",
    "感觉疲倦或没有活力",
    "食欲不振或吃得太多",
    "觉得自己很糟，或觉得自己很失败，或让自己和家人失望",
    "对事物专注有困难，例如阅读报纸或看电视时",
    "动作或说话速度缓慢到别人已察觉，或烦躁不安、动来动去",
    "有不如死掉或用某种方式伤害自己的念头",
]
phq9_sessions: dict[str, dict] = {}


# ── 页面 ──

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


# ── 认证 API ──

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str = ""
    code: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/auth/send-code")
async def send_verification_code(req: RegisterRequest):
    """发送邮箱验证码"""
    email = req.email.strip()
    if not email:
        raise HTTPException(400, "请输入邮箱地址")
    if verify is None:
        raise HTTPException(503, "邮件服务未配置")
    result = verify.send_verification_code(email)
    if not result["ok"]:
        raise HTTPException(400, result["message"])
    return result


@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    username = req.username.strip()
    password = req.password.strip()

    if len(username) < 2 or len(username) > 50:
        raise HTTPException(400, "用户名长度 2-50 个字符")
    if len(password) < 4:
        raise HTTPException(400, "密码至少 4 个字符")

    # 邮箱验证
    email = req.email.strip()
    if email:
        code = req.code.strip()
        if not code:
            raise HTTPException(400, "请输入验证码")
        if verify is None:
            raise HTTPException(503, "邮件服务未配置")
        vresult = verify.verify_code(email, code)
        if not vresult["ok"]:
            raise HTTPException(400, vresult["message"])

    existing = db.get_user_by_username(username)
    if existing:
        raise HTTPException(409, "用户名已被注册")

    user_id = db.create_user(username, hash_password(password))
    if email:
        db.update_user_email(user_id, email)
    token = create_token(user_id, username)
    return {"token": token, "user_id": user_id, "username": username}


@app.post("/api/auth/login")
async def login(req: LoginRequest):
    user = db.get_user_by_username(req.username.strip())
    if not user or not verify_password(req.password.strip(), user["password_hash"]):
        raise HTTPException(401, "用户名或密码错误")

    token = create_token(user["id"], user["username"])
    return {"token": token, "user_id": user["id"], "username": user["username"]}


@app.get("/api/auth/me")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user


# ── 用户偏好 API ──

@app.get("/api/user/preferences")
async def get_preferences(current_user: dict = Depends(get_current_user)):
    if prefs is None:
        return {}
    return prefs.get_preferences(current_user["username"])


class PreferencesUpdate(BaseModel):
    display_name: str = ""
    theme: str = ""
    timezone: str = ""
    daily_reminder: bool = True
    reminder_time: str = "21:00"
    goals: str = ""
    triggers: str = ""
    coping_strategies: str = ""
    api_key: str = ""
    api_base_url: str = "https://api.deepseek.com/v1"
    api_model: str = "deepseek-chat"


@app.put("/api/user/preferences")
async def update_preferences(req: PreferencesUpdate, current_user: dict = Depends(get_current_user)):
    if prefs is None:
        return {"ok": True}
    return prefs.save_preferences(current_user["username"], req.model_dump(exclude_unset=True))


# ── 聊天 API ──

class ChatSendRequest(BaseModel):
    message: str


@app.post("/api/chat/send")
async def chat_send(req: ChatSendRequest, current_user: dict = Depends(get_current_user)):
    user_msg = req.message.strip()
    if not user_msg:
        raise HTTPException(400, "消息不能为空")

    uid = current_user["user_id"]
    username = current_user["username"]
    db.save_message(uid, "user", user_msg)
    history = db.get_messages(uid, 100)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    user_prefs = prefs.get_preferences(username) if prefs else {}

    async def generate():
        full_reply = ""
        async for chunk in agent.chat_stream_async(messages, user_prefs, uid):
            full_reply += chunk
            yield f"data: {chunk}\n\n"
        db.save_message(uid, "assistant", full_reply)
        score = agent.calculate_daily_score([user_msg])
        db.save_daily_score(uid, date.today().isoformat(), score, "对话后自动评估")
        yield "data: [DONE]\n\n"

        # 同步对话到微信（你发的 + AI 回复，带标签区分）
        if wechat_bot:
            import threading
            def _sync():
                try:
                    bot = db.get_wechat_bot(uid)
                    if bot and bot.get("wechat_user_id") and bot.get("bot_token"):
                        wechat_bot._send_text_message(
                            bot["wechat_user_id"],
                            f"💬 你：{user_msg}",
                            bot["bot_token"],
                        )
                        wechat_bot._send_text_message(
                            bot["wechat_user_id"],
                            f"🫧 小暖：{full_reply}",
                            bot["bot_token"],
                        )
                except Exception:
                    pass
            threading.Thread(target=_sync, daemon=True).start()

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/chat/history")
async def chat_history(
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    messages = db.get_messages(current_user["user_id"], limit)
    return {"messages": messages}


@app.post("/api/chat/clear")
async def chat_clear(current_user: dict = Depends(get_current_user)):
    db.clear_messages(current_user["user_id"])
    return {"ok": True}


# ── 情绪仪表盘 API ──

@app.get("/api/mood/scores")
async def mood_scores(
    days: int = Query(30, ge=7, le=365),
    current_user: dict = Depends(get_current_user),
):
    uid = current_user["user_id"]
    scores = db.get_daily_scores(uid, days)
    phq9 = db.get_phq9_history(uid, days)
    return {"scores": scores, "phq9_history": phq9}


@app.get("/api/mood/report")
async def mood_report(current_user: dict = Depends(get_current_user)):
    scores = db.get_daily_scores(current_user["user_id"], 7)
    if not scores:
        return {"text": "还没有任何情绪记录。每天聊聊天，系统会自动帮你追踪情绪变化。"}

    dates = [r["date"].strftime("%m-%d") if hasattr(r["date"], "strftime") else str(r["date"])[5:] for r in scores]
    values = [float(r["score"]) for r in scores]
    avg = sum(values) / len(values)
    mx = max(values)
    mn = min(values)
    trend = values[-1] - values[0]

    if trend > 0.1:
        trend_msg = "本周情绪分数呈上升趋势（分数越高状态越需关注），建议多留意自己的感受。"
    elif trend < -0.1:
        trend_msg = "本周情绪分数呈下降趋势，状态在改善，继续保持。"
    else:
        trend_msg = "本周情绪分数整体平稳。"

    if avg >= 0.6:
        risk = "本周平均分数较高，强烈建议联系心理老师聊聊。"
    elif avg >= 0.35:
        risk = "本周平均分数处于中等范围，建议关注自己的状态。"
    else:
        risk = "本周情绪状态整体良好，继续保持。"

    lines = [
        "📊 本周情绪趋势报告", "=" * 40, "",
        *[f"{d} {'🔴' if v>=0.6 else '🟡' if v>=0.35 else '🟢'} {'█'*int(v*30)} {v:.2f}" for d, v in zip(dates, values)],
        "",
        f"平均分：{avg:.2f} | 最高：{mx:.2f} | 最低：{mn:.2f}",
        trend_msg, risk,
    ]
    return {"text": "\n".join(lines)}


# ── PHQ-9 API ──

@app.post("/api/phq9/start")
async def phq9_start():
    sid = f"phq9_{random.randint(10000, 99999)}"
    indices = list(range(9))
    random.shuffle(indices)
    ordered = [{"index": idx, "text": phq9_questions[idx], "score": None} for idx in indices]
    phq9_sessions[sid] = {"questions": ordered, "current": 0, "scores": [None] * 9}
    q = ordered[0]
    return {
        "session_id": sid, "current": 1, "total": 9,
        "question": q["text"],
        "options": ["完全没有", "几天", "一半以上天数", "几乎每天"],
    }


class PHQ9AnswerRequest(BaseModel):
    session_id: str
    answer: int


@app.post("/api/phq9/answer")
async def phq9_answer(req: PHQ9AnswerRequest, current_user: dict = Depends(get_current_user)):
    session = phq9_sessions.get(req.session_id)
    if not session:
        raise HTTPException(404, "会话不存在，请重新开始测试")
    if req.answer < 0 or req.answer > 3:
        raise HTTPException(400, "请回复 0、1、2 或 3")

    q = session["questions"][session["current"]]
    q["score"] = req.answer
    session["scores"][q["index"]] = req.answer
    session["current"] += 1

    if session["current"] >= 9:
        total = sum(s for s in session["scores"] if s is not None)
        q9 = session["scores"][8] or 0

        if total <= 4: severity = "none"
        elif total <= 9: severity = "mild"
        elif total <= 14: severity = "moderate"
        elif total <= 19: severity = "moderately-severe"
        else: severity = "severe"

        db.save_phq9_record(current_user["user_id"], total, severity, q9, "Web PHQ-9 测试")

        # 反馈到情绪追踪系统
        score = agent.calculate_daily_score([], phq9_score=total)
        db.save_daily_score(
            current_user["user_id"],
            date.today().isoformat(),
            score,
            f"PHQ-9: {total}/27 ({severity})",
        )

        feedback_map = {
            "none": "根据你的回答，目前情绪状态在正常范围内。生活总有起伏，这很正常。如果你想聊聊任何事，我随时在这里。",
            "mild": "结果显示你最近可能有些轻度的情绪困扰。这在压力大、睡不好时很常见。我们可以聊聊最近发生了什么，或者一起试试放松练习。如果这种感觉持续超过两周，建议和心理老师聊聊。",
            "moderate": "谢谢你的信任。结果显示你最近的情绪状态可能需要一些关注。我建议你考虑和学校的心理老师聊一聊——他们是专业的，能给你更好的支持。",
            "moderately-severe": "我有些担心你。这个分数提示你最近可能承受了很大的情绪压力。我强烈建议你和专业人士聊一聊——这不代表你软弱，恰恰说明你在积极照顾自己。",
            "severe": "我有些担心你。这个分数提示你最近可能承受了很大的情绪压力。我强烈建议你和专业人士聊一聊——这不代表你软弱，恰恰说明你在积极照顾自己。",
        }
        feedback = feedback_map[severity]

        if q9 >= 1:
            feedback += "\n\n我还注意到你提到有伤害自己的念头。这让我有些担心。生命是最宝贵的，请你一定联系专业人士聊聊。这是24小时心理援助热线：希望24热线 400-161-9995。如果你在学校，也可以直接联系心理中心。你不需要一个人面对这些。"

        del phq9_sessions[req.session_id]
        return {"completed": True, "total_score": total, "severity": severity, "q9_score": q9, "feedback": feedback}

    q_next = session["questions"][session["current"]]
    return {
        "completed": False, "current": session["current"] + 1, "total": 9,
        "question": q_next["text"],
        "options": ["完全没有", "几天", "一半以上天数", "几乎每天"],
    }


@app.get("/api/phq9/history")
async def phq9_history(
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    records = db.get_phq9_history(current_user["user_id"], limit)
    return {"records": records}


# ── 日记 API ──

@app.get("/api/diary/list")
async def diary_list(
    limit: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(get_current_user),
):
    entries = db.get_diary_list(current_user["user_id"], limit)
    return {"entries": entries}


@app.get("/api/diary/{diary_date}")
async def diary_get(diary_date: str, current_user: dict = Depends(get_current_user)):
    entry = db.get_diary(current_user["user_id"], diary_date)
    if not entry:
        raise HTTPException(404, "该日期没有日记")
    return {"entry": entry}


class DiaryGenerateRequest(BaseModel):
    date: str = ""


@app.post("/api/diary/generate")
async def diary_generate(req: DiaryGenerateRequest, current_user: dict = Depends(get_current_user)):
    today = req.date or date.today().isoformat()
    messages = db.get_messages(current_user["user_id"], 200)

    if not messages:
        return {"entry": None, "message": "今天好像还没聊什么特别的事，等有值得记录的时刻，我再帮你写成日记吧。"}

    conversation = "\n".join(
        f"{'用户' if m['role']=='user' else '小暖'}: {m['content']}" for m in messages[-30:]
    )

    user_prefs = prefs.get_preferences(current_user["username"]) if prefs else {}
    api_key = user_prefs.get("api_key") or agent.DEEPSEEK_API_KEY
    base_url = user_prefs.get("api_base_url") or agent.DEEPSEEK_BASE_URL
    model = user_prefs.get("api_model") or agent.DEEPSEEK_MODEL

    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "你是一个温暖的日记助手。根据对话内容生成一篇150-250字的第一人称情绪日记。包含：今日情绪基调 + 1-2个关键事件 + 一句鼓励或反思。用温暖口语化的中文，不要出现'根据对话'等元描述。输出JSON格式：{\"mood\": \"情绪标签\", \"content\": \"日记正文\"}",
            },
            {"role": "user", "content": f"今天的对话内容：\n{conversation}\n\n请生成今天的情绪日记。"},
        ],
        temperature=0.8,
        max_tokens=1024,
    )

    try:
        result = json.loads(response.choices[0].message.content)
        mood = result.get("mood", "日常")
        content = result.get("content", "")
    except (json.JSONDecodeError, KeyError):
        mood = "日常"
        content = response.choices[0].message.content

    db.save_diary(current_user["user_id"], today, content, mood)
    entry = db.get_diary(current_user["user_id"], today)
    return {"entry": entry}


# ── 微信配置 API ──

@app.post("/api/wechat/start-login")
async def wechat_start_login(current_user: dict = Depends(get_current_user)):
    """为当前用户生成专属微信扫码二维码"""
    if wxlogin is None:
        raise HTTPException(503, "微信服务暂不可用")
    result = wxlogin.start_login()
    return result


@app.get("/api/wechat/login-status/{session_id}")
async def wechat_login_status(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """查询扫码状态，连接成功后自动保存 bot 凭据"""
    if wxlogin is None:
        raise HTTPException(503, "微信服务暂不可用")
    status = wxlogin.get_login_status(session_id)
    # 连接成功 → 保存凭据 + 启动消息轮询
    if status.get("status") == "connected" and status.get("bot_token"):
        db.save_wechat_bot(
            current_user["user_id"],
            bot_token=status["bot_token"],
            bot_id=status["bot_id"],
            wechat_user_id=status.get("wechat_user_id", ""),
            base_url=status.get("base_url", ""),
        )
        try:
            wxlogin.save_bot_to_gateway(
                status["bot_token"], status["bot_id"],
                status.get("wechat_user_id", ""), status.get("base_url", ""),
            )
        except Exception:
            pass
        if wechat_bot:
            wechat_bot.start_bot_polling(current_user["user_id"])
    return status


@app.get("/api/wechat/login-qrcode/{session_id}")
async def wechat_login_qrcode(session_id: str):
    """生成微信扫码二维码图片（PNG）"""
    if wxlogin is None:
        raise HTTPException(503, "微信服务暂不可用")
    img_data = wxlogin.get_qrcode_image(session_id)
    if not img_data:
        raise HTTPException(404, "二维码尚未生成或已过期")
    return Response(content=img_data, media_type="image/png")


@app.get("/api/wechat/info")
async def wechat_info(current_user: dict = Depends(get_current_user)):
    """获取当前用户的微信连接状态"""
    bot = db.get_wechat_bot(current_user["user_id"])
    gateway_bots = wxlogin.get_active_bot_info() if wxlogin else None
    return {
        "connected": bot is not None,
        "bot_id": bot["bot_id"] if bot else None,
        "wechat_user_id": bot["wechat_user_id"] if bot else None,
        "connected_at": bot["connected_at"] if bot else None,
        "gateway_bots": gateway_bots is not None,
    }


class WechatConfigRequest(BaseModel):
    qrcode_url: str
    description: str = "扫描二维码，添加小暖微信，随时随地聊聊天"


@app.put("/api/config/wechat")
async def wechat_update(req: WechatConfigRequest):
    db.set_config("wechat_qrcode_url", req.qrcode_url)
    db.set_config("wechat_description", req.description)
    return {"ok": True}


@app.get("/api/health")
async def health():
    db_ok = False
    try:
        with db.get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                db_ok = True
    except Exception:
        pass
    return {
        "status": "ok",
        "time": datetime.now().isoformat(),
        "database": db_ok,
    }
