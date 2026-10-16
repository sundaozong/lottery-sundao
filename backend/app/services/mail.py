"""SMTP 邮件推送。"""
from __future__ import annotations
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ..config import get_settings


def smtp_configured() -> bool:
    s = get_settings()
    return bool(s.smtp_host and (s.smtp_from or s.smtp_user))


def send_mail(to: str, subject: str, body: str) -> dict:
    s = get_settings()
    if not smtp_configured():
        return {
            "ok": False,
            "error": "未配置 SMTP。请在 .env 中设置 SMTP_HOST / SMTP_USER / SMTP_PASSWORD / SMTP_FROM 后重试。",
        }
    if not to:
        return {"ok": False, "error": "未指定收件人。请在设置中填写邮箱或传入 to。"}
    msg = MIMEMultipart()
    msg["From"] = s.smtp_from or s.smtp_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    try:
        if s.smtp_tls:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as server:
                server.starttls()
                if s.smtp_user:
                    server.login(s.smtp_user, s.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as server:
                if s.smtp_user:
                    server.login(s.smtp_user, s.smtp_password)
                server.send_message(msg)
        return {"ok": True, "message": f"已发送至 {to}"}
    except Exception as e:
        return {"ok": False, "error": f"发送失败: {type(e).__name__}: {e}"}


def send_draw_digest(to: str, draws: list[dict]) -> dict:
    lines = ["【孙导带你夜夜笙歌】开奖摘要", "", "以下为本地最新开奖（请以官方为准）：", ""]
    for d in draws:
        lines.append(f"- {d.get('name', d.get('lottery_type'))} 第{d.get('issue')}期: {d.get('numbers_text', d.get('numbers'))}")
    lines += ["", "本邮件由个人观测站自动发送，仅供参考。"]
    return send_mail(to, "开奖推送 · 孙导带你夜夜笙歌", "\n".join(lines))
