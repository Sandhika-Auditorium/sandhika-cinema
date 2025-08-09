from app import create_app, db
from app.models import *  # Import all models so tables are created

app = create_app()

with app.app_context():
    db.create_all()
