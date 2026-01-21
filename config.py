import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = 'matura-master-secret-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'matura.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = "static/uploads/zadania"
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
    AVATAR_FOLDER = "static/avatars"
