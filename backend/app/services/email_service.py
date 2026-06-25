"""轻量 SMTP 邮件发送（密码找回验证码）。未配置 SMTP_HOST 时静默跳过。"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


def _smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


def send_verification_code_email(to_email: str, code: str) -> bool:
    """发送密码重置验证码邮件。SMTP 未配置时返回 False 并 log warning + 打印验证码到日志。"""
    if not _smtp_configured():
        logger.warning("SMTP 未配置，跳过邮件发送 (to=%s, code=%s)", to_email, code)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Password Reset Code - BuildLink"
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to_email

    text = f"""\
Your BuildLink password reset verification code is: {code}

This code expires in 10 minutes. If you did not request this, please ignore this email.
"""

    html = f"""\
<div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 24px;">
  <h2 style="color: #0D4D4D; margin-bottom: 16px;">Password Reset Code</h2>
  <p style="color: #333; line-height: 1.6;">
    Your verification code is:
  </p>
  <div style="text-align: center; margin: 28px 0;">
    <div style="display: inline-block; padding: 16px 40px; background: #f5f5f5; border-radius: 12px;
                font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #0D4D4D;">
      {code}
    </div>
  </div>
  <p style="color: #888; font-size: 13px; line-height: 1.5;">
    This code expires in 10 minutes.<br>
    If you did not request this, please ignore this email.
  </p>
  <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
  <p style="color: #aaa; font-size: 11px;">BuildLink — East Africa Construction Supply Chain</p>
</div>
"""

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        if settings.SMTP_USE_TLS:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())
        server.quit()
        logger.info("验证码邮件已发送 to=%s", to_email)
        return True
    except Exception:
        logger.exception("验证码邮件发送失败 to=%s", to_email)
        return False
