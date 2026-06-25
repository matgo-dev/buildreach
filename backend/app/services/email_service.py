"""SMTP 邮件发送服务。"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)

# 验证码邮件模板(三语)
_TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        "subject": "Your BuildLink verification code: {code}",
        "body_text": (
            "Hi,\n\n"
            "Your verification code is: {code}\n\n"
            "This code will expire in {minutes} minutes.\n"
            "If you did not request this code, please ignore this email.\n\n"
            "— BuildLink Team"
        ),
        "body_html": (
            "<div style='font-family:Arial,sans-serif;max-width:480px;margin:0 auto;'>"
            "<h2 style='color:#1a1a1a;'>BuildLink Verification Code</h2>"
            "<p>Hi,</p>"
            "<p>Your verification code is:</p>"
            "<p style='font-size:32px;font-weight:bold;letter-spacing:8px;"
            "color:#2563eb;margin:24px 0;'>{code}</p>"
            "<p>This code will expire in {minutes} minutes.</p>"
            "<p style='color:#666;font-size:13px;'>If you did not request this code, "
            "please ignore this email.</p>"
            "<hr style='border:none;border-top:1px solid #eee;margin:24px 0;'/>"
            "<p style='color:#999;font-size:12px;'>— BuildLink Team</p>"
            "</div>"
        ),
    },
    "zh": {
        "subject": "您的 BuildLink 验证码：{code}",
        "body_text": (
            "您好，\n\n"
            "您的验证码是：{code}\n\n"
            "验证码将在 {minutes} 分钟后过期。\n"
            "如果您没有请求此验证码，请忽略此邮件。\n\n"
            "— BuildLink 团队"
        ),
        "body_html": (
            "<div style='font-family:Arial,sans-serif;max-width:480px;margin:0 auto;'>"
            "<h2 style='color:#1a1a1a;'>BuildLink 验证码</h2>"
            "<p>您好，</p>"
            "<p>您的验证码是：</p>"
            "<p style='font-size:32px;font-weight:bold;letter-spacing:8px;"
            "color:#2563eb;margin:24px 0;'>{code}</p>"
            "<p>验证码将在 {minutes} 分钟后过期。</p>"
            "<p style='color:#666;font-size:13px;'>如果您没有请求此验证码，"
            "请忽略此邮件。</p>"
            "<hr style='border:none;border-top:1px solid #eee;margin:24px 0;'/>"
            "<p style='color:#999;font-size:12px;'>— BuildLink 团队</p>"
            "</div>"
        ),
    },
    "sw": {
        "subject": "Nambari yako ya uthibitisho ya BuildLink: {code}",
        "body_text": (
            "Habari,\n\n"
            "Nambari yako ya uthibitisho ni: {code}\n\n"
            "Nambari hii itaisha baada ya dakika {minutes}.\n"
            "Ikiwa hukuomba nambari hii, tafadhali puuza barua pepe hii.\n\n"
            "— Timu ya BuildLink"
        ),
        "body_html": (
            "<div style='font-family:Arial,sans-serif;max-width:480px;margin:0 auto;'>"
            "<h2 style='color:#1a1a1a;'>Nambari ya Uthibitisho ya BuildLink</h2>"
            "<p>Habari,</p>"
            "<p>Nambari yako ya uthibitisho ni:</p>"
            "<p style='font-size:32px;font-weight:bold;letter-spacing:8px;"
            "color:#2563eb;margin:24px 0;'>{code}</p>"
            "<p>Nambari hii itaisha baada ya dakika {minutes}.</p>"
            "<p style='color:#666;font-size:13px;'>Ikiwa hukuomba nambari hii, "
            "tafadhali puuza barua pepe hii.</p>"
            "<hr style='border:none;border-top:1px solid #eee;margin:24px 0;'/>"
            "<p style='color:#999;font-size:12px;'>— Timu ya BuildLink</p>"
            "</div>"
        ),
    },
}


def _get_template(locale: str) -> dict[str, str]:
    # 只取前两位匹配语言(zh-CN → zh)
    lang = locale[:2] if locale else "en"
    return _TEMPLATES.get(lang, _TEMPLATES["en"])


def send_verification_email(
    to_email: str,
    code: str,
    locale: str = "en",
) -> None:
    """同步发送验证码邮件。调用方应在线程池中执行以避免阻塞事件循环。"""
    if not settings.SMTP_HOST:
        logger.warning("SMTP not configured, skipping email to %s", to_email)
        return

    tpl = _get_template(locale)
    minutes = settings.VERIFICATION_CODE_EXPIRE_MINUTES

    msg = MIMEMultipart("alternative")
    msg["Subject"] = tpl["subject"].format(code=code)
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = to_email

    msg.attach(MIMEText(tpl["body_text"].format(code=code, minutes=minutes), "plain", "utf-8"))
    msg.attach(MIMEText(tpl["body_html"].format(code=code, minutes=minutes), "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())
        logger.info("Verification email sent to %s", to_email)
    except Exception:
        logger.exception("Failed to send verification email to %s", to_email)
        raise
