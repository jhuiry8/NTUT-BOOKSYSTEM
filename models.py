from extensions import db

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sid = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    english_name = db.Column(db.String(100), nullable=True)

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

class Semester(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    # --- 新增期限欄位 ---
    deadline = db.Column(db.DateTime, nullable=True)
    # --- 新增設定：是否開放修改個人資料 ---
    allow_profile_edit = db.Column(db.Boolean, default=True)
