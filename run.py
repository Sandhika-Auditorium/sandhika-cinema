
from app import create_app, db  # ✅ Make sure db is imported
from flask import Flask

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # ✅ Now db is defined and can be used
    app.run(debug=True)
