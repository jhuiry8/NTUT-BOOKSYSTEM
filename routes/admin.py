import csv
from io import StringIO, BytesIO
from flask import Blueprint, request, redirect, url_for, flash, session, render_template, send_file
from datetime import datetime, timedelta
from extensions import db
from models import Student, Semester, Book, OrderRecord

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('auth.login'))

    # 學期切換
    view_sem_id = request.args.get('sem_id')
    if view_sem_id:
        view_sem = Semester.query.get(view_sem_id)
    else:
        view_sem = Semester.query.filter_by(is_active=True).first()
        if not view_sem: view_sem = Semester.query.first()

    all_sems = Semester.query.order_by(Semester.id.desc()).all()
    books = Book.query.filter_by(semester_id=view_sem.id).order_by(Book.display_order.asc(), Book.id.asc()).all() if view_sem else []
    now_tw = datetime.utcnow() + timedelta(hours=8)
    
    # 準備學生列表與統計
    student_list = []
    book_stats = {b.title: 0 for b in books} # 初始化統計
    
    if view_sem:
        all_students = Student.query.order_by(Student.sid.asc()).all()
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
                           total_income=total_income, book_stats=book_stats, now=now_tw)

@admin_bp.route('/add_book', methods=['POST'])
def add_book():
    if session.get('role') != 'admin': return redirect(url_for('auth.login'))
    sem_id = request.form.get('sem_id')
    new_book = Book(
        semester_id=sem_id,
        title=request.form.get('title'),
        price=int(request.form.get('price')),
        image_url=request.form.get('image_url'),
        remark=request.form.get('remark'),
        display_order=int(request.form.get('display_order', 0))
    )
    db.session.add(new_book)
    db.session.commit()
    return redirect(url_for('admin.admin_dashboard', sem_id=sem_id))

@admin_bp.route('/update_book/<int:book_id>', methods=['POST'])
def update_book(book_id):
    if session.get('role') != 'admin': return redirect(url_for('auth.login'))
    book = Book.query.get_or_404(book_id)
    
    book.price = int(request.form.get('price'))
    book.remark = request.form.get('remark')
    book.display_order = int(request.form.get('display_order', 0))
    
    db.session.commit()
    flash(f"已更新書籍：{book.title}")
    return redirect(url_for('admin.admin_dashboard', sem_id=book.semester_id))

@admin_bp.route('/delete_book/<int:book_id>', methods=['POST'])
def delete_book(book_id):
    if session.get('role') != 'admin': return redirect(url_for('auth.login'))
    book = Book.query.get_or_404(book_id)
    sem_id = book.semester_id
    
    db.session.delete(book)
    db.session.commit()
    flash(f"已刪除書籍：{book.title}")
    return redirect(url_for('admin.admin_dashboard', sem_id=sem_id))

@admin_bp.route('/add_student', methods=['POST'])
def add_student():
    if session.get('role') != 'admin': return redirect(url_for('auth.login'))
    sid = request.form.get('sid')
    name = request.form.get('name')
    if not Student.query.filter_by(sid=sid).first():
        db.session.add(Student(sid=sid, name=name))
        db.session.commit()
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/unlock/<int:record_id>', methods=['POST'])
def unlock_student(record_id):
    if session.get('role') != 'admin': return redirect(url_for('auth.login'))
    rec = OrderRecord.query.get(record_id)
    sem_id = None
    if rec:
        rec.is_locked = False
        sem_id = rec.semester_id
        db.session.commit()
    return redirect(url_for('admin.admin_dashboard', sem_id=sem_id))

