"""轻量 SMTP 邮件发送（注册验证码 + 密码找回验证码）。未配置 SMTP_HOST 时 graceful degrade：log 验证码到 stdout。"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


def _smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


def send_verification_code_email(to_email: str, code: str, purpose: str = "RESET_PASSWORD") -> bool:
    """发送验证码邮件。purpose: REGISTER / RESET_PASSWORD。SMTP 未配置时打印验证码到日志并返回 False。"""
    if not _smtp_configured():
        logger.warning(
            "SMTP 未配置，跳过邮件发送 (to=%s, code=%s, purpose=%s)",
            to_email, code, purpose,
        )
        return False

    if purpose == "REGISTER":
        subject = "Registration Verification Code - Matgo"
        heading = "Registration Verification Code"
        text_intro = "Your Matgo registration verification code is:"
    else:
        subject = "Password Reset Code - Matgo"
        heading = "Password Reset Code"
        text_intro = "Your Matgo password reset verification code is:"

    expire_minutes = settings.VERIFICATION_CODE_EXPIRE_MINUTES

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to_email

    text = f"""\
{text_intro} {code}

This code expires in {expire_minutes} minutes. If you did not request this, please ignore this email.
"""

    html = f"""\
<div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 24px;">
  <h2 style="color: #0D4D4D; margin-bottom: 16px;">{heading}</h2>
  <p style="color: #333; line-height: 1.6;">
    {text_intro}
  </p>
  <div style="text-align: center; margin: 28px 0;">
    <div style="display: inline-block; padding: 16px 40px; background: #f5f5f5; border-radius: 12px;
                font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #0D4D4D;">
      {code}
    </div>
  </div>
  <p style="color: #888; font-size: 13px; line-height: 1.5;">
    This code expires in {expire_minutes} minutes.<br>
    If you did not request this, please ignore this email.
  </p>
  <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
  <p style="color: #aaa; font-size: 11px;">Matgo — East Africa Building Materials Supply Chain</p>
</div>
"""

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            if settings.SMTP_USE_TLS:
                server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())
        server.quit()
        logger.info("验证码邮件已发送 to=%s purpose=%s", to_email, purpose)
        return True
    except Exception:
        logger.exception("验证码邮件发送失败 to=%s purpose=%s", to_email, purpose)
        return False
