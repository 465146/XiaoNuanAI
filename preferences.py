import json
import os
from datetime import datetime
from pathlib import Path

# 用户数据根目录（项目内）
USER_DATA_DIR = Path(__file__).parent / "user_data"

# 每个用户默认偏好
DEFAULT_PREFERENCES = {
    "display_name": "",
    "theme": "warm",
    "timezone": "Asia/Shanghai",
    "daily_reminder": True,
    "reminder_time": "21:00",
    "language": "zh-CN",
    "goals": "",
    "triggers": "",
    "coping_strategies": "",
    # 用户自己的大模型 API 配置
    "api_key": "",
    "api_base_url": "https://api.deepseek.com/v1",
    "api_model": "deepseek-chat",
    "created_at": "",
    "updated_at": "",
}


def _user_dir(username: str) -> Path:
    """获取用户数据目录，自动创建"""
    safe_name = "".join(c for c in username if c.isalnum() or c in "_-")
    d = USER_DATA_DIR / safe_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _prefs_path(username: str) -> Path:
    return _user_dir(username) / "preferences.json"


def get_preferences(username: str) -> dict:
    """读取用户偏好，不存在时返回默认值"""
    path = _prefs_path(username)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    prefs = {**DEFAULT_PREFERENCES, **data}
    prefs["display_name"] = prefs.get("display_name") or username
    return prefs


def save_preferences(username: str, updates: dict) -> dict:
    """保存用户偏好，只更新传入的字段"""
    current = get_preferences(username)
    # 只允许更新白名单字段
    allowed = {"display_name", "theme", "timezone", "daily_reminder",
               "reminder_time", "language", "goals", "triggers", "coping_strategies",
               "api_key", "api_base_url", "api_model"}
    for key in updates:
        if key in allowed:
            current[key] = updates[key]
    current["updated_at"] = datetime.now().isoformat()

    path = _prefs_path(username)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

    return current


def get_user_memory_dir(username: str) -> Path:
    """获取用户记忆文件目录"""
    return _user_dir(username)


def save_user_memory(username: str, date_str: str, content: str):
    """保存用户某天的记忆内容"""
    d = _user_dir(username) / "memory"
    d.mkdir(exist_ok=True)
    path = d / f"{date_str}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def get_user_memory(username: str, date_str: str) -> str:
    """读取用户某天的记忆内容"""
    path = _user_dir(username) / "memory" / f"{date_str}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def list_user_memories(username: str) -> list[str]:
    """列出用户所有记忆日期"""
    d = _user_dir(username) / "memory"
    if not d.exists():
        return []
    return sorted([p.stem for p in d.glob("*.md")], reverse=True)
