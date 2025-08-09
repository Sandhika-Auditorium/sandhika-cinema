import os
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mail import Mail, Message

# Load environment variables from .env (local) or Railway Variables (production)
load_dotenv()

# ---- Flask app setup ----
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-me")

# ---- Admin credentials ----
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# ---- Mail config ----
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")

mail = Mail(app)

# ---- In-memory stores (restart = reset) ----
otp_store = {}
users = []
user_id_counter = 1

# ---- Health check ----
@app.get("/health")
def health():
    return {"ok": True}

# ---- Routes ----
@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    global user_id_counter
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name")
    email = request.form.get("email")
    category = request.form.get("category")
    dependents = []

    # Parse dependents
    for key in request.form:
        if key.startswith("dependents[") and key.endswith("][name]"):
            index = key.split("[")[1].split("]")[0]
            dep_name = request.form.get(f"dependents[{index}][name]")
            dep_age = request.form.get(f"dependents[{index}][age]")
            dependents.append({"name": dep_name, "age": dep_age})

    user = {
        "id": user_id_counter,
        "name": name,
        "email": email,
        "category": category,
        "dependents": dependents,
        "approved": False,
        "registered_on": datetime.utcnow(),
    }

    users.append(user)
    user_id_counter += 1

    flash("Registered successfully! Waiting for admin approval.", "info")
    return render_template("registration_pending.html", user=user)

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html", step="email")

@app.route("/send_otp", methods=["POST"])
def send_otp():
    email = request.form.get("email")
    entered_otp = request.form.get("otp")

    # Step 1: send OTP
    if not entered_otp:
        otp = str(random.randint(100000, 999999))
        expires = datetime.utcnow() + timedelta(minutes=5)
        otp_store[email] = {"otp": otp, "expires": expires}
        session["login_email"] = email
        send_email_otp(email, otp)
        flash("OTP sent to your email. It will expire in 5 minutes.", "info")
        return render_template("login.html", step="otp", email=email)

    # Step 2: verify OTP
    stored = otp_store.get(email)
    if not stored:
        flash("No OTP sent to this email. Try again.", "danger")
        return redirect(url_for("login"))

    if datetime.utcnow() > stored["expires"]:
        flash("OTP expired. Please request a new one.", "warning")
        return redirect(url_for("login"))

    if entered_otp == stored["otp"]:
        user = next((u for u in users if u["email"] == email), None)
        if not user:
            flash("User not found. Please register.", "danger")
            return redirect(url_for("register"))

        if not user["approved"]:
            flash("Your account is not approved yet by admin.", "warning")
            return render_template("login.html", step="email")

        flash("Login successful!", "success")
        session["user_email"] = email
        return redirect(url_for("dashboard"))

    flash("Invalid OTP. Try again.", "danger")
    return render_template("login.html", step="otp", email=email)

@app.route("/dashboard")
def dashboard():
    if "user_email" not in session:
        return redirect(url_for("login"))
    return f"<h1>Welcome, {session['user_email']}!</h1><p>You are now logged in.</p>"

def send_email_otp(recipient_email, otp_code):
    try:
        msg = Message(
            "Your Sandhika Login OTP",
            sender=app.config["MAIL_USERNAME"],
            recipients=[recipient_email],
        )
        msg.body = f"Your OTP is: {otp_code}\n\nThis will expire in 5 minutes."
        mail.send(msg)
    except Exception as e:
        print("Error sending email:", e)
        flash("Failed to send OTP. Try again later.", "danger")

# ---- Admin ----
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        return render_template("admin_login.html")

    username = request.form.get("username")
    password = request.form.get("password")
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session["admin"] = True
        return redirect(url_for("admin_dashboard"))

    flash("Invalid admin credentials", "danger")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    pending = [u for u in users if not u["approved"]]
    return render_template("admin_dashboard.html", pending_users=pending)

@app.route("/admin/approve/<int:user_id>", methods=["POST"])
def approve_user(user_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    for u in users:
        if u["id"] == user_id:
            u["approved"] = True
            flash(f"Approved {u['name']}", "success")
            break
    return redirect(url_for("admin_dashboard"))

# ---- Run (dev only). Railway will use Gunicorn via Procfile ----
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
