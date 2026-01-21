from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


# =======================
# USERS
# =======================
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    imie = db.Column(db.String(100), nullable=False)
    nazwisko = db.Column(db.String(100), nullable=False)
    login = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)

    zadania_utworzone = db.relationship(
        'Zadanie',
        backref='autor',
        lazy=True
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# =======================
# ZADANIA
# =======================
class Zadanie(db.Model):
    __tablename__ = 'zadania'

    id = db.Column(db.Integer, primary_key=True)
    przedmiot = db.Column(
        db.String(30),
        nullable=False
    )
    zakres = db.Column(
        db.String(20),
        nullable=False
    )
    rok_arkusza = db.Column(db.Integer, nullable=False)
    rodzaj_arkusza = db.Column(db.String(50), nullable=False)
    numer_zadania = db.Column(db.Integer, nullable=False)
    typ_zadania = db.Column(db.String(20), nullable=False)  # 'zamkniete' / 'otwarte'
    dzial = db.Column(db.String(100), nullable=False)
    tresc = db.Column(db.Text, nullable=False)

    odp_a = db.Column(db.Text)
    odp_b = db.Column(db.Text)
    odp_c = db.Column(db.Text)
    odp_d = db.Column(db.Text)
    poprawna_odp = db.Column(db.String(1))

    created_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utcnow
    )

    def validate(self):
        if self.typ_zadania == 'zamkniete':
            required = [
                self.odp_a,
                self.odp_b,
                self.odp_c,
                self.odp_d,
                self.poprawna_odp
            ]
            if any(x is None for x in required):
                raise ValueError(
                    "Zadanie zamknięte wymaga odpowiedzi A-D i poprawnej odpowiedzi."
                )


# =======================
# ZAŁĄCZNIKI DO ZADAŃ
# =======================
class ZadanieZalacznik(db.Model):
    __tablename__ = 'zadania_zalaczniki'

    id = db.Column(db.Integer, primary_key=True)
    zadanie_id = db.Column(
        db.Integer,
        db.ForeignKey('zadania.id'),
        nullable=False
    )
    nazwa_pliku = db.Column(db.String(255), unique=True, nullable=False)


# =======================
# ZADANIA ↔ USER (STUDENT)
# =======================
class ZadanieUser(db.Model):
    __tablename__ = 'zadania_user'

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        primary_key=True
    )
    zadanie_id = db.Column(
        db.Integer,
        db.ForeignKey('zadania.id'),
        primary_key=True
    )

    status = db.Column(db.String(30), nullable=False)
    odpowiedz_usera = db.Column(db.Text)


# =======================
# ZAŁĄCZNIKI USERA DO ZADANIA
# =======================
class ZadanieUserZalacznik(db.Model):
    __tablename__ = 'zadania_user_zalaczniki'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False
    )
    zadanie_id = db.Column(
        db.Integer,
        db.ForeignKey('zadania.id'),
        nullable=False
    )
    nazwa_pliku = db.Column(db.String(255), nullable=False)


# =======================
# LEKCJE
# =======================

class Lesson(db.Model):
    __tablename__ = "lessons"

    id = db.Column(db.Integer, primary_key=True)

    # Kiedy jest lekcja
    date = db.Column(db.Date, nullable=False)
    time_from = db.Column(db.Time, nullable=True)
    time_to = db.Column(db.Time, nullable=True)

    # Treść
    topic = db.Column(db.String(255), nullable=False)
    teacher_comment = db.Column(db.Text, nullable=True)

    # Relacje
    teacher_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=utcnow
    )

    # ORM
    teacher = db.relationship(
        "User",
        backref=db.backref("lessons_created", lazy=True)
    )


class LessonStudent(db.Model):
    __tablename__ = "lesson_students"

    lesson_id = db.Column(
        db.Integer,
        db.ForeignKey("lessons.id"),
        primary_key=True,
        nullable=False
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        primary_key=True,
        nullable=False
    )

    lesson = db.relationship(
        "Lesson",
        backref=db.backref("students", lazy="dynamic")
    )
    student = db.relationship("User")


class LessonTask(db.Model):
    __tablename__ = "lesson_tasks"

    lesson_id = db.Column(
        db.Integer,
        db.ForeignKey("lessons.id"),
        primary_key=True,
        nullable=False
    )

    zadanie_id = db.Column(
        db.Integer,
        db.ForeignKey("zadania.id"),
        primary_key=True,
        nullable=False
    )

    lesson = db.relationship("Lesson", backref="lesson_tasks")
    zadanie = db.relationship("Zadanie")


class LessonNote(db.Model):
    __tablename__ = "lesson_notes"

    __table_args__ = (
        db.UniqueConstraint(
            "lesson_id",
            "student_id",
            name="uq_lesson_student_note"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    lesson_id = db.Column(
        db.Integer,
        db.ForeignKey("lessons.id"),
        nullable=False
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    note = db.Column(db.Text, nullable=False)

    updated_at = db.Column(
        db.DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False
    )

    lesson = db.relationship("Lesson", backref="notes")
    student = db.relationship("User")


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    content = db.Column(db.Text, nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=utcnow,
        nullable=False
    )

    is_read = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship("User", backref="notifications")


# =======================
# MATERIAŁY
# =======================

class Material(db.Model):
    __tablename__ = "materials"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(255), nullable=False)

    subject = db.Column(db.String(30), nullable=False)
    zakres = db.Column(db.String(20), nullable=False)
    dzial = db.Column(db.String(100), nullable=False)

    material_type = db.Column(db.String(30), nullable=False)

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    created_at = db.Column(db.DateTime, default=utcnow)

    author = db.relationship("User")


class MaterialNote(db.Model):
    __tablename__ = "material_notes"

    id = db.Column(db.Integer, primary_key=True)

    material_id = db.Column(
        db.Integer,
        db.ForeignKey("materials.id"),
        nullable=False
    )

    content = db.Column(db.Text, nullable=False)

    material = db.relationship(
        "Material",
        backref=db.backref("note", uselist=False)
    )


class VocabularyItem(db.Model):
    __tablename__ = "vocabulary_items"

    id = db.Column(db.Integer, primary_key=True)

    material_id = db.Column(
        db.Integer,
        db.ForeignKey("materials.id"),
        nullable=False
    )

    word_en = db.Column(db.String(100), nullable=False)
    word_pl = db.Column(db.String(100), nullable=False)

    image_url = db.Column(db.Text)
    audio_url = db.Column(db.Text)

    category = db.Column(db.String(100))

    material = db.relationship(
        "Material",
        backref=db.backref("vocabulary_items", cascade="all, delete-orphan")
    )
