import json
import os
from datetime import datetime
from openai import OpenAI

def _load_deepseek_key() -> str:
    """读取全局默认 API Key（项目 .env > 环境变量）"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("DEEPSEEK_API_KEY="):
                    return line.split("=", 1)[1]
    return os.environ.get("DEEPSEEK_API_KEY", "")


DEEPSEEK_API_KEY = _load_deepseek_key()
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"

# AGENTS.md 和知识库路径（项目自包含，不依赖外部 OpenClaw）
_AGENT_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_data")


def _load_file(path: str) -> str:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def build_system_prompt(user_prefs: dict | None = None, memory_context: str = "") -> str:
    """从 agent_data/ 构建 System Prompt，可选附加 Gateway 记忆"""
    agents = _load_file(os.path.join(_AGENT_DATA, "AGENTS.md"))
    cbt = _load_file(os.path.join(_AGENT_DATA, "knowledge", "cbt-core.md"))
    anxiety = _load_file(os.path.join(_AGENT_DATA, "knowledge", "anxiety-coping.md"))
    sleep = _load_file(os.path.join(_AGENT_DATA, "knowledge", "sleep-guide.md"))
    mindfulness = _load_file(
        os.path.join(_AGENT_DATA, "knowledge", "mindfulness-intro.md")
    )

    prompt = f"""{agents}

---
## 专业知识库

### CBT 核心概念：认知扭曲
{cbt}

### 焦虑应对策略
{anxiety}

### 睡眠改善指南
{sleep}

### 正念冥想入门
{mindfulness}
"""

    if user_prefs:
        name = user_prefs.get("display_name", "")
        goals = user_prefs.get("goals", "")
        triggers = user_prefs.get("triggers", "")
        coping = user_prefs.get("coping_strategies", "")
        parts = []
        if name:
            parts.append(f"用户称呼：{name}")
        if goals:
            parts.append(f"用户目标：{goals}")
        if triggers:
            parts.append(f"情绪触发点：{triggers}")
        if coping:
            parts.append(f"惯用应对方式：{coping}")
        if parts:
            prompt += f"""
---
## 用户个人档案（可在对话中自然引用）
{chr(10).join(parts)}
"""

    if memory_context:
        prompt += f"""
---
## 近期对话记忆（由 Gateway 记忆系统提供）
{memory_context}
"""

    prompt += f"""
