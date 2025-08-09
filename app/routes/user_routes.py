from flask import Blueprint, render_template, redirect, url_for, request, flash, session, send_file
from flask_login import login_required, current_user
from app.models import User, Dependent, Booking, Showtime, Seat, Movie
from app import db
import io
import pdfkit
from flask import send_file, render_template, jsonify
from datetime import datetime

user_bp = Blueprint('user', __name__, url_prefix='/user')

# ROLE LOGIC
ROLE_PRIORITY = {'junior': 1, 'senior': 2, 'officer': 3}
ROLE_MAP = {'junior': 'Junior Sailor', 'senior': 'Senior Sailor', 'officer': 'Officer'}


# DASHBOARD
@user_bp.route('/dashboard')
@login_required
def dashboard():
    from datetime import date
    today = date.today()
    showtime = Showtime.query.filter(Showtime.date >= today).order_by(Showtime.date, Showtime.time).first()
    user_has_booking, booked_seats, booking, movie_title = False, [], None, None

    if showtime:
        booking = Booking.query.filter_by(user_id=current_user.id, showtime_id=showtime.id).first()
        user_has_booking = booking is not None
        if booking:
            seat_ids = [int(sid) for sid in booking.seat_numbers.split(",") if sid]
            seats = Seat.query.filter(Seat.id.in_(seat_ids)).all()
            booked_seats = [s.label for s in seats]
            movie_title = Movie.query.get(showtime.movie_id).title

    all_seats = Seat.query.all() if showtime else []
    bookings = Booking.query.filter_by(showtime_id=showtime.id).all() if showtime else []
    booked_seat_ids = []
    for b in bookings:
        booked_seat_ids.extend([int(x) for x in b.seat_numbers.split(",") if x])

    return render_template(
        'user_dashboard.html',
        user_has_booking=user_has_booking,
        user_booking=booking,
        booked_seats=booked_seats,
        showtime=showtime,
        movie_title=movie_title,
        seats=all_seats,
        booked_seat_ids=booked_seat_ids,
        user_role=current_user.role
    )

# SEAT BOOKING (GET: show grid, POST: process booking)
@user_bp.route('/book', methods=['GET', 'POST'])
@login_required
def book_tickets():
    # Movie & showtime selection
    movies = Movie.query.all()
    selected_movie_id = request.args.get('movie_id', type=int)
    selected_showtime_id = request.args.get('showtime_id', type=int)
    showtimes = []
    seats, booked_ids = [], []

    if selected_movie_id:
        showtimes = Showtime.query.filter_by(movie_id=selected_movie_id).order_by(Showtime.date, Showtime.time).all()
    if selected_showtime_id:
        seats = Seat.query.order_by(Seat.label).all()
        bookings = Booking.query.filter_by(showtime_id=selected_showtime_id).all()
        for b in bookings:
            booked_ids.extend([int(x) for x in b.seat_numbers.split(",") if x])

    # POST: booking logic
    if request.method == 'POST':
        showtime_id = request.form.get('showtime_id')
        if not showtime_id:
            flash("Select showtime.", "warning")
            return redirect(request.url)

        seat_ids = request.form.getlist('seat_ids')
        self_count = int(request.form.get('self_count', 0))
        dependent_count = int(request.form.get('dependent_count', 0))
        guest_count = int(request.form.get('guest_count', 0))
        total_requested = self_count + dependent_count + guest_count

        if total_requested != len(seat_ids) or not seat_ids:
            flash("Selected seat count does not match participants.", "danger")
            return redirect(request.url)

        # Dependents logic (only approved)
        dependents = Dependent.query.filter_by(user_id=current_user.id, is_approved=True).all()
        if dependent_count > len(dependents):
            flash("You can only book for approved dependents.", "danger")
            return redirect(request.url)

        # Prevent more than 1 free seat per type (per show)
        prior = Booking.query.filter_by(user_id=current_user.id, showtime_id=showtime_id).first()
        if prior:
            flash("You have already booked free seats for this showtime.", "danger")
            return redirect(request.url)

        # Role logic
        user_role = current_user.role.lower()
        user_level = ROLE_PRIORITY.get(user_role, 1)

        all_seat_objs = Seat.query.filter(Seat.id.in_(seat_ids)).all()
        for seat in all_seat_objs:
            seat_restriction = seat.restricted.lower() if seat.restricted else 'junior'
            seat_level = ROLE_PRIORITY.get(seat_restriction, 1)
            if user_level < seat_level:
                flash(f"Seat {seat.label} not allowed for your role.", "danger")
                return redirect(request.url)

        # Already booked seat?
        bookings = Booking.query.filter_by(showtime_id=showtime_id).all()
        all_booked_ids = []
        for b in bookings:
            all_booked_ids.extend([int(x) for x in b.seat_numbers.split(",") if x])
        if any(int(sid) in all_booked_ids for sid in seat_ids):
            flash("One or more seats are already booked.", "danger")
            return redirect(request.url)

        # Save booking
        booking = Booking(
            user_id=current_user.id,
            showtime_id=showtime_id,
            seat_numbers=",".join(seat_ids),
            extra_guests=guest_count,
            payment_status="Pay at Counter" if guest_count > 0 else "Not Required"
        )
        db.session.add(booking)
        db.session.commit()
        if guest_count > 0:
            flash(f"Booking successful. ₹50/guest (x{guest_count}) to be paid at counter.", "info")
        else:
            flash("Booking successful!", "success")
        return redirect(url_for('user.my_bookings'))

    # Get dependents for seat form
    dependents = Dependent.query.filter_by(user_id=current_user.id, is_approved=True).all()

    return render_template(
        "book_seats.html",
        movies=movies,
        showtimes=showtimes,
        selected_movie_id=selected_movie_id,
        selected_showtime_id=selected_showtime_id,
        seats=seats,
        booked_seat_ids=booked_ids,
        user_role=current_user.role,
        user_level=ROLE_PRIORITY.get(current_user.role, 1),
        dependents=dependents
    )

