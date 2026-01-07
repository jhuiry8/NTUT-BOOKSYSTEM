import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
# 設定密鑰 (正式上線建議改更複雜)
app.secret_key = os.environ.get('SECRET_KEY', 'default_dev_key_do_not_use_in_prod')

ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')      # 預設 admin
ADMIN_PASS = os.environ.get('ADMIN_PASSWORD', 'admin')  # 預設 admin (在本機測試時用)
# --- 資料庫連線設定 ---
# 如果在本地端跑，用 SQLite；如果在 Render 跑，用環境變數的 PostgreSQL URL
db_url = os.environ.get('DATABASE_URL', 'sqlite:///local_test.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- 資料庫模型 (Models) ---

class Semester(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # 例如: 113-2
    is_active = db.Column(db.Boolean, default=False) # 是否為當前學期

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sid = db.Column(db.String(20), unique=True, nullable=False) # 學號
    name = db.Column(db.String(50), nullable=False)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    semester_id = db.Column(db.Integer, db.ForeignKey('semester.id'))
    title = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String(500)) # 存圖片網址

class OrderRecord(db.Model):
    """紀錄學生在該學期的狀態與訂購內容"""
    id = db.Column(db.Integer, primary_key=True)
    semester_id = db.Column(db.Integer, db.ForeignKey('semester.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    
    # 訂單內容 (存成字串簡單處理，例如 "微積分, 工程數學")
    items_summary = db.Column(db.String(500), default="")
    total_amount = db.Column(db.Integer, default=0)
    
    # 狀態控制
    is_locked = db.Column(db.Boolean, default=False) # 是否已送出切結
    bank_last_5 = db.Column(db.String(5), nullable=True) # 匯款後五碼

    # 關聯
    student = db.relationship('Student', backref='records')
    semester = db.relationship('Semester')

# --- 初始化資料庫 ---
with app.app_context():
    db.create_all()
    # 預設建立一個管理員與幾個測試學生 (如果資料庫是空的)
    if not Student.query.first():
        db.session.add(Student(sid="admin", name="管理員")) # 特殊帳號
        db.session.add(Student(sid="112001", name="王小明"))
        db.session.add(Student(sid="112002", name="陳大華"))
        db.session.commit()
    # 預設建立一個學期
    if not Semester.query.first():
        db.session.add(Semester(name="113-1 (測試)", is_active=True))
        db.session.commit()

# --- 路由 (Routes) ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        sid = request.form.get('sid')
        name = request.form.get('name')
        
        # --- 資安升級：比對環境變數 ---
        # 這裡不再寫死 'admin'，而是比對 ADMIN_USER 和 ADMIN_PASS
        if sid == ADMIN_USER and name == ADMIN_PASS:
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))

        # 學生登入邏輯不變
        user = Student.query.filter_by(sid=sid, name=name).first()
        if user:
            session['user_id'] = user.id
            session['role'] = 'student'
            return redirect(url_for('student_area'))
        else:
            flash("登入失敗：學號或姓名錯誤 (非本班學生)")
    
    return render_template('login.html')

@app.route('/student', methods=['GET', 'POST'])
def student_area():
    if session.get('role') != 'student': return redirect(url_for('login'))
    
    user = Student.query.get(session['user_id'])
    current_sem = Semester.query.filter_by(is_active=True).first()
    
    if not current_sem:
        return "目前沒有開放訂書。"

    # 取得或建立該生本學期的紀錄
    record = OrderRecord.query.filter_by(student_id=user.id, semester_id=current_sem.id).first()
    if not record:
        record = OrderRecord(student_id=user.id, semester_id=current_sem.id)
        db.session.add(record)
        db.session.commit()

    # 取得本學期書單
    books = Book.query.filter_by(semester_id=current_sem.id).all()

    # --- 處理表單提交 (下訂單) ---
    if request.method == 'POST':
        if record.is_locked:
            flash("您已完成訂購，無法修改。")
            return redirect(url_for('student_area'))
            
        selected_book_ids = request.form.getlist('book_ids')
        bank_code = request.form.get('bank_code')
        
        # 計算總金額與書名摘要
        total = 0
        summary_list = []
        for bid in selected_book_ids:
            book = Book.query.get(int(bid))
            if book:
                total += book.price
                summary_list.append(book.title)
        
        # 寫入資料庫
        record.items_summary = ", ".join(summary_list)
        record.total_amount = total
        record.bank_last_5 = bank_code
        record.is_locked = True # 鎖定！
        db.session.commit()
        
        flash("訂單已送出並鎖定！請記得繳費。")
        return redirect(url_for('student_area'))

    return render_template('student.html', user=user, sem=current_sem, books=books, record=record)
# --- 在 app.py 中加入這段 ---

@app.route('/admin/add_student', methods=['POST'])
def add_student():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    
    sid = request.form.get('sid')
    name = request.form.get('name')
    
    # 檢查學號是否重複
    existing_student = Student.query.filter_by(sid=sid).first()
    if existing_student:
        flash(f"錯誤：學號 {sid} 已經存在！")
        return redirect(url_for('admin_dashboard'))
        
    # 新增學生
    new_student = Student(sid=sid, name=name)
    db.session.add(new_student)
    db.session.commit()
    
    flash(f"成功新增學生：{name} ({sid})")
    return redirect(url_for('admin_dashboard'))
    
@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))

    # 1. 切換檢視學期
    view_sem_id = request.args.get('sem_id')
    if view_sem_id:
        view_sem = Semester.query.get(view_sem_id)
    else:
        view_sem = Semester.query.filter_by(is_active=True).first()
        if not view_sem: view_sem = Semester.query.first()

    all_sems = Semester.query.order_by(Semester.id.desc()).all()
    
    # 2. 取得該學期資料
    books = Book.query.filter_by(semester_id=view_sem.id).all() if view_sem else []
    records = OrderRecord.query.filter_by(semester_id=view_sem.id).all() if view_sem else []

    # 3. 計算統計
    total_income = sum(r.total_amount for r in records)
    
    return render_template('admin.html', 
                           view_sem=view_sem, 
                           all_sems=all_sems, 
                           books=books, 
                           records=records,
                           total_income=total_income)

# --- 管理員功能 API ---

@app.route('/admin/add_book', methods=['POST'])
def add_book():
    sem_id = request.form.get('sem_id')
    new_book = Book(
        semester_id=sem_id,
        title=request.form.get('title'),
        price=int(request.form.get('price')),
        image_url=request.form.get('image_url')
    )
    db.session.add(new_book)
    db.session.commit()
    return redirect(url_for('admin_dashboard', sem_id=sem_id))

@app.route('/admin/unlock/<int:record_id>')
def unlock_student(record_id):
    rec = OrderRecord.query.get(record_id)
    if rec:
        rec.is_locked = False # 解鎖
        db.session.commit()
    return redirect(url_for('admin_dashboard', sem_id=rec.semester_id))

@app.route('/admin/new_semester', methods=['POST'])
def new_semester():
    name = request.form.get('name')
    # 將舊學期停用
    Semester.query.update({Semester.is_active: False})
    # 建立新學期
    new_sem = Semester(name=name, is_active=True)
    db.session.add(new_sem)
    db.session.commit()
    flash(f"新學期 {name} 已開啟！")
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
