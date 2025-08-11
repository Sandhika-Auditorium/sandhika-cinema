# app/utils/email_utils.py
from flask import current_app
from flask_mail import Message
from app.extensions import mail  # <- from extensions, not app

def _send(msg: Message, retries: int = 2, delay: float = 2.0) -> bool:
    """
    Try to send the email up to retries+1 times, waiting `delay` seconds between attempts.
    """
    import time
    for attempt in range(retries + 1):
        try:
            mail.send(msg)
            print(f"✅ Email sent to {msg.recipients}")
            return True
        except Exception as e:
            print(f"❌ Email send failed (attempt {attempt + 1}/{retries + 1}): {e}")
            if attempt < retries:
                time.sleep(delay)
    return False

def send_otp_email(to_email: str, otp: str) -> bool:
    subject = "Your OTP for Sandhika Movie Booking"
    text = f"Dear user,\n\nYour OTP is: {otp}\n\nThis OTP is valid for 5 minutes."
    html = f"""
        <p>Dear user,</p>
        <p>Your OTP is: <strong>{otp}</strong></p>
        <p>This OTP is valid for 5 minutes.</p>
    """
    msg = Message(
        subject=subject,
        recipients=[to_email],
        sender=current_app.config.get("MAIL_DEFAULT_SENDER")  # optional
    )
    msg.body = text
    msg.html = html
    return _send(msg)

def send_approval_email(user_email: str, user_name: str) -> bool:
    subject = "Profile Approved | Sandhika Booking"
    text = (
        f"Dear {user_name},\n\n"
        "Your profile has been approved by the admin. You can now book tickets using the Sandhika portal.\n\n"
        "- Team Sandhika"
    )
    html = f"""
        <p>Dear {user_name},</p>
        <p>Your profile has been approved by the admin. You can now book tickets using the Sandhika portal.</p>
        <p>- Team Sandhika</p>
    """
    msg = Message(subject=subject, recipients=[user_email],
                  sender=current_app.config.get("MAIL_DEFAULT_SENDER"))
    msg.body = text
    msg.html = html
    return _send(msg)

def send_dependent_approval_email(user_email: str, user_name: str, dependent_name: str) -> bool:
    subject = "Dependent Approved | Sandhika Booking"
    text = (
        f"Dear {user_name},\n\n"
        f"Your dependent '{dependent_name}' has been approved and can now be included while booking tickets.\n\n"
        "- Team Sandhika"
    )
    html = f"""
        <p>Dear {user_name},</p>
        <p>Your dependent '<strong>{dependent_name}</strong>' has been approved and can be included while booking tickets.</p>
        <p>- Team Sandhika</p>
    """
    msg = Message(subject=subject, recipients=[user_email],
                  sender=current_app.config.get("MAIL_DEFAULT_SENDER"))
    msg.body = text
    msg.html = html
    return _send(msg)


# --- PDF (xhtml2pdf) helpers ---
import os
from io import BytesIO
from urllib.parse import urlparse
from flask import current_app, render_template, make_response
from xhtml2pdf import pisa

def _pdf_link_callback(uri: str, rel) -> str:
    # Allow http(s) URLs as-is
    parsed = urlparse(uri)
    if parsed.scheme in ("http", "https"):
        return uri
    # Your app uses template_folder='../templates', static_folder='../static'
    static_folder = os.path.join(current_app.root_path, "..", "static")
    # If it's /static/...
    if uri.startswith("/static/"):
        return os.path.abspath(os.path.join(static_folder, uri.replace("/static/", "", 1)))
    # Try relative to static
    candidate = os.path.abspath(os.path.join(static_folder, uri))
    return candidate

def render_pdf_from_template(template_name: str, **ctx) -> bytes | None:
    html = render_template(template_name, **ctx)
    buf = BytesIO()
    result = pisa.CreatePDF(html, dest=buf, link_callback=_pdf_link_callback, encoding="utf-8")
    if result.err:
        return None
    return buf.getvalue()

def make_pdf_response(pdf_bytes: bytes, filename: str = "document.pdf", inline: bool = True):
    dispo = "inline" if inline else "attachment"
    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'{dispo}; filename="{filename}"'
    return resp