@user_bp.route('/download-ticket/<int:booking_id>')
@login_required
def download_ticket(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for('user.my_bookings'))

    showtime = Showtime.query.get(booking.showtime_id)
    movie = Movie.query.get(showtime.movie_id)
    seat_labels = []
    for sid in booking.seat_numbers.split(','):
        if sid.strip():
            seat = Seat.query.get(int(sid))
            if seat:
                seat_labels.append(seat.label)

    # Render an HTML template for the ticket
    rendered = render_template(
        'ticket_pdf.html',
        booking=booking,
        showtime=showtime,
        movie=movie,
        seat_labels=seat_labels
    )

    # Path to wkhtmltopdf (update as needed for your PC)
    config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')

    # Convert HTML to PDF
    pdf = pdfkit.from_string(rendered, False, configuration=config)
    return send_file(
        io.BytesIO(pdf),
        download_name=f"Ticket_{booking.id}.pdf",
        as_attachment=True,
        mimetype='application/pdf'
    )

@user_bp.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@user_bp.route('/dependents')
@login_required
def view_dependents():
    dependents = Dependent.query.filter_by(user_id=current_user.id).all()
    return render_template('dependents.html', dependents=dependents)

@user_bp.route('/my-bookings')
@login_required
def my_bookings():
    bookings = Booking.query.filter_by(user_id=current_user.id).all()
    enriched_bookings = []
    for booking in bookings:
        show = Showtime.query.get(booking.showtime_id)
        movie = Movie.query.get(show.movie_id)
        seat_ids = [int(sid) for sid in booking.seat_numbers.split(",") if sid]
        seat_objects = Seat.query.filter(Seat.id.in_(seat_ids)).all()
        enriched_bookings.append({
            "id": booking.id,
            "showtime": show,
            "movie": movie,
            "seats": seat_objects,
            "extra_guests": booking.extra_guests,
            "payment_status": booking.payment_status
        })
    return render_template("my_bookings.html", bookings=enriched_bookings)

@user_bp.route('/get_showtimes/<int:movie_id>')
def get_showtimes(movie_id):
    showtimes = Showtime.query.filter_by(movie_id=movie_id).all()
    # Format the date & time for easy reading
    data = []
    for show in showtimes:
        data.append({
            "id": show.id,
            "date": show.date.strftime('%d %b %Y'),
            "time": show.time.strftime('%I:%M %p')
        })
    return jsonify(data)

@user_bp.route('/cancel-booking/<int:booking_id>', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        flash("Unauthorized cancellation.", "danger")
        return redirect(url_for('user.my_bookings'))
    db.session.delete(booking)
    db.session.commit()
    flash("Booking cancelled.", "success")
    return redirect(url_for('user.my_bookings'))

@user_bp.route('/add-dependent', methods=['GET', 'POST'])
@login_required
def add_dependent():
    if request.method == 'POST':
        name = request.form.get('name')
        age = request.form.get('age')
        if not name or not age:
            flash("Please provide both name and age.", "danger")
            return redirect(url_for('user.add_dependent'))
        try:
            age = int(age)
            new_dep = Dependent(user_id=current_user.id, name=name, age=age)
            db.session.add(new_dep)
            db.session.commit()
            flash("Dependent added successfully.", "success")
            return redirect(url_for('user.view_dependents'))
        except ValueError:
            flash("Invalid age entered.", "danger")
            return redirect(url_for('user.add_dependent'))
    return render_template('add_dependent.html')
