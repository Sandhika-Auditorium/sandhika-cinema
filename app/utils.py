from flask_mail import Message
from app import mail

def send_otp_email(to_email, otp):
    subject = "Your OTP for Sandhika Movie Booking"
    body = f"Dear user,\n\nYour OTP is: {otp}\n\nThis OTP is valid for 5 minutes."

    msg = Message(subject, recipients=[to_email])
    msg.body = body

    try:
        mail.send(msg)
        print(f"✅ OTP sent to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Failed to send OTP: {e}")
        return False

def send_approval_email(user_email, user_name):
    msg = Message(
        subject="Profile Approved | Sandhika Booking",
        recipients=[user_email],
        body=(
            f"Dear {user_name},\n\n"
            "Your profile has been approved by the admin. "
            "You can now book tickets using the Sandhika Booking portal.\n\n"
            "- Team Sandhika"
        )
    )
    mail.send(msg)

def send_dependent_approval_email(user_email, user_name, dependent_name):
    msg = Message(
        subject="Dependent Approved | Sandhika Booking",
        recipients=[user_email],
        body=(
            f"Dear {user_name},\n\n"
            f"Your dependent '{dependent_name}' has been approved and can now be included while booking tickets.\n\n"
            "- Team Sandhika"
        )
    )
    mail.send(msg)



