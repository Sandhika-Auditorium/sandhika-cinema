from flask_login import UserMixin
from app.extensions import db
from datetime import datetime
# ---------------------------
# User model
# ---------------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 'junior', 'senior', 'officer'
    is_approved = db.Column(db.Boolean, default=False)  # ✅ Rename this to match your code

    dependents = db.relationship('Dependent', backref='user', cascade="all, delete-orphan")
    bookings = db.relationship('Booking', backref='user', cascade="all, delete-orphan")

class OTP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    otp = db.Column(db.String(6), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ---------------------------
# Dependent model
# ---------------------------
class Dependent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_approved = db.Column(db.Boolean, default=False)
# ---------------------------
# Movie model
# ---------------------------

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    duration = db.Column(db.Integer)
    poster_url = db.Column(db.String(255))
    showtimes = db.relationship('Showtime', backref='movie', cascade="all, delete-orphan")

# ---------------------------
# Showtime model
# ---------------------------
class Showtime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    #movie = db.relationship('Movie', backref='showtimes')
# ---------------------------
# Booking model
# ---------------------------
class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    showtime_id = db.Column(db.Integer, db.ForeignKey('showtime.id'), nullable=False)
    seat_numbers = db.Column(db.String(250), nullable=False)
    extra_guests = db.Column(db.Integer, default=0)
    payment_status = db.Column(db.String(50), default='Not Required')
    status = db.Column(db.String(20), default='confirmed')

    # NEW: Add this line
    booked_for = db.Column(db.String(20), default='Self')  # Values: 'Self', 'Dependent', 'Guest'

    showtime = db.relationship('Showtime', backref='bookings')

class Seat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(10), nullable=False, unique=True)  # e.g., A1, B3
    restricted = db.Column(db.String(20))  # Optional: restrict to 'Junior Sailor', etc.

    def __repr__(self):
        return f"<Seat {self.label}>"

   
   

