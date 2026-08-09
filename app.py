import os
from flask import Flask
from sqlalchemy import text
from dotenv import load_dotenv
from extensions import db
from models import Student, Semester

# 載入 .env 檔案
load_dotenv()

def create_app():
    app = Flask(__name__)

    # --- 1. 設定與資安 (Environment Config) ---
    app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key_123')

    # 資料庫連線 (自動適應 Render 或 本機)
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 初始化套件
    db.init_app(app)

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
        
        # 嘗試手動補上 deadline 欄位
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE semester ADD COLUMN deadline TIMESTAMP;"))
                conn.commit()
                print("Success: Added deadline column")
        except Exception as e:
            print("Info: Column deadline might already exist, skipping.")
            
        # 嘗試手動補上 allow_profile_edit 欄位
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE semester ADD COLUMN allow_profile_edit BOOLEAN DEFAULT TRUE;"))
                conn.commit()
                print("Success: Added allow_profile_edit column")
        except Exception as e:
            print("Info: Column allow_profile_edit might already exist, skipping.")
            
        # 嘗試手動補上 Student 新欄位
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE student ADD COLUMN email VARCHAR(120);"))
                conn.execute(text("ALTER TABLE student ADD COLUMN english_name VARCHAR(100);"))
                conn.commit()
                print("Success: Added Email and english_name to Student")
        except Exception as e:
            print("Info: Student columns might already exist, skipping.")
            
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
