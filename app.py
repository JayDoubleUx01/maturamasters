from flask import Flask, request, jsonify, render_template, redirect, url_for, session, abort
from functools import wraps
from config import Config
from models import db, User, Zadanie, ZadanieUser, Lesson, LessonStudent, LessonNote, LessonTask, Notification, \
    Material, MaterialNote, VocabularyItem
import os
from werkzeug.utils import secure_filename
from models import ZadanieZalacznik
from collections import defaultdict
from datetime import datetime, date, time, timedelta
from sqlalchemy import text, inspect

app = Flask(__name__)
app.config.from_object(Config)
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER

db.init_app(app)

# =======================
# INIT DB
# =======================
if os.environ.get("RENDER") != "true":
    with app.app_context():
        db.create_all()

# =======================
# DATA
# =======================
DZIALY_PRZEDMIOTOW = {
    'matematyka': [
        "Liczby rzeczywiste i wyrażenia algebraiczne",
        "Zbiory, wartość bezwzględna i nierówności",
        "Funkcje",
        "Funkcja liniowa",
        "Funkcja kwadratowa",
        "Wielomiany i wyrażenia wymierne",
        "Funkcja wykładnicza i funkcja logarytmiczna",
        "Trygonometria",
        "Ciągi",
        "Planimetria",
        "Geometria analityczna",
        "Stereometria",
        "Rachunek prawdopodobieństwa",
        "Statystyka"
    ],
    'polski': [
        "Czytanie ze zrozumieniem",
        "Lektury obowiązkowe",
        "Środki stylistyczne",
        "Epoki literackie",
        "Wypowiedź argumentacyjna",
        "Gramatyka i język"
    ],
    'angielski': {
        "Reading": [],
        "Listening": [],
        "Use of English": [],
        "Writing": [],
        "Grammar": [],
        "Vocabulary": [
            "Personal details",
            "Feelings and emotions"
        ],
        "Picture description": []
    }
}

PRZEDMIOTY = list(DZIALY_PRZEDMIOTOW.keys())

ZAKRESY = ['podstawa', 'rozszerzenie']

app.config['AVATAR_FOLDER'] = Config.AVATAR_FOLDER


# =====================================================
# ======================= HELPERS =====================
# =====================================================

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return wrapper


def role_required(role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if session.get('user_role') != role:
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)

        return wrapper

    return decorator


@app.context_processor
def inject_current_user():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        avatar = get_user_avatar(user.id)
        return dict(current_user=user, current_user_avatar=avatar)
    return dict(current_user=None, current_user_avatar="avatars/default.png")


def get_lesson_tasks(lesson_id, user):
    tasks = (
        db.session.query(Zadanie)
        .join(LessonTask, LessonTask.zadanie_id == Zadanie.id)
        .filter(LessonTask.lesson_id == lesson_id)
        .all()
    )

    # UCZEŃ – dołącz status
    if user.role == "student":
        result = []
        for z in tasks:
            zu = (
                db.session.query(ZadanieUser)
                .filter(
                    ZadanieUser.zadanie_id == z.id,
                    ZadanieUser.user_id == user.id
                )
                .first()
            )
            result.append({
                "id": z.id,
                "title": f"{z.przedmiot} – {z.dzial}",
                "numer": z.numer_zadania,
                "status": zu.status if zu else "nieoddane"
            })
        return result

    # NAUCZYCIEL
    return [{
        "id": z.id,
        "title": f"{z.przedmiot} – {z.dzial}",
        "numer": z.numer_zadania
    } for z in tasks]


def get_user_avatar(user_id):
    for ext in ("png", "jpg", "jpeg"):
        path = f"avatars/user_{user_id}.{ext}"
        if os.path.exists(os.path.join("static", path)):
            return path
    return "avatars/default.png"


