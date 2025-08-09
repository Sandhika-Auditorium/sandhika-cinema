from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from datetime import datetime
from app import db
from app.models import Seat, User, Dependent, Movie, Showtime, Booking
from functools import wraps
from app.utils import send_approval_email, send_dependent_approval_email
import re

admin_bp = Blueprint('admin_routes', __name__, template_folder='../templates/admin')

_label_re = re.compile(r'^([A-Z]+)(\d+)$')

def _label_key(label: str):

    if not label:
        return ('', 0)
    m = _label_re.match(label.strip().upper())
    if not m:
        return (label.strip().upper(), 0)
    row, num = m.groups()
    return (row, int(num))

def build_local_seat_index(seats):
   
    ordered = sorted(seats, key=lambda s: _label_key(getattr(s, 'label', '')))
    return {s.id: i + 1 for i, s in enumerate(ordered)}

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_routes.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ---- ADMIN LOGIN/LOGOUT ----
@admin_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == current_app.config.get('ADMIN_USERNAME') and password == current_app.config.get('ADMIN_PASSWORD'):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_routes.admin_dashboard'))
        else:
            flash('Invalid admin credentials', 'danger')
    return render_template('admin/admin_login.html')

@admin_bp.route('/admin/logout', methods=['POST'])
@admin_required
def admin_logout():
    session.pop('admin_logged_in', None)
    flash("Logged out successfully.", "info")
    return redirect(url_for('admin_routes.admin_login'))

# ---- DASHBOARD & APPROVALS ----
@admin_bp.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    pending_users = User.query.filter_by(is_approved=False).all()
    pending_dependents = Dependent.query.filter_by(is_approved=False).all()
    return render_template('admin/admin_dashboard.html', users=pending_users, dependents=pending_dependents)

@admin_bp.route('/approve_user/<int:user_id>', methods=['POST'])
@admin_required
def approve_user(user_id):
    user = User.query.get(user_id)
    if user:
        user.is_approved = True
        db.session.commit()
        flash('User approved successfully.', 'success')
        send_approval_email(user.email, user.full_name)
    return redirect(url_for('admin_routes.admin_dashboard'))


@admin_bp.route('/approve_dependent/<int:dependent_id>', methods=['POST'])
@admin_required
def approve_dependent(dependent_id):
    dependent = Dependent.query.get(dependent_id)
    if dependent:
        dependent.is_approved = True
        db.session.commit()
        flash('Dependent approved successfully.', 'success')
        # Get parent user info
        user = User.query.get(dependent.user_id)
        if user:
            send_dependent_approval_email(user.email, user.full_name, dependent.name)
    return redirect(url_for('admin_routes.admin_dashboard'))

@admin_bp.route('/populate_seats')
@admin_required
def populate_seats():
    for row in range(13):  # Rows A to M
        row_letter = chr(ord('A') + row)
        for col in range(1, 11):  # 1 to 10
            label = f"{row_letter}{col}"
            if not Seat.query.filter_by(label=label).first():
                seat = Seat(label=label)
                db.session.add(seat)
    db.session.commit()
    return "Seats populated!"

# ---- MOVIES ----
@admin_bp.route('/admin/movies')
@admin_required
def admin_movies():
    movies = Movie.query.all()
    showtimes = Showtime.query.all()
    return render_template('admin/admin_movies.html', movies=movies, showtimes=showtimes)

@admin_bp.route('/admin/add-movie', methods=['GET', 'POST'])
@admin_required
def admin_add_movie():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        duration = request.form.get('duration')
        if not title or not description or not duration:
            flash("Please fill in all fields.", "danger")
            return redirect(url_for('admin_routes.admin_add_movie'))
        try:
            duration = int(duration)
            new_movie = Movie(title=title, description=description, duration=duration)
            db.session.add(new_movie)
            db.session.commit()
            flash("Movie added successfully!", "success")
            return redirect(url_for('admin_routes.admin_movies'))
        except ValueError:
            flash("Duration must be a number.", "danger")
    return render_template('admin/admin_add_movie.html')

@admin_bp.route('/admin/delete-movie/<int:movie_id>', methods=['POST'])
@admin_required
def delete_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    # Find all showtimes for this movie
    showtimes = Showtime.query.filter_by(movie_id=movie_id).all()
    for show in showtimes:
        # Delete all bookings for this showtime
        Booking.query.filter_by(showtime_id=show.id).delete()
        db.session.delete(show)
    db.session.delete(movie)
    db.session.commit()
    flash("Movie and all associated showtimes and bookings deleted.", "info")
    return redirect(url_for('admin_routes.admin_dashboard'))


