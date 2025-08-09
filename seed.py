
from app import create_app, db, Movie, Showtime

app = create_app()
with app.app_context():
    movie = Movie(title="Top Gun", description="Action movie")
    db.session.add(movie)
    db.session.commit()

    showtime = Showtime(movie_id=movie.id, time="18:00")
    db.session.add(showtime)
    db.session.commit()
    print("Seeded movie and showtime.")
