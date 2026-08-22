import os
from flask import Flask
from sqlalchemy import inspect, text
from dotenv import load_dotenv
from extensions import csrf, db
from models import Student, Semester

# 載入 .env 檔案
load_dotenv()

def _add_missing_columns(engine, table_name, columns):
    """Add legacy columns one at a time without touching existing data."""
    existing = {column['name'] for column in inspect(engine).get_columns(table_name)}
    for column_name, definition in columns.items():
        if column_name in existing:
            continue
        with engine.begin() as connection:
            connection.execute(text(
                f'ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}'
            ))


def create_app(test_config=None):
    app = Flask(__name__)

    # --- 1. 設定與資安 (Environment Config) ---
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        raise RuntimeError('SECRET_KEY must be set before the application starts')
    app.secret_key = secret_key

    # 資料庫連線 (自動適應 Render 或 本機)
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    if test_config:
        app.config.update(test_config)

    # 初始化套件
    db.init_app(app)
    csrf.init_app(app)

    # 註冊 Blueprints
    from routes.auth import auth_bp
    from routes.student import student_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)

    # --- 2. 初始化與手動遷移腳本 ---
    with app.app_context():
        # 先嘗試建立所有表單 (針對新用戶)
        db.create_all()
        
        # 舊資料庫安全升級：只補缺少的欄位，不刪除或重建資料表。
        _add_missing_columns(db.engine, 'semester', {
            'deadline': 'TIMESTAMP',
            'allow_profile_edit': 'BOOLEAN DEFAULT TRUE',
        })
        _add_missing_columns(db.engine, 'student', {
            'email': 'VARCHAR(120)',
            'english_name': 'VARCHAR(100)',
        })
        _add_missing_columns(db.engine, 'book', {
            'remark': 'TEXT',
            'display_order': 'INTEGER DEFAULT 0',
        })
            
        # 預設建立一組測試資料 (受環境變數保護)
        if os.environ.get('SEED_DB', '').lower() == 'true':
            if not Student.query.first():
                db.session.add(Student(sid="112001", name="測試生"))
                db.session.commit()
        
            if not Semester.query.first():
                db.session.add(Semester(name="113-1 (預設)", is_active=True, deadline=None))
                db.session.commit()

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