# =====================================================
# ======================= AUTH ========================
# =====================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']

        user = User.query.filter_by(login=login).first()

        if not user or not user.check_password(password):
            return render_template('login.html', error="Błędny login lub hasło")

        session.clear()
        session['user_id'] = user.id
        session['user_role'] = user.role
        session['user_name'] = f"{user.imie} {user.nazwisko}"

        return redirect(url_for('dashboard'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route("/lekcje")
@login_required
def lekcje():
    user = db.session.get(User, session['user_id'])
    students = User.query.filter_by(role="student").all()

    today = date.today()
    days = [today + timedelta(days=i) for i in range(7)]

    if user.role == "teacher":
        lessons = get_teacher_lessons(user)
    else:
        lessons = get_student_lessons(user)

    return render_template(
        "lekcje.html",
        lessons=lessons,
        days=days,
        role=user.role,
        students=students
    )


@app.route("/vocabulary")
@login_required
def vocabulary_all():
    words = (
        VocabularyItem.query
        .order_by(VocabularyItem.word_en.asc())
        .all()
    )

    from collections import defaultdict
    grouped = defaultdict(list)

    for w in words:
        first_letter = w.word_en[0].upper()
        grouped[first_letter].append(w)

    return render_template(
        "vocabulary_all.html",
        grouped=grouped
    )


@app.route("/lekcje/<int:lesson_id>")
@login_required
def lesson_detail(lesson_id):
    user = db.session.get(User, session["user_id"])
    lesson = db.session.get(Lesson, lesson_id)
    tasks = get_lesson_tasks(lesson.id, user)

    if not lesson:
        abort(404)

    if user.role == "student":
        assigned = (
            db.session.query(LessonStudent)
            .filter(
                LessonStudent.lesson_id == lesson_id,
                LessonStudent.student_id == user.id
            )
            .first()
        )
        if not assigned:
            abort(403)

        note = (
            db.session.query(LessonNote)
            .filter(
                LessonNote.lesson_id == lesson_id,
                LessonNote.student_id == user.id
            )
            .first()
        )

        return render_template(
            "lesson_student.html",
            lesson=lesson,
            note=note,
            tasks=tasks
        )

    # teacher
    if lesson.teacher_id != user.id:
        abort(403)

    return render_template(
        "lesson_teacher.html",
        lesson=lesson,
        tasks=tasks
    )


@app.route("/lekcje/<int:lesson_id>/zadania", methods=["GET"])
@login_required
@role_required("teacher")
def assign_tasks_view(lesson_id):
    user = db.session.get(User, session["user_id"])
    lesson = db.session.get(Lesson, lesson_id)

    if not lesson:
        abort(404)

    if lesson.teacher_id != user.id:
        abort(403)

    zadania = Zadanie.query.order_by(
        Zadanie.przedmiot,
        Zadanie.dzial,
        Zadanie.numer_zadania
    ).all()

    return render_template(
        "assign_lesson_tasks.html",
        lesson=lesson,
        zadania=zadania
    )


@app.route("/lekcje/<int:lesson_id>/zadania/<int:zadanie_id>")
@login_required
def student_task_view(lesson_id, zadanie_id):
    user = db.session.get(User, session["user_id"])

    if user.role != "student":
        abort(403)

    # sprawdź przypisanie do lekcji
    assigned = (
        db.session.query(LessonStudent)
        .filter(
            LessonStudent.lesson_id == lesson_id,
            LessonStudent.student_id == user.id
        )
        .first()
    )
    if not assigned:
        abort(403)

    # sprawdź czy zadanie należy do lekcji
    lesson_task = (
        db.session.query(LessonTask)
        .filter(
            LessonTask.lesson_id == lesson_id,
            LessonTask.zadanie_id == zadanie_id
        )
        .first()
    )
    if not lesson_task:
        abort(404)

    zadanie = db.session.get(Zadanie, zadanie_id)
    attachments = ZadanieZalacznik.query.filter_by(
        zadanie_id=zadanie_id
    ).all()

    zu = (
        db.session.query(ZadanieUser)
        .filter(
            ZadanieUser.user_id == user.id,
            ZadanieUser.zadanie_id == zadanie_id
        )
        .first()
    )

    return render_template(
        "student_task.html",
        lesson_id=lesson_id,
        zadanie=zadanie,
        zu=zu,
        attachments=attachments
    )


@app.route("/lekcje/<int:lesson_id>/zadania/<int:zadanie_id>", methods=["POST"])
@login_required
def student_task_submit(lesson_id, zadanie_id):
    user = db.session.get(User, session["user_id"])

    if user.role != "student":
        abort(403)

    answer = request.form.get("answer")

    zu = (
        db.session.query(ZadanieUser)
        .filter(
            ZadanieUser.user_id == user.id,
            ZadanieUser.zadanie_id == zadanie_id
        )
        .first()
    )

    if not zu:
        zu = ZadanieUser(
            user_id=user.id,
            zadanie_id=zadanie_id,
            status="oddane",
            odpowiedz_usera=answer
        )
        db.session.add(zu)
    else:
        zu.odpowiedz_usera = answer
        zu.status = "oddane"

    db.session.commit()

    return redirect(url_for(
        "student_task_view",
        lesson_id=lesson_id,
        zadanie_id=zadanie_id
    ))


@app.route("/lekcje", methods=["POST"])
@login_required
@role_required("teacher")
def create_lesson():
    user = db.session.get(User, session["user_id"])

    # --- dane podstawowe ---
    topic = request.form.get("topic")
    lesson_date = request.form.get("date")
    time_from = request.form.get("time_from")
    time_to = request.form.get("time_to")
    teacher_comment = request.form.get("teacher_comment")

    if not topic or not lesson_date:
        abort(400, "Brak tematu lub daty lekcji")

    try:
        lesson = Lesson(
            topic=topic,
            date=datetime.strptime(lesson_date, "%Y-%m-%d").date(),
            time_from=datetime.strptime(time_from, "%H:%M").time()
            if time_from else None,
            time_to=datetime.strptime(time_to, "%H:%M").time()
            if time_to else None,
            teacher_comment=teacher_comment,
            teacher_id=user.id
        )
    except ValueError:
        abort(400, "Niepoprawny format daty lub godziny")

    db.session.add(lesson)
    db.session.flush()  # 👈 mamy lesson.id bez commit

    # --- przypisanie uczniów (opcjonalne) ---
    student_ids = request.form.getlist("student_ids")

    students = (
        db.session.query(User)
        .filter(
            User.id.in_(student_ids),
            User.role == "student"
        )
        .all()
    )

    for s in students:
        db.session.add(
            LessonStudent(
                lesson_id=lesson.id,
                student_id=s.id
            )
        )

    db.session.commit()

    return redirect(url_for("lekcje"))


@app.route("/lekcje/<int:lesson_id>/edit", methods=["POST"])
@login_required
@role_required("teacher")
def update_lesson(lesson_id):
    user = db.session.get(User, session["user_id"])
    lesson = db.session.get(Lesson, lesson_id)

    if not lesson:
        abort(404, "Lekcja nie istnieje")

    # tylko autor lekcji może edytować
    if lesson.teacher_id != user.id:
        abort(403, "Brak dostępu do tej lekcji")

    # --- dane z formularza ---
    topic = request.form.get("topic")
    lesson_date = request.form.get("date")
    time_from = request.form.get("time_from")
    time_to = request.form.get("time_to")
    teacher_comment = request.form.get("teacher_comment")

    if not topic or not lesson_date:
        abort(400, "Temat i data są wymagane")

    try:
        lesson.topic = topic
        lesson.date = datetime.strptime(lesson_date, "%Y-%m-%d").date()
        lesson.time_from = (
            datetime.strptime(time_from, "%H:%M").time()
            if time_from else None
        )
        lesson.time_to = (
            datetime.strptime(time_to, "%H:%M").time()
            if time_to else None
        )
        lesson.teacher_comment = teacher_comment
    except ValueError:
        abort(400, "Niepoprawny format daty lub godziny")

    db.session.commit()

    return redirect(url_for("lekcje"))


@app.route("/lekcje/<int:lesson_id>/notatka", methods=["POST"])
@login_required
@role_required("student")
def upsert_lesson_note(lesson_id):
    user = db.session.get(User, session["user_id"])
    lesson = db.session.get(Lesson, lesson_id)

    if not lesson:
        abort(404, "Lekcja nie istnieje")

    # uczeń musi być przypisany do lekcji
    assigned = (
        db.session.query(LessonStudent)
        .filter(
            LessonStudent.lesson_id == lesson_id,
            LessonStudent.student_id == user.id
        )
        .first()
    )
    if not assigned:
        abort(403, "Brak dostępu do tej lekcji")

    note_text = request.form.get("note") or (
        request.json.get("note") if request.is_json else None
    )

    if note_text is None:
        abort(400, "Brak treści notatki")

    # UPSERT (dzięki UniqueConstraint)
    note = (
        db.session.query(LessonNote)
        .filter(
            LessonNote.lesson_id == lesson_id,
            LessonNote.student_id == user.id
        )
        .first()
    )

    if note:
        note.note = note_text
    else:
        note = LessonNote(
            lesson_id=lesson_id,
            student_id=user.id,
            note=note_text
        )
        db.session.add(note)

    db.session.commit()

    # HTML → redirect, JS → JSON
    if request.is_json:
        return jsonify({"status": "ok", "note": note.note})

    return redirect(url_for("lekcje"))


@app.route("/lekcje/<int:lesson_id>/zadania", methods=["POST"])
@login_required
@role_required("teacher")
def assign_tasks_to_lesson(lesson_id):
    user = db.session.get(User, session["user_id"])
    lesson = db.session.get(Lesson, lesson_id)

    if not lesson:
        abort(404, "Lekcja nie istnieje")

    # bezpieczeństwo: tylko autor lekcji
    if lesson.teacher_id != user.id:
        abort(403, "Brak dostępu do tej lekcji")

    # lista ID zadań (checkboxy / multi-select)
    task_ids = request.form.getlist("zadanie_ids")

    if not task_ids:
        abort(400, "Nie wybrano zadań")

    existing_task_ids = {
        lt.zadanie_id for lt in lesson.lesson_tasks
    }

    added = 0

    for tid in task_ids:
        tid = int(tid)
        if tid not in existing_task_ids:
            db.session.add(
                LessonTask(
                    lesson_id=lesson.id,
                    zadanie_id=tid
                )
            )
            added += 1

    db.session.commit()

    return redirect(url_for("lekcje"))


def get_teacher_lessons(user: User):
    lessons = (
        db.session.query(Lesson)
        .filter(Lesson.teacher_id == user.id)
        .order_by(Lesson.date.desc(), Lesson.time_from)
        .all()
    )

    result = []

    for lesson in lessons:
        result.append({
            "type": "teacher",
            "lesson_id": lesson.id,
            "date": lesson.date,
            "time_from": lesson.time_from,
            "time_to": lesson.time_to,
            "topic": lesson.topic,
            "teacher_comment": lesson.teacher_comment,

            "students_count": lesson.students.count(),
            "tasks_count": len(lesson.lesson_tasks),

            "can_assign_tasks": True,
            "can_comment": True
        })

    return result


def get_student_lessons(user: User):
    lessons = (
        db.session.query(Lesson)
        .join(LessonStudent)
        .filter(LessonStudent.student_id == user.id)
        .order_by(Lesson.date.desc(), Lesson.time_from)
        .all()
    )

    result = []

    for lesson in lessons:
        note = (
            db.session.query(LessonNote)
            .filter(
                LessonNote.lesson_id == lesson.id,
                LessonNote.student_id == user.id
            )
            .first()
        )

        result.append({
            "type": "student",
            "lesson_id": lesson.id,
            "date": lesson.date,
            "time_from": lesson.time_from,
            "time_to": lesson.time_to,
            "topic": lesson.topic,
            "teacher_comment": lesson.teacher_comment,

            "note": note.note if note else "",

            "tasks_count": len(lesson.lesson_tasks),

            "can_add_notes": True
        })

    return result


# =====================================================
# ======================= DASHBOARD ===================
# =====================================================

@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('user_role')

    if role == 'admin':
        return redirect(url_for('panel_admina'))

    if role == 'teacher':
        return redirect(url_for('panel_nauczyciela'))

    if role == 'student':
        return redirect(url_for('panel_ucznia'))

    abort(403)


# =====================================================
# ======================= PANELS ======================
# =====================================================

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = db.session.get(User, session['user_id'])
    error = None
    success = None

    if request.method == 'POST':
        user.imie = request.form.get('imie')
        user.nazwisko = request.form.get('nazwisko')
        avatar = request.files.get('avatar')

        old_password = request.form.get('old_password')
        new_password = request.form.get('password')
        confirm_password = request.form.get('password_confirm')

        if avatar and avatar.filename:
            # 🔒 sprawdź, czy plik faktycznie ma zawartość
            avatar.stream.seek(0, os.SEEK_END)
            size = avatar.stream.tell()
            avatar.stream.seek(0)

            if size > 0:
                filename = f"user_{user.id}.png"
                save_path = os.path.join("static", "avatars", filename)

                # usuń stare wersje avatara
                for ext in ("png", "jpg", "jpeg"):
                    old = os.path.join("static", "avatars", f"user_{user.id}.{ext}")
                    if os.path.exists(old):
                        os.remove(old)

                avatar.save(save_path)

        if new_password:
            if not old_password:
                error = "Aby zmienić hasło, podaj stare hasło"
            elif not user.check_password(old_password):
                error = "Stare hasło jest nieprawidłowe"
            elif new_password != confirm_password:
                error = "Nowe hasła nie są takie same"
            elif len(new_password) < 6:
                error = "Hasło musi mieć minimum 6 znaków"
            else:
                user.set_password(new_password)
                db.session.commit()
                session.clear()
                return redirect(url_for('login'))

        if not error:
            db.session.commit()
            success = "Dane zapisane poprawnie"

    return render_template(
        'profile.html',
        user=user,
        error=error,
        success=success
    )


@app.route('/panel/admin')
@login_required
@role_required('admin')
def panel_admina():
    return render_template('panel_admina.html')


@app.route('/panel/student')
@login_required
@role_required('student')
def panel_ucznia():
    user = db.session.get(User, session['user_id'])

    rows = (
        db.session.query(ZadanieUser, Zadanie)
        .join(Zadanie, Zadanie.id == ZadanieUser.zadanie_id)
        .filter(ZadanieUser.user_id == user.id)
        .all()
    )

    zadania = [
        {
            'id': z.id,
            'rok': z.rok_arkusza,
            'numer': z.numer_zadania,
            'dzial': z.dzial,
            'typ': z.typ_zadania,
            'status': zu.status
        }
        for zu, z in rows
    ]

    return render_template(
        'panel_ucznia.html',
        user=user,
        zadania=zadania
    )


@app.route('/panel/teacher')
@login_required
@role_required('teacher')
def panel_nauczyciela():
    return render_template('panel_nauczyciela.html')


@app.route('/panel/teacher/assign', methods=['GET'])
@login_required
@role_required('teacher')
def assign_view():
    dzialy = (
        db.session.query(Zadanie.dzial)
        .distinct()
        .order_by(Zadanie.dzial)
        .all()
    )

    dzialy = [d[0] for d in dzialy]

    return render_template(
        'assign_tasks.html',
        users=User.query.all(),
        zadania=Zadanie.query.all(),
        dzialy=dzialy
    )


@app.route('/student/zadania')
@login_required
@role_required('student')
def zadania_ucznia():
    user = db.session.get(User, session['user_id'])

    rows = (
        db.session.query(Zadanie, ZadanieUser.status)
        .join(ZadanieUser, Zadanie.id == ZadanieUser.zadanie_id)
        .filter(ZadanieUser.user_id == user.id)
        .all()
    )

    struktura = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )

    for z, status in rows:
        z.status = status
        struktura[z.przedmiot][z.zakres][z.dzial].append(z)

    return render_template(
        'zadania_ucznia.html',
        user=user,
        struktura=struktura,
        PRZEDMIOTY=PRZEDMIOTY
    )


@app.route('/student/statystyki')
@login_required
@role_required('student')
def student_stats():
    return render_template('student_stats.html')


@app.route('/panel/teacher/assign', methods=['POST'])
@login_required
@role_required('teacher')
def assign_tasks():
    user_ids = request.form.getlist('user_ids')
    mode = request.form['mode']

    if not user_ids:
        return "Nie wybrano uczniów", 400

    # wybór zadań
    if mode == 'single':
        task_ids = [int(request.form['zadanie_id'])]

    elif mode == 'section':
        task_ids = [
            z.id for z in Zadanie.query.filter_by(
                dzial=request.form['dzial']
            ).all()
        ]

    elif mode == 'all':
        task_ids = [z.id for z in Zadanie.query.all()]

    assignments = []
    for uid in user_ids:
        for tid in task_ids:
            if not ZadanieUser.query.filter_by(
                    user_id=uid, zadanie_id=tid
            ).first():
                assignments.append(
                    ZadanieUser(
                        user_id=uid,
                        zadanie_id=tid,
                        status='do zrobienia'
                    )
                )

    db.session.bulk_save_objects(assignments)
    db.session.commit()

    return redirect(url_for('panel_nauczyciela'))


# =====================================================
# ======================= USERS =======================
# =====================================================

@app.route('/users')
@login_required
@role_required('teacher')
def users():
    return render_template(
        'users.html',
        users=User.query.all()
    )


@app.route('/users/dodaj', methods=['GET', 'POST'])
@login_required
@role_required('teacher')
def dodaj_usera():
    if request.method == 'POST':
        if User.query.filter_by(login=request.form['login']).first():
            return "Użytkownik z takim loginem już istnieje", 400

        user = User(
            imie=request.form['imie'],
            nazwisko=request.form['nazwisko'],
            login=request.form['login'],
            role=request.form['role']
        )
        user.set_password(request.form['password'])

        db.session.add(user)
        db.session.commit()

        return redirect(url_for('users'))

    return render_template('dodaj_usera.html')


# =====================================================
# ======================= ZADANIA =====================
# =====================================================

@app.route('/zadania')
@login_required
@role_required('teacher')
def zadania():
    return render_template(
        'zadania.html',
        zadania=Zadanie.query.all()
    )


@app.route("/notifications/read", methods=["POST"])
@login_required
def mark_notifications_read():
    Notification.query.filter_by(
        user_id=session["user_id"],
        is_read=False
    ).update({Notification.is_read: True})

    db.session.commit()
    return jsonify({"status": "ok"})


@app.route('/task/<int:zadanie_id>', methods=['GET'])
@login_required
@role_required('student')
def resolve_task(zadanie_id):
    user_id = session['user_id']

    assignment = ZadanieUser.query.filter_by(
        user_id=user_id,
        zadanie_id=zadanie_id
    ).first_or_404()

    zadanie = Zadanie.query.get_or_404(zadanie_id)
    is_closed = assignment.status in ("zrobione", "błędne")
    zalacznik = ZadanieZalacznik.query.filter_by(
        zadanie_id=zadanie_id
    ).first()

    autor_avatar = get_user_avatar(zadanie.autor.id)

    return render_template(
        'resolve_task.html',
        zadanie=zadanie,
        assignment=assignment,
        zalacznik=zalacznik,
        is_closed=is_closed,
        autor_avatar=autor_avatar
    )


@app.route("/materials")
@login_required
def materials():
    materials = Material.query.all()

    from collections import defaultdict

    tree = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(list)
            )
        )
    )

    for m in materials:
        if m.material_type == "VOCABULARY":
            categories = {
                v.category or "Inne"
                for v in m.vocabulary_items
            }
            for cat in categories:
                tree[m.subject][m.zakres][m.dzial][cat].append(m)
        else:
            tree[m.subject][m.zakres][m.dzial]["_"].append(m)

    return render_template("materials.html", tree=tree)