# ---- SHOWTIMES ----
@admin_bp.route('/admin/showtimes', methods=['GET', 'POST'])
@admin_required
def admin_showtimes():
    movies = Movie.query.all()
    showtimes = Showtime.query.all()
    if request.method == 'POST':
        movie_id = request.form.get('movie_id')
        date_str = request.form.get('date')
        time_str = request.form.get('time')
        if not movie_id or not date_str or not time_str:
            flash("All fields are required.", "danger")
            return redirect(url_for('admin_routes.admin_showtimes'))
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
            time = datetime.strptime(time_str, "%H:%M").time()
            new_show = Showtime(movie_id=movie_id, date=date, time=time)
            db.session.add(new_show)
            db.session.commit()
            flash("Showtime added successfully!", "success")
            return redirect(url_for('admin_routes.admin_showtimes'))
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
    return render_template('admin/admin_showtimes.html', movies=movies, showtimes=showtimes)

@admin_bp.route('/admin/delete-showtime/<int:showtime_id>', methods=['POST'])
@admin_required
def delete_showtime(showtime_id):
    showtime = Showtime.query.get_or_404(showtime_id)
    # Delete all bookings for this showtime
    Booking.query.filter_by(showtime_id=showtime_id).delete()
    db.session.delete(showtime)
    db.session.commit()
    flash("Showtime and all associated bookings deleted.", "info")
    return redirect(url_for('admin_routes.admin_dashboard'))


# ---- SEAT STATUS ----
@admin_bp.route('/admin/seats')
@admin_required
def admin_seats():
    showtimes = Showtime.query.all()
    seat_map = {}
    for show in showtimes:
        all_seats = Seat.query.all()
        bookings = Booking.query.filter_by(showtime_id=show.id).all()
        booked_seat_ids = {}
        for b in bookings:
            user = User.query.get(b.user_id)
            seat_ids = [int(s) for s in b.seat_numbers.split(",") if s]
            for sid in seat_ids:
                booked_seat_ids[sid] = {
                    "user": user.full_name,
                    "role": user.role,
                    "email": user.email
                }
        seat_map[show] = {
            "all_seats": all_seats,
            "booked_seat_ids": booked_seat_ids
        }
    return render_template('admin/admin_seats.html', seat_map=seat_map)

# ---- SEAT SUMMARY ----
@admin_bp.route('/admin/summary')
@admin_required
def admin_summary():
    from sqlalchemy import and_

    movie_id = request.args.get('movie_id', type=int)
    date_str = request.args.get('date')

    filters = []
    if movie_id:
        filters.append(Showtime.movie_id == movie_id)
    if date_str:
        try:
            filters.append(Showtime.date == datetime.strptime(date_str, '%Y-%m-%d').date())
        except:
            pass

    # Showtimes to include
    showtimes = Showtime.query.filter(and_(*filters)) if filters else Showtime.query.all()
    all_seats = Seat.query.all()
    local_index = build_local_seat_index(all_seats)     # { seat_id: 1..N }

    st_ids = [s.id for s in showtimes]
    bookings = Booking.query.filter(Booking.showtime_id.in_(st_ids)).all() if st_ids else []

    showtime_bookings = []
    for show in showtimes:
        # Collect mapped local numbers for this showtime
        local_nums = []
        for b in bookings:
            if b.showtime_id != show.id:
                continue
            # seat_numbers holds comma-separated seat IDs
            ids = [s for s in (x.strip() for x in (b.seat_numbers or '').split(',')) if s]
            # map id->local number; keep only those that exist in index
            mapped = [local_index.get(int(sid), None) for sid in ids if sid.isdigit()]
            mapped = [m for m in mapped if m is not None]
            local_nums.extend(mapped)

        local_nums.sort()
        flat_seats = ", ".join(map(str, local_nums)) if local_nums else "-"

        showtime_bookings.append({
            'showtime': show,
            'seats': flat_seats
        })

    movies = Movie.query.all()
    return render_template(
        'admin/admin_summary.html',
        movies=movies,
        selected_movie_id=movie_id,
        selected_date=date_str,
        showtime_bookings=showtime_bookings
    )
