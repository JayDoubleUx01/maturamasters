from app import app
from models import db, User

with app.app_context():
    if User.query.filter_by(login="admin").first():
        print("Admin już istnieje")
    else:
        admin = User(
            imie="Jakub",
            nazwisko="Wasilewski",
            login="ladm",
            role="admin"
        )
        admin.set_password("B4rdzoTajne")

        db.session.add(admin)
        db.session.commit()

        print("✅ Utworzono administratora")
