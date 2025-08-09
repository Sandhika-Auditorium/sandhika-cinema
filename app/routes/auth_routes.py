from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, current_user, login_required
from app.models import User, Dependent, OTP, Booking, db
from app.utils import send_otp_email
from datetime import datetime, timedelta
import random
import string, re

auth_bp = Blueprint('auth', __name__)

def is_password_strong(password):
    """
    Minimum 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special char.
    """
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    if not re.search(r'[@$!%*?&#^()_+=\-]', password):
        return False
    return True

# ---------- Home ----------
@auth_bp.route('/')
def home():
    return render_template('home.html')


# ---------- Send OTP (Registration Step 1) ----------
@auth_bp.route('/send-otp', methods=['POST'])
def send_otp():
    email = request.form.get('email')
    password = request.form.get('password')
    full_name = request.form.get('full_name')
    role = request.form.get('role')

    if not all([email, password, full_name, role]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('auth.register'))
    
    if not is_password_strong(password):
        flash('Password must be at least 8 characters and include uppercase, lowercase, number, and special character.', 'danger')
        return redirect(url_for('auth.register'))

    if User.query.filter_by(email=email).first():
        flash('Email already registered.', 'danger')
        return redirect(url_for('auth.register'))

    otp = ''.join(random.choices(string.digits, k=6))
    expires = datetime.utcnow() + timedelta(minutes=5)

    # Save OTP to database
    db.session.add(OTP(email=email, otp=otp, expires_at=expires))
    db.session.commit()

    # Save temp user data in session
    session['temp_user'] = {
        'email': email,
        'full_name': full_name,
        'role': role,
        'hashed_password': generate_password_hash(password),
        'otp': otp
    }

    try:
        send_otp_email(email, otp)
        flash('OTP sent to your email.', 'success')
    except Exception as e:
        print(f"Error sending OTP: {e}")
        flash('Failed to send OTP. Try again later.', 'danger')

    return render_template('verify_registration.html', email=email)


# ---------- Verify Registration OTP (Registration Step 2) ----------
@auth_bp.route('/verify-registration', methods=['GET', 'POST'])
def verify_registration():
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        temp_user = session.get('temp_user')

        if not temp_user:
            flash("Session expired. Please register again.", "warning")
            return redirect(url_for('auth.register'))

        if entered_otp == temp_user['otp']:
            user = User(
                full_name=temp_user['full_name'],
                email=temp_user['email'],
                role=temp_user['role'],
                is_approved=False
            )
            user.password = temp_user['hashed_password']
            db.session.add(user)
            db.session.commit()

            session.pop('temp_user', None)
            session['awaiting_approval'] = True

            flash("Registration successful. Awaiting admin approval.", "info")
            return redirect(url_for('auth.home'))
        else:
            flash("Incorrect OTP. Please try again.", "danger")

    return render_template('verify_registration.html')


# ---------- Register Form Page ----------
@auth_bp.route('/register')
def register():
    return render_template('register.html')


# ---------- Login ----------
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if not user:
            flash('Email not registered.', 'danger')
            return redirect(url_for('auth.login'))

        if not user.is_approved:
            flash('Account pending admin approval.', 'warning')
            return redirect(url_for('auth.login'))

        if check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful.', 'success')

            # Redirect based on booking status
            booking = Booking.query.filter_by(user_id=user.id).first()
            if booking:
                return redirect(url_for('user.my_bookings'))
            else:
                return redirect(url_for('user.book_tickets'))
        else:
            flash('Incorrect password.', 'danger')

    return render_template('login.html')


# ---------- Logout ----------
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('auth.login'))


# ---------- Forgot Password ----------
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if not user:
            flash("Email not found.", "danger")
            return redirect(url_for('auth.forgot_password'))

        otp = ''.join(random.choices(string.digits, k=6))
        session['reset_email'] = email
        session['reset_otp'] = otp

        send_otp_email(email, otp)
        flash("OTP sent to your email.", "info")
        return redirect(url_for('auth.reset_password'))

    return render_template('forgot_password.html')


# ---------- Reset Password ----------
@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        new_password = request.form.get('new_password')
        email = session.get('reset_email')
        correct_otp = session.get('reset_otp')

        if not email or not correct_otp:
            flash("Session expired. Try again.", "danger")
            return redirect(url_for('auth.forgot_password'))
        
        if entered_otp != correct_otp:
            flash("Incorrect OTP. Try again.", "danger")
            return redirect(url_for('auth.reset_password'))

        if not is_password_strong(new_password):
            flash('Password must be at least 8 characters and include uppercase, lowercase, number and special character.', 'danger')
            return redirect(url_for('auth.reset_password'))


        user = User.query.filter_by(email=email).first()
        if user:
            user.password = generate_password_hash(new_password)
            db.session.commit()

        session.pop('reset_email', None)
        session.pop('reset_otp', None)

        flash("Password reset successful. Please login.", "success")
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html')


# ---------- Clear "Awaiting Approval" Flag ----------
@auth_bp.route('/clear-approval-flag')
def clear_approval_flag():
    session.pop('awaiting_approval', None)
    return '', 204


# ---------- Test Email (Optional Dev Route) ----------
@auth_bp.route('/test-email')
def test_email():
    try:
        send_otp_email('test@example.com', '123456')
        return "Email sent successfully"
    except Exception as e:
        return f"Error sending email: {e}"