---
## 当前时间
{datetime.now().strftime("%Y年%m月%d日 %H:%M")}
"""
    return prompt


def evaluate_emotion(user_message: str) -> float:
    """简单的情绪评估（基于关键词），返回 0-1 的分数"""
    crisis_words = ["自杀", "想死", "不想活", "自残", "伤害自己", "结束生命", "活不下去"]
    severe_words = ["崩溃", "绝望", "撑不住", "受不了", "痛苦", "无助", "好累", "活着好累"]
    moderate_words = [
        "焦虑", "压力", "烦躁", "失眠", "睡不着", "迷茫", "难过", "低落", "害怕", "担心"
    ]
    mild_words = ["累了", "无聊", "没劲", "不太开心", "郁闷", "没意思"]

    msg = user_message.lower()
    if any(w in msg for w in crisis_words):
        return 0.95
    if any(w in msg for w in severe_words):
        return 0.75
    if any(w in msg for w in moderate_words):
        return 0.55
    if any(w in msg for w in mild_words):
        return 0.35
    return 0.1


def check_behavior_flags(user_message: str) -> dict:
    """检查行为特征（睡眠/食欲/社交）"""
    msg = user_message
    flags = {"sleep": False, "appetite": False, "social": False}

    sleep_words = ["失眠", "睡不着", "入睡困难", "早醒", "睡太多", "睡不好", "熬夜"]
    appetite_words = ["吃不下", "暴食", "没胃口", "吃太多", "不想吃"]
    social_words = ["不想见人", "不想说话", "不想出门", "躲着", "社恐"]

    if any(w in msg for w in sleep_words):
        flags["sleep"] = True
    if any(w in msg for w in appetite_words):
        flags["appetite"] = True
    if any(w in msg for w in social_words):
        flags["social"] = True

    return flags


def calculate_daily_score(
    user_messages: list[str],
    phq9_score: int | None = None,
) -> float:
    """计算每日情绪加权分"""
    combined = " ".join(user_messages)

    # 维度一：量表分（权重 40%）
    scale_score = (phq9_score / 27) if phq9_score is not None else 0.5

    # 维度二：对话情绪（权重 30%）
    emotion_score = evaluate_emotion(combined)

    # 维度三：行为特征（权重 30%）
    flags = check_behavior_flags(combined)
    behavior_score = 0
    if flags["sleep"]:
        behavior_score += 0.1
    if flags["appetite"]:
        behavior_score += 0.1
    if flags["social"]:
        behavior_score += 0.1

    total = scale_score * 0.4 + emotion_score * 0.3 + behavior_score * 0.3
    return round(total, 3)


def get_deepseek_client() -> OpenAI:
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


def chat_stream(messages: list[dict]) -> str:
    """调用 DeepSeek API，返回完整回复"""
    client = get_deepseek_client()
    system_prompt = build_system_prompt()

    api_messages = [{"role": "system", "content": system_prompt}]
    for m in messages:
        api_messages.append({"role": m["role"], "content": m["content"]})

    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=api_messages,
        temperature=0.85,
        max_tokens=1024,
    )
    return response.choices[0].message.content


# OpenClaw Gateway 地址
GATEWAY_URL = "http://127.0.0.1:18789"

# Gateway 工作区记忆目录（同一容器内可直接写文件）
import pathlib
GATEWAY_MEMORY_DIR = pathlib.Path(__file__).resolve().parent / "gateway" / "workspace" / "cbt" / "memory"

# 触发 Gateway 路由的关键词（skills 相关）
GATEWAY_KEYWORDS = [
    # 音乐类关键词不通过 Gateway（由 Python 音乐搜索 API 处理）
]

MUSIC_KEYWORDS = [
    "网易云", "云音乐", "放歌", "放首歌", "播放", "点歌", "听歌",
    "来首歌", "下一首", "上一首", "搜歌", "找歌", "推荐歌", "歌单",
    "红心", "音乐", "ncm", "neteasy",
    "点首", "点一", "播首", "播一", "来首", "来一", "推荐首",
    "唱首", "唱一", "弹首", "弹一", "想听", "我要听", "给我放",
]


def _detect_music_query(messages: list[dict]) -> str | None:
    """检测最新用户消息是否为音乐请求，返回搜索关键词"""
    # 只看最新一条用户消息
    for m in reversed(messages):
        if m["role"] != "user":
            continue
        msg = m["content"]
        if not any(kw in msg for kw in MUSIC_KEYWORDS):
            return None  # 最近一条不是音乐请求，直接返回
        for kw in ["放首歌", "放首", "放歌", "播放", "点歌", "听歌", "搜歌",
                     "点首", "点一首", "播首", "来首", "来一首", "唱首",
                     "想听", "我要听", "给我放", "推荐"]:
            if kw in msg:
                parts = msg.split(kw, 1)
                after = parts[-1].strip().rstrip("。！？,!?~～的吧《》\"'")
                # 提取有意义的关键词（至少2个字符）
                # 有效的搜索词至少3个字且不能只是代词/助词
                stop = {"帮我", "我想", "我要", "给我", "来一", "随便", "一首", "来个", "一个"}
                if len(after) >= 3 and after not in stop:
                    return after
                return "热歌榜 华语"
        return "热歌榜"
    return None


def _search_music(keyword: str) -> list[dict]:
    """搜索网易云音乐歌曲，返回带 ID 的结果"""
    import urllib.request
    import urllib.parse
    q = urllib.parse.quote(keyword.strip().strip("《》\"'「」"))
    url = f"https://netease-cloud-music-api-eta.vercel.app/search?keywords={q}&limit=3"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "XiaoNuan/1.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read())
        songs = data.get("result", {}).get("songs", [])
        results = []
        for s in songs[:3]:
            results.append({
                "id": str(s.get("id", "")),
                "name": s.get("name", ""),
                "artist": ", ".join(a.get("name", "") for a in s.get("artists", [])),
            })
        return results
    except Exception:
        return []


def _gateway_available() -> bool:
    """检测 Gateway 是否可用"""
    try:
        import urllib.request
        req = urllib.request.Request(f"{GATEWAY_URL}/health")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def _needs_gateway(messages: list[dict]) -> bool:
    """判断用户消息是否需要用 Gateway（有 skill 需求时）"""
    for m in reversed(messages):
        if m["role"] == "user":
            msg = m["content"].lower()
            return any(kw in msg for kw in GATEWAY_KEYWORDS)
    return False


async def chat_stream_async(messages: list[dict], user_prefs: dict | None = None, user_id: int = 0):
    """异步流式调用 AI。

    优先通过 OpenClaw Gateway（支持 skills、agent 记忆、微信渠道），
    Gateway 不可用时 fallback 到直接调用大模型 API。
    日常对话走 DeepSeek 直连（快），技能请求走 Gateway（功能全）。
    """
    import httpx

    prefs = user_prefs or {}
    memory_context = load_gateway_memories(user_id) if user_id else ""
    use_gateway = _needs_gateway(messages) and _gateway_available()

    if use_gateway:
        try:
            # ── 走 OpenClaw Gateway（skills 模式）──
            api_key = prefs.get("api_key") or DEEPSEEK_API_KEY
            model = "openclaw/cbt"

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            }
            api_messages = list(messages)
            if prefs.get("goals") or prefs.get("display_name"):
                context_parts = []
                if prefs.get("display_name"):
                    context_parts.append(f"用户称呼：{prefs['display_name']}")
                if prefs.get("goals"):
                    context_parts.append(f"用户目标：{prefs['goals']}")
                if prefs.get("triggers"):
                    context_parts.append(f"情绪触发点：{prefs['triggers']}")
                api_messages.insert(0, {"role": "system", "content": "\n".join(context_parts)})

            payload = {
                "model": model,
                "messages": api_messages,
                "temperature": 0.85,
                "max_tokens": 1024,
                "stream": True,
            }

            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream(
                    "POST",
                    f"{GATEWAY_URL}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    got_content = False
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str.strip() == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    got_content = True
                                    yield content
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue
                    if got_content:
                        return
                    # Gateway 返回了空响应（可能 agent 未加载），走 fallback
        except Exception:
            pass
        # Gateway 失败 → 继续走下面的 DeepSeek 直连

    # ── Fallback: 直接调用大模型 API（带记忆上下文）──
    system_prompt = build_system_prompt(user_prefs, memory_context)

    # 音乐请求：搜歌 + 注入结果（try/except 确保不影响聊天）
    try:
        music_query = _detect_music_query(messages)
        if music_query:
            songs = _search_music(music_query)
            if songs:
                song_lines = []
                for s in songs[:3]:
                    sid = s.get("id", "")
                    name = s.get("name", "")
                    artist = s.get("artist", "")
                    song_lines.append(f"- {name} — {artist}\n  https://music.163.com/#/song?id={sid}")
                system_prompt += "\n\n【系统指令】用户想听歌，已搜索到以下歌曲。请自然地推荐这些歌曲并在回复中附带以下链接：\n" + "\n".join(song_lines) + "\n\n只推荐1-2首，口吻温暖。不要用Markdown链接格式，直接给网址。"
    except Exception:
        pass

    api_messages = [{"role": "system", "content": system_prompt}]
    for m in messages:
        api_messages.append({"role": m["role"], "content": m["content"]})

    api_key = prefs.get("api_key") or DEEPSEEK_API_KEY
    base_url = prefs.get("api_base_url") or DEEPSEEK_BASE_URL
    model = prefs.get("api_model") or DEEPSEEK_MODEL

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    payload = {
        "model": model,
        "messages": api_messages,
        "temperature": 0.85,
        "max_tokens": 1024,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST",
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue


# ── 记忆同步到 Gateway ──

def sync_memory_to_gateway(user_id: int, summary: str, date_str: str = ""):
    """将对话摘要写入 Gateway 工作区记忆目录。
    Gateway 的 mengram 插件会自动索引这些文件。
    """
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    try:
        GATEWAY_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        filename = GATEWAY_MEMORY_DIR / f"user_{user_id}_{date_str}.md"
        content = f"""# 用户 {user_id} - {date_str} 情绪摘要

