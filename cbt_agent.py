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


def build_system_prompt(user_prefs: dict | None = None) -> str:
    """从 agent_data/ 构建 System Prompt"""
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

# 触发 Gateway 路由的关键词（skills 相关）
GATEWAY_KEYWORDS = [
    "网易云", "云音乐", "放歌", "放首歌", "播放", "点歌", "听歌",
    "来首歌", "播放器", "下一首", "上一首", "暂停", "音量",
    "搜歌", "找歌", "推荐歌", "歌单", "红心", "音乐",
    "ncm", "neteasy",
]


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


async def chat_stream_async(messages: list[dict], user_prefs: dict | None = None):
    """异步流式调用 AI。

    优先通过 OpenClaw Gateway（支持 skills、agent 记忆、微信渠道），
    Gateway 不可用时 fallback 到直接调用大模型 API。
    """
    import httpx

    prefs = user_prefs or {}
    use_gateway = _needs_gateway(messages) and _gateway_available()

    if use_gateway:
        # ── 走 OpenClaw Gateway（skills 模式）──
        api_key = prefs.get("api_key") or DEEPSEEK_API_KEY
        # Gateway 使用 cbt agent，自动加载 AGENTS.md + knowledge + skills
        model = "openclaw/cbt"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        # 将用户偏好作为 system message 附加
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
        return

    # ── Fallback: 直接调用大模型 API ──
    system_prompt = build_system_prompt(user_prefs)
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
