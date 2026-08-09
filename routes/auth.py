import os
from flask import Blueprint, request, redirect, url_for, flash, session, render_template
from models import Student

auth_bp = Blueprint('auth', __name__)

ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASSWORD', 'admin')

@auth_bp.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        sid = request.form.get('sid')
        name = request.form.get('name')
        
        # 管理員登入
        if sid == ADMIN_USER and name == ADMIN_PASS:
            session['role'] = 'admin'
            return redirect(url_for('admin.admin_dashboard'))

        # 學生登入
        user = Student.query.filter_by(sid=sid, name=name).first()
        if user:
            session['user_id'] = user.id
            session['role'] = 'student'
            return redirect(url_for('student.student_area'))
        else:
            flash("登入失敗：學號或姓名錯誤 (非本班學生)")
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