@app.route("/materials/add", methods=["GET", "POST"])
@login_required
@role_required("teacher")
def add_material():
    if request.method == "POST":
        title = request.form.get("title")
        subject = request.form.get("subject")
        zakres = request.form.get("zakres")
        dzial = request.form.get("dzial")
        material_type = request.form.get("material_type")

        if not all([title, subject, zakres, dzial, material_type]):
            abort(400, "Brak wymaganych danych")

        material = Material(
            title=title,
            subject=subject,
            zakres=zakres,
            dzial=dzial,
            material_type=material_type,
            created_by=session["user_id"]
        )

        db.session.add(material)
        db.session.flush()  # TERAZ przejdzie

        # ===== NOTATKA =====
        if material_type == "NOTE":
            content = request.form.get("content")
            if not content:
                abort(400, "Notatka nie może być pusta")

            note = MaterialNote(
                material_id=material.id,
                content=content
            )
            db.session.add(note)

        # ===== SŁÓWKA =====
        elif material_type == "VOCABULARY":
            words_en = request.form.getlist("word_en[]")
            words_pl = request.form.getlist("word_pl[]")
            images = request.form.getlist("image_url[]")
            audios = request.form.getlist("audio_url[]")

            vocab_category = request.form.get("vocab_category")

            for i in range(len(words_en)):
                if not words_en[i] or not words_pl[i]:
                    continue

                vocab = VocabularyItem(
                    material_id=material.id,
                    word_en=words_en[i],
                    word_pl=words_pl[i],
                    image_url=images[i] or None,
                    audio_url=audios[i] or None,
                    category=vocab_category
                )
                db.session.add(vocab)

        else:
            abort(400, "Nieznany typ materiału")

        db.session.commit()
        return redirect(url_for("materials"))

    return render_template(
        "material_add.html",
        PRZEDMIOTY=PRZEDMIOTY,
        ZAKRESY=ZAKRESY,
        DZIALY_PRZEDMIOTOW=DZIALY_PRZEDMIOTOW
    )