{summary}

---
*由小暖 CBT 系统自动生成*
"""
        filename.write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False


def load_gateway_memories(user_id: int, days: int = 7) -> str:
    """读取 Gateway 工作区中的历史记忆，用于增强 System Prompt"""
    try:
        if not GATEWAY_MEMORY_DIR.exists():
            return ""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        parts = []
        for f in sorted(GATEWAY_MEMORY_DIR.glob(f"user_{user_id}_*.md")):
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime >= cutoff:
                parts.append(f.read_text(encoding="utf-8"))
        return "\n\n---\n".join(parts) if parts else ""
    except Exception:
        return ""


async def generate_conversation_summary(messages: list[dict], api_key: str = "", base_url: str = "") -> str:
    """用 AI 生成对话摘要（100 字以内）"""
    import httpx
    key = api_key or DEEPSEEK_API_KEY
    url = base_url or DEEPSEEK_BASE_URL
    conversation = "\n".join(
        f"{'用户' if m['role'] == 'user' else '助手'}: {m['content'][:200]}"
        for m in messages[-30:]
    )
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{url}/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个简洁的心理摘要助手。用一段话（不超过100字）总结用户最近的对话：主要话题、情绪变化、值得关注的点。用中文。",
                    },
                    {"role": "user", "content": f"最近对话：\n{conversation}\n\n请生成摘要。"},
                ],
                "temperature": 0.5,
                "max_tokens": 256,
            },
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
