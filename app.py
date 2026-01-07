import os
import csv
from io import StringIO, BytesIO
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# --- 1. 設定與資安 (Environment Config) ---
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key_123')
ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASSWORD', 'admin')

# 資料庫連線 (自動適應 Render 或 本機)
db_url = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- 2. 資料庫模型 (Database Models) ---

class Semester(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=False)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sid = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(50), nullable=False)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    semester_id = db.Column(db.Integer, db.ForeignKey('semester.id'))
    title = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String(500))

class OrderRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    semester_id = db.Column(db.Integer, db.ForeignKey('semester.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    
    # 購買內容摘要 (Text 類型，防爆字數)
    items_summary = db.Column(db.Text, default="")
    total_amount = db.Column(db.Integer, default=0)
    
    # 狀態
    is_locked = db.Column(db.Boolean, default=False)
    bank_last_5 = db.Column(db.String(5), nullable=True)

    student = db.relationship('Student', backref='records')
    semester = db.relationship('Semester')

    def get_book_list(self):
        if not self.items_summary: return []
        return self.items_summary.split(', ')

# 初始化
with app.app_context():
    db.create_all()
    # 預設建立一組測試資料
    if not Student.query.first():
        db.session.add(Student(sid="112001", name="測試生"))
        db.session.commit()
    if not Semester.query.first():
        db.session.add(Semester(name="113-1 (預設)", is_active=True))
        db.session.commit()

# --- 3. 路由邏輯 (Routes) ---

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        sid = request.form.get('sid')
        name = request.form.get('name')
        
        # 管理員登入
        if sid == ADMIN_USER and name == ADMIN_PASS:
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))

        # 學生登入
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
    
    if not current_sem: return "目前沒有開放訂書。"

    # 取得或建立訂單紀錄
    record = OrderRecord.query.filter_by(student_id=user.id, semester_id=current_sem.id).first()
    if not record:
        record = OrderRecord(student_id=user.id, semester_id=current_sem.id)
        db.session.add(record)
        db.session.commit()

    books = Book.query.filter_by(semester_id=current_sem.id).all()

    if request.method == 'POST':
        if record.is_locked:
            flash("訂單已鎖定，無法修改。")
            return redirect(url_for('student_area'))
            
        selected_ids = request.form.getlist('book_ids')
        bank_code = request.form.get('bank_code')
        
        total = 0
        titles = []
        for bid in selected_ids:
            book = Book.query.get(int(bid))
            if book:
                total += book.price
                titles.append(book.title)
        
        record.items_summary = ", ".join(titles)
        record.total_amount = total
        record.bank_last_5 = bank_code
        record.is_locked = True
        db.session.commit()
        flash("訂購成功！")
        return redirect(url_for('student_area'))

    return render_template('student.html', user=user, sem=current_sem, books=books, record=record)

# --- 4. 後台管理路由 (Admin Routes) ---

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))

    # 學期切換
    view_sem_id = request.args.get('sem_id')
    if view_sem_id:
        view_sem = Semester.query.get(view_sem_id)
    else:
        view_sem = Semester.query.filter_by(is_active=True).first()
        if not view_sem: view_sem = Semester.query.first()

    all_sems = Semester.query.order_by(Semester.id.desc()).all()
    books = Book.query.filter_by(semester_id=view_sem.id).all() if view_sem else []

    # 準備學生列表與統計
    student_list = []
    book_stats = {b.title: 0 for b in books} # 初始化統計
    
    if view_sem:
        all_students = Student.query.all()
        for stu in all_students:
            rec = OrderRecord.query.filter_by(student_id=stu.id, semester_id=view_sem.id).first()
            student_list.append({'info': stu, 'record': rec})
            
            # 統計邏輯
            if rec and rec.items_summary:
                bought_titles = rec.get_book_list()
                for t in bought_titles:
                    if t in book_stats:
                        book_stats[t] += 1

    total_income = sum(s['record'].total_amount for s in student_list if s['record'])

    return render_template('admin.html', 
                           view_sem=view_sem, all_sems=all_sems, 
                           books=books, student_list=student_list, 
                           total_income=total_income, book_stats=book_stats)

@app.route('/admin/add_book', methods=['POST'])
def add_book():
    if session.get('role') != 'admin': return redirect(url_for('login'))
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

# --- 新增功能：刪除書籍 ---
@app.route('/admin/delete_book/<int:book_id>', methods=['POST'])
def delete_book(book_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    book = Book.query.get_or_404(book_id)
    sem_id = book.semester_id
    
    db.session.delete(book)
    db.session.commit()
    flash(f"已刪除書籍：{book.title}")
    return redirect(url_for('admin_dashboard', sem_id=sem_id))

@app.route('/admin/add_student', methods=['POST'])
def add_student():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    sid = request.form.get('sid')
    name = request.form.get('name')
    if not Student.query.filter_by(sid=sid).first():
        db.session.add(Student(sid=sid, name=name))
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/unlock/<int:record_id>')
def unlock_student(record_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    rec = OrderRecord.query.get(record_id)
    if rec:
        rec.is_locked = False
        db.session.commit()
    return redirect(url_for('admin_dashboard', sem_id=rec.semester_id))

@app.route('/admin/delete_student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    
    # 1. 找到該學生 (使用資料庫的 primary key id，不是學號)
    student = Student.query.get_or_404(student_id)
    
    try:
        # 2. 為了避免資料庫報錯，要先刪除該學生的所有訂單紀錄
        OrderRecord.query.filter_by(student_id=student.id).delete()
        
        # 3. 刪除學生本人
        db.session.delete(student)
        db.session.commit()
        
        flash(f"已刪除學生：{student.name} ({student.sid})")
    except Exception as e:
        db.session.rollback()
        flash(f"刪除失敗：{str(e)}")
        
    return redirect(url_for('admin_dashboard'))
    
@app.route('/admin/book_detail/<int:book_id>')
def book_detail(book_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    book = Book.query.get_or_404(book_id)
    all_students = Student.query.all()
    bought, not_bought = [], []
    
    for stu in all_students:
        rec = OrderRecord.query.filter_by(student_id=stu.id, semester_id=book.semester_id).first()
        if rec and rec.items_summary and book.title in rec.get_book_list():
            bought.append(stu)
        else:
            not_bought.append(stu)
    return render_template('book_detail.html', book=book, bought=bought, not_bought=not_bought)

@app.route('/admin/export_csv/<int:sem_id>')
def export_csv(sem_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    semester = Semester.query.get_or_404(sem_id)
    records = OrderRecord.query.filter_by(semester_id=sem_id).all()
    all_students = Student.query.all()
    
    si = StringIO()
    si.write('\ufeff') # BOM for Excel
    writer = csv.writer(si)
    writer.writerow(['學號', '姓名', '總金額', '匯款後五碼', '狀態', '購買書單'])
    
    for stu in all_students:
        rec = next((r for r in records if r.student_id == stu.id), None)
        status = "已鎖定" if (rec and rec.is_locked) else "未確認"
        writer.writerow([
            stu.sid, 
            stu.name, 
            rec.total_amount if rec else 0,
            rec.bank_last_5 if rec else "",
            status,
            rec.items_summary if rec else ""
        ])
        
    output = BytesIO()
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name=f"report_{semester.name}.csv")

@app.route('/admin/new_semester', methods=['POST'])
def new_semester():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    Semester.query.update({Semester.is_active: False})
    db.session.add(Semester(name=request.form.get('name'), is_active=True))
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