@app.route("/materials/<int:material_id>")
@login_required
def material_view(material_id):
    material = Material.query.get_or_404(material_id)
    return render_template("material_view.html", material=material)


@app.route("/notifications")
@login_required
def get_notifications():
    notifs = (
        Notification.query
        .filter_by(user_id=session["user_id"])
        .order_by(Notification.created_at.desc())
        .limit(10)
        .all()
    )

    return jsonify([
        {
            "id": n.id,
            "content": n.content,
            "created_at": n.created_at.strftime("%d.%m.%Y %H:%M"),
            "is_read": n.is_read
        }
        for n in notifs
    ])


@app.route('/teacher/task/<int:zadanie_id>')
@login_required
@role_required('teacher')
def teacher_task_preview(zadanie_id):
    zadanie = Zadanie.query.get_or_404(zadanie_id)
    zalacznik = ZadanieZalacznik.query.filter_by(
        zadanie_id=zadanie_id
    ).first()

    return render_template(
        'teacher_task_preview.html',
        zadanie=zadanie,
        zalacznik=zalacznik
    )


@app.route('/teacher/task/<int:zadanie_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('teacher')
def edit_task(zadanie_id):
    zadanie = Zadanie.query.get_or_404(zadanie_id)

    if request.method == 'POST':
        # --- METADANE ---
        zadanie.przedmiot = request.form['przedmiot']
        zadanie.zakres = request.form['zakres']
        zadanie.dzial = request.form['dzial']
        zadanie.rodzaj_arkusza = request.form['rodzaj_arkusza']

        zadanie.rok_arkusza = int(
            request.form.get('rok_arkusza') or 0
        )
        zadanie.numer_zadania = int(
            request.form.get('numer_zadania') or 0
        )

        # --- TREŚĆ ---
        zadanie.tresc = request.form['tresc']
        zadanie.odp_a = request.form.get('odp_a')
        zadanie.odp_b = request.form.get('odp_b')
        zadanie.odp_c = request.form.get('odp_c')
        zadanie.odp_d = request.form.get('odp_d')
        zadanie.poprawna_odp = request.form.get('poprawna_odp')

        # WALIDACJA (ta sama co przy dodawaniu)
        zadanie.validate()

        db.session.commit()

        return redirect(url_for(
            'teacher_task_preview',
            zadanie_id=zadanie.id
        ))

    return render_template(
        'edit_task.html',
        zadanie=zadanie,
        PRZEDMIOTY=PRZEDMIOTY,
        DZIALY_PRZEDMIOTOW=DZIALY_PRZEDMIOTOW,
        ZAKRESY=ZAKRESY
    )


@app.route('/task/<int:zadanie_id>/submit', methods=['POST'])
@login_required
@role_required('student')
def submit_task(zadanie_id):
    data = request.json
    user_answer = data.get('answer')

    if not user_answer:
        return jsonify({'error': 'Brak odpowiedzi'}), 400

    assignment = ZadanieUser.query.filter_by(
        user_id=session['user_id'],
        zadanie_id=zadanie_id
    ).first_or_404()

    zadanie = Zadanie.query.get_or_404(zadanie_id)

    assignment.odpowiedz_usera = user_answer

    is_correct = user_answer == zadanie.poprawna_odp

    assignment.status = 'zrobione' if is_correct else 'błędne'
    db.session.commit()

    return jsonify({
        'correct': is_correct,
        'correct_answer': zadanie.poprawna_odp
    })


@app.route('/zadania/dodaj', methods=['GET', 'POST'])
@login_required
@role_required('teacher')
def dodaj_zadanie_ui():
    if request.method == 'POST':
        przedmiot = request.form.get('przedmiot')
        if przedmiot not in PRZEDMIOTY:
            return "Niepoprawny przedmiot", 400

        zakres = request.form.get('zakres')
        if zakres not in ZAKRESY:
            return "Niepoprawny zakres", 400

        dzial = request.form.get('dzial')
        if dzial not in DZIALY_PRZEDMIOTOW.get(przedmiot, []):
            return "Niepoprawny dział", 400

        rodzaj_arkusza = request.form['rodzaj_arkusza']

        rok_arkusza = request.form.get('rok_arkusza')
        numer_zadania = request.form.get('numer_zadania')

        if rodzaj_arkusza != 'out':
            if not rok_arkusza or not numer_zadania:
                return "Rok i numer zadania są wymagane dla arkuszy maturalnych", 400
        else:
            rok_arkusza = 0
            numer_zadania = 0

        try:
            zadanie = Zadanie(
                przedmiot=przedmiot,
                zakres=zakres,
                dzial=dzial,
                rodzaj_arkusza=request.form['rodzaj_arkusza'],
                rok_arkusza=int(rok_arkusza),
                numer_zadania=int(numer_zadania),
                typ_zadania=request.form['typ_zadania'],
                tresc=request.form['tresc'],
                odp_a=request.form.get('odp_a') or None,
                odp_b=request.form.get('odp_b') or None,
                odp_c=request.form.get('odp_c') or None,
                odp_d=request.form.get('odp_d') or None,
                poprawna_odp=request.form.get('poprawna_odp') or None,
                created_by=session['user_id']
            )
            zadanie.validate()
        except ValueError as e:
            return f"Błąd walidacji: {e}", 400

        db.session.add(zadanie)
        db.session.commit()

        # ===== ZAŁĄCZNIK =====
        file = request.files.get('zalacznik')
        if file and file.filename:
            filename = secure_filename(file.filename)

            zadanie_folder = os.path.join(
                app.config['UPLOAD_FOLDER'],
                str(zadanie.id)
            )
            os.makedirs(zadanie_folder, exist_ok=True)

            file.save(os.path.join(zadanie_folder, filename))

            db.session.add(
                ZadanieZalacznik(
                    zadanie_id=zadanie.id,
                    nazwa_pliku=f"{zadanie.id}/{filename}"
                )
            )
            db.session.commit()

        return redirect(url_for('zadania'))

    # ===== GET =====
    return render_template(
        'dodaj_zadanie.html',
        przedmioty=PRZEDMIOTY,
        dzialy_przedmiotow=DZIALY_PRZEDMIOTOW,
        zakresy=ZAKRESY
    )


# =====================================================
# ======================= INDEX =======================
# =====================================================

@app.route('/')
def index():
    return redirect(url_for('login'))


# =====================================================
# ======================= BAZA ADMIN ==================
# =====================================================

@app.route('/baza', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def baza():
    query = ""
    result = None
    columns = []
    error = None
    message = None

    if request.method == 'POST':
        query = request.form.get('query', '').strip()

        if not query:
            error = "Zapytanie SQL nie może być puste"
        else:
            try:
                # surowe połączenie (bez ORM)
                with db.engine.connect() as conn:
                    # SELECT
                    if query.lower().startswith("select"):
                        res = conn.execute(text(query))
                        result = res.fetchall()
                        columns = res.keys()
                    # INSERT / UPDATE / DELETE
                    else:
                        conn.execute(text(query))
                        conn.commit()
                        message = "Zapytanie wykonane poprawnie"

            except Exception as e:
                error = str(e)

    return render_template(
        'baza.html',
        query=query,
        result=result,
        columns=columns,
        error=error,
        message=message
    )


@app.route('/baza/tabele')
@login_required
@role_required('admin')
def baza_tabele():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    return render_template(
        'baza_tabele.html',
        tables=tables
    )


@app.route('/baza/tabele/<table_name>')
@login_required
@role_required('admin')
def baza_tabela_podglad(table_name):
    inspector = inspect(db.engine)

    if table_name not in inspector.get_table_names():
        abort(404, "Tabela nie istnieje")

    # kolumny
    columns = [c['name'] for c in inspector.get_columns(table_name)]

    # dane (limit bezpieczeństwa)
    with db.engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT * FROM {table_name} LIMIT 100")
        ).fetchall()

    return render_template(
        'baza_tabela_podglad.html',
        table_name=table_name,
        columns=columns,
        rows=result
    )


# =====================================================
# ======================= RUN =========================
# =====================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
