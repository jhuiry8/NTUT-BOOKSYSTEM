from flask import Blueprint, request, redirect, url_for, flash, session, render_template
from datetime import datetime, timedelta
from extensions import db
from models import Student, Semester, Book, OrderRecord

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/', methods=['GET', 'POST'])
def student_area():
    # 1. 權限檢查
    if session.get('role') != 'student': 
        return redirect(url_for('auth.login'))
    
    user = Student.query.get(session['user_id'])
    current_sem = Semester.query.filter_by(is_active=True).first()
    
    if not current_sem: 
        return "目前沒有開放訂書。"

    # 2. 時間與過期檢查 (加入 Log)
    now_tw = datetime.utcnow() + timedelta(hours=8)
    is_expired = False
    if current_sem.deadline:
        if now_tw > current_sem.deadline:
            is_expired = True
            print(f"[DEBUG] 系統判定過期！現在: {now_tw}, 期限: {current_sem.deadline}")
        else:
            print(f"[DEBUG] 尚未過期。現在: {now_tw}, 期限: {current_sem.deadline}")
    else:
        print("[DEBUG] 本學期未設定期限")

    # 3. 取得或建立訂單
    record = OrderRecord.query.filter_by(student_id=user.id, semester_id=current_sem.id).first()
    if not record:
        print(f"[DEBUG] 學生 {user.name} 尚無紀錄，建立新空單")
        record = OrderRecord(student_id=user.id, semester_id=current_sem.id)
        db.session.add(record)
        db.session.commit()

    books = Book.query.filter_by(semester_id=current_sem.id).order_by(Book.display_order.asc(), Book.id.asc()).all()

    # --- 處理表單提交 (POST) ---
    if request.method == 'POST':
        print(f"--- [DEBUG] 收到 POST 請求: 學生 {user.name} ---")

        # A. 檢查是否過期
        if is_expired:
            flash("❌ 已經超過填寫期限，系統拒絕儲存！")
            print("[DEBUG] 儲存失敗：已過期")
            return redirect(url_for('student.student_area'))

        # B. 檢查是否已鎖定
        if record.is_locked:
            flash("訂單已鎖定，無法重複修改。")
            print("[DEBUG] 儲存失敗：已鎖定")
            return redirect(url_for('student.student_area'))
            
        # C. 讀取表單資料
        selected_ids = request.form.getlist('book_ids')
        bank_code = request.form.get('bank_code')
        
        print(f"[DEBUG] 勾選書本 ID: {selected_ids}")
        print(f"[DEBUG] 勾選書本數量: {len(selected_ids)}")
        print("[DEBUG] 匯款帳號輸入已收到 (已隱藏)")
        # D. 安全性處理：防止匯款帳號超過 5 碼導致資料庫崩潰
        if bank_code and len(bank_code) > 5:
            bank_code = bank_code[:5]
            print(f"[DEBUG] 匯款帳號過長，已自動截斷為: {bank_code}")

        # E. 計算金額與摘要
        total = 0
        titles = []
        try:
            requested_ids = {int(book_id) for book_id in selected_ids}
        except ValueError:
            flash("書籍資料格式錯誤，請重新選擇。")
            return redirect(url_for('student.student_area'))

        selected_books = Book.query.filter(
            Book.id.in_(requested_ids),
            Book.semester_id == current_sem.id,
        ).all() if requested_ids else []
        if len(selected_books) != len(requested_ids):
            flash("書單包含無效或非本學期書籍，訂單未儲存。")
            return redirect(url_for('student.student_area'))

        for book in selected_books:
            total += book.price
            titles.append(book.title)
        
        # F. 更新資料庫物件
        try:
            record.items_summary = ", ".join(titles)
            record.total_amount = total
            record.bank_last_5 = bank_code
            record.is_locked = True # 鎖定訂單
            
            db.session.commit() # 這裡是最關鍵的一步
            print(f"[DEBUG] 資料庫 Commit 成功！總金額: {total}")
            flash("訂購成功！")
            
        except Exception as e:
            db.session.rollback() # 如果失敗就回滾
            print(f"[ERROR] 資料庫寫入失敗: {str(e)}")
            flash("系統錯誤：資料儲存失敗，請稍後再試")
            return redirect(url_for('student.student_area'))

        return redirect(url_for('student.student_area'))

    # GET 請求回傳頁面
    return render_template('student.html', user=user, sem=current_sem, books=books, record=record, is_expired=is_expired)

@student_bp.route('/update_profile', methods=['POST'])
def update_profile():
    # 檢查權限
    if session.get('role') != 'student': 
        return redirect(url_for('auth.login'))
    
    current_sem = Semester.query.filter_by(is_active=True).first()
    if current_sem and not current_sem.allow_profile_edit:
        flash("❌ 目前未開放修改個人資料！")
        return redirect(url_for('student.student_area'))
    
    user = Student.query.get(session['user_id'])
    if user:
        # 讀取表單資料並更新 (截斷過長字串避免報錯)
        email = request.form.get('email')
        english_name = request.form.get('english_name')
        
        user.email = email[:120] if email else None
        user.english_name = english_name[:100] if english_name else None
        
        try:
            db.session.commit()
            flash("✅ 個人資料更新成功！")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ 更新失敗：{str(e)}")
            
    return redirect(url_for('student.student_area'))

@student_bp.route('/update_bank_code', methods=['POST'])
def update_bank_code():
    if session.get('role') != 'student': 
        return redirect(url_for('auth.login'))
    
    current_sem = Semester.query.filter_by(is_active=True).first()
    if not current_sem: return redirect(url_for('student.student_area'))
    
    now_tw = datetime.utcnow() + timedelta(hours=8)
    if current_sem.deadline and now_tw > current_sem.deadline:
        flash("❌ 已經超過填寫期限，無法修改匯款帳號！")
        return redirect(url_for('student.student_area'))
        
    user = Student.query.get(session['user_id'])
    record = OrderRecord.query.filter_by(student_id=user.id, semester_id=current_sem.id).first()
    
    if record and record.is_locked:
        bank_code = request.form.get('bank_code')
        if bank_code and len(bank_code) > 5:
            bank_code = bank_code[:5]
        record.bank_last_5 = bank_code
        try:
            db.session.commit()
            flash("✅ 匯款帳號更新成功！")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ 更新失敗：{str(e)}")
        
    return redirect(url_for('student.student_area'))