@admin_bp.route('/delete_student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    if session.get('role') != 'admin': return redirect(url_for('auth.login'))
    
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
        
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/book_detail/<int:book_id>')
def book_detail(book_id):
    if session.get('role') != 'admin': return redirect(url_for('auth.login'))
    book = Book.query.get_or_404(book_id)
    all_students = Student.query.order_by(Student.sid.asc()).all()
    bought, not_bought = [], []
    
    for stu in all_students:
        rec = OrderRecord.query.filter_by(student_id=stu.id, semester_id=book.semester_id).first()
        if rec and rec.items_summary and book.title in rec.get_book_list():
            bought.append(stu)
        else:
            not_bought.append(stu)
    return render_template('book_detail.html', book=book, bought=bought, not_bought=not_bought)

@admin_bp.route('/export_csv/<int:sem_id>')
def export_csv(sem_id):
    if session.get('role') != 'admin': return redirect(url_for('auth.login'))
    semester = Semester.query.get_or_404(sem_id)
    records = OrderRecord.query.filter_by(semester_id=sem_id).all()
    records_by_student = {r.student_id: r for r in records}
    all_students = Student.query.order_by(Student.sid.asc()).all()
    
    si = StringIO()
    si.write('\ufeff') # BOM for Excel
    writer = csv.writer(si)
    
    # --- 修改 1：標題列加入「英文名字」與「Email」 ---
    writer.writerow(['學號', '姓名', '英文名字', 'Email', '總金額', '匯款後五碼', '狀態', '購買書單'])
    
    for stu in all_students:
        rec = records_by_student.get(stu.id)
        status = "已鎖定" if (rec and rec.is_locked) else "未確認"
        
        # --- 修改 2：寫入資料時加入學生的英文名字與 Email ---
        writer.writerow([
            stu.sid, 
            stu.name, 
            stu.english_name or "",  # 如果沒填會是 None，轉為空字串以免報錯
            stu.email or "",         # 如果沒填會是 None，轉為空字串以免報錯
            rec.total_amount if rec else 0,
            rec.bank_last_5 if rec else "",
            status,
            rec.items_summary if rec else ""
        ])
        
    output = BytesIO()
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name=f"report_{semester.name}.csv")

@admin_bp.route('/new_semester', methods=['POST'])
def new_semester():
    if session.get('role') != 'admin': return redirect(url_for('auth.login'))
    Semester.query.update({Semester.is_active: False})
    db.session.add(Semester(name=request.form.get('name'), is_active=True))
    db.session.commit()
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/set_deadline', methods=['POST'])
def set_deadline():
    if session.get('role') != 'admin': return redirect(url_for('auth.login'))
    
    sem_id = request.form.get('sem_id')
    deadline_str = request.form.get('deadline') # 格式: "2024-06-30T23:59"
    
    semester = Semester.query.get(sem_id)
    if semester and deadline_str:
        # 將字串轉為 datetime 物件
        semester.deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
        db.session.commit()
        flash(f"已設定期限：{deadline_str}")
    
    return redirect(url_for('admin.admin_dashboard', sem_id=sem_id))

@admin_bp.route('/toggle_profile_edit/<int:sem_id>', methods=['POST'])
def toggle_profile_edit(sem_id):
    if session.get('role') != 'admin': return redirect(url_for('auth.login'))
    semester = Semester.query.get_or_404(sem_id)
    semester.allow_profile_edit = not semester.allow_profile_edit
    db.session.commit()
    status = "開啟" if semester.allow_profile_edit else "關閉"
    flash(f"已{status}學生個人資料填寫功能！")
    return redirect(url_for('admin.admin_dashboard', sem_id=sem_id))

@admin_bp.route('/delete_semester/<int:sem_id>', methods=['POST'])
def delete_semester(sem_id):
    if session.get('role') != 'admin': return redirect(url_for('auth.login'))
    semester = Semester.query.get_or_404(sem_id)
    
    try:
        # 刪除與此學期相關的訂單紀錄與書籍
        OrderRecord.query.filter_by(semester_id=sem_id).delete()
        Book.query.filter_by(semester_id=sem_id).delete()
        
        # 刪除學期
        db.session.delete(semester)
        db.session.commit()
        flash(f"已成功刪除學期：{semester.name}")
    except Exception as e:
        db.session.rollback()
        flash(f"刪除學期失敗：{str(e)}")
        
    return redirect(url_for('admin.admin_dashboard'))
