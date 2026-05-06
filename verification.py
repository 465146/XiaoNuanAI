"""邮箱验证码服务"""
import os
import random
import smtplib
import time
from email.mime.text import MIMEText
from datetime import datetime, timedelta

import database as db

# SMTP 配置（从环境变量或 .env 读取）
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")

CODE_LENGTH = 6
CODE_EXPIRE_MINUTES = 5
SEND_COOLDOWN = 60  # 两次发送间隔（秒）
_last_send: dict[str, float] = {}


def _generate_code() -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(CODE_LENGTH))


def _load_smtp_config():
    """从项目 .env 加载 SMTP 配置"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("SMTP_HOST="):
                    globals()["SMTP_HOST"] = line.split("=", 1)[1]
                elif line.startswith("SMTP_PORT="):
                    globals()["SMTP_PORT"] = int(line.split("=", 1)[1])
                elif line.startswith("SMTP_USER="):
                    globals()["SMTP_USER"] = line.split("=", 1)[1]
                elif line.startswith("SMTP_PASS="):
                    globals()["SMTP_PASS"] = line.split("=", 1)[1]


_load_smtp_config()


def send_verification_code(email: str) -> dict:
    """发送验证码到邮箱"""
    email = email.strip().lower()
    if not email or "@" not in email:
        return {"ok": False, "message": "请输入有效的邮箱地址"}

    # 发送冷却
    now = time.time()
    if email in _last_send and now - _last_send[email] < SEND_COOLDOWN:
        remaining = int(SEND_COOLDOWN - (now - _last_send[email]))
        return {"ok": False, "message": f"请 {remaining} 秒后再试"}

    code = _generate_code()
    expires = datetime.now() + timedelta(minutes=CODE_EXPIRE_MINUTES)

    # 保存到数据库
    db.save_verify_code(email, code, expires)

    # 发送邮件
    smtp_ok = _send_email(email, code)

    _last_send[email] = now

    if smtp_ok:
        return {"ok": True, "message": f"验证码已发送到 {email}，{CODE_EXPIRE_MINUTES} 分钟内有效"}
    else:
        # SMTP 未配置时，开发模式下显示验证码
        is_dev = not SMTP_USER or not SMTP_PASS
        msg = f"验证码已生成（{'开发模式：' if is_dev else '邮件发送失败，请联系管理员'}）"
        if is_dev:
            msg += f" 验证码：{code}"
        return {"ok": True, "message": msg, "dev_code": code if is_dev else None}


def verify_code(email: str, code: str) -> dict:
    """校验验证码"""
    email = email.strip().lower()
    code = code.strip()

    if not code or len(code) != CODE_LENGTH:
        return {"ok": False, "message": "请输入6位验证码"}

    valid = db.check_verify_code(email, code)
    if valid:
        db.mark_code_used(email, code)
        return {"ok": True, "message": "验证成功"}
    return {"ok": False, "message": "验证码错误或已过期"}


def _send_email(to: str, code: str) -> bool:
    """通过 SMTP 发送验证码邮件"""
    if not SMTP_USER or not SMTP_PASS:
        return False  # 未配置 SMTP

    try:
        msg = MIMEText(
            f"""<div style="max-width:480px;margin:0 auto;padding:32px;font-family:sans-serif;">
  <h2 style="color:#FF8C42;">🫧 小暖 · 邮箱验证</h2>
  <p>你的验证码是：</p>
  <div style="font-size:32px;font-weight:700;letter-spacing:6px;color:#FF8C42;padding:16px 0;text-align:center;">
    {code}
  </div>
  <p style="color:#999;font-size:13px;">验证码 {CODE_EXPIRE_MINUTES} 分钟内有效，请勿转发给他人。</p>
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
  <p style="color:#bbb;font-size:11px;">小暖 AI 心理陪伴伙伴</p>
</div>""",
            "html", "utf-8",
        )
        msg["Subject"] = f"小暖验证码：{code}"
        msg["From"] = f"小暖 <{SMTP_USER}>"
        msg["To"] = to

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_USER, [to], msg.as_string())
        return True
    except Exception as e:
        print(f"[SMTP] Send failed: {e}")
        return False
