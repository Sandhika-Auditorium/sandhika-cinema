from app.models import db, Seat

def seed_seats_if_empty():
    if Seat.query.first():
        return

    seats = []

    # Junior Sailors: A-F (60 seats)
    for row in ['A', 'B', 'C', 'D', 'E', 'F']:
        for num in range(1, 11):
            seats.append(Seat(label=f"{row}{num}", restricted='Junior Sailor'))

    # Senior Sailors: G-J (40 seats)
    for row in ['G', 'H', 'I', 'J']:
        for num in range(1, 11):
            seats.append(Seat(label=f"{row}{num}", restricted='Senior Sailor'))

    # Officers: K-M (30 seats)
    for row in ['K', 'L', 'M']:
        for num in range(1, 11):
            seats.append(Seat(label=f"{row}{num}", restricted='Officer'))

    db.session.bulk_save_objects(seats)
    db.session.commit()
    print("✅ Seats seeded.")
