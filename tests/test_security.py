from sqlalchemy import create_engine, inspect, text

from app import _add_missing_columns, create_app
from extensions import db
from models import Book, OrderRecord, Semester, Student
from routes.admin import csv_safe


def login_as_student(client, student_id):
    with client.session_transaction() as session:
        session['role'] = 'student'
        session['user_id'] = student_id


def test_order_rejects_book_from_another_semester(app, client):
    with app.app_context():
        current = Semester(name='current', is_active=True)
        archived = Semester(name='archived', is_active=False)
        student = Student(sid='112001', name='Student')
        db.session.add_all([current, archived, student])
        db.session.flush()
        foreign_book = Book(
            semester_id=archived.id,
            title='Wrong semester',
            price=999,
        )
        db.session.add(foreign_book)
        db.session.commit()
        student_id = student.id
        foreign_book_id = foreign_book.id

    login_as_student(client, student_id)
    response = client.post('/student/', data={
        'book_ids': [str(foreign_book_id)],
    })

    assert response.status_code == 302
    with app.app_context():
        record = OrderRecord.query.filter_by(student_id=student_id).one()
        assert record.is_locked is False
        assert record.total_amount == 0


def test_post_without_csrf_token_is_rejected():
    application = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': True,
    })
    response = application.test_client().post('/', data={
        'sid': 'someone',
        'name': 'someone',
    })
    assert response.status_code == 400


def test_csv_safe_neutralizes_spreadsheet_formulas():
    assert csv_safe('=HYPERLINK("https://example.invalid")').startswith("'=")
    assert csv_safe('+1+1').startswith("'+")
    assert csv_safe('normal@example.com') == 'normal@example.com'


def test_legacy_column_upgrade_preserves_existing_rows():
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(text(
            'CREATE TABLE book ('
            'id INTEGER PRIMARY KEY, title VARCHAR(100), price INTEGER)'
        ))
        connection.execute(text(
            "INSERT INTO book (id, title, price) VALUES (1, 'Existing book', 500)"
        ))

    _add_missing_columns(engine, 'book', {
        'remark': 'TEXT',
        'display_order': 'INTEGER DEFAULT 0',
    })

    assert {'remark', 'display_order'} <= {
        column['name'] for column in inspect(engine).get_columns('book')
    }
    with engine.connect() as connection:
        row = connection.execute(text(
            'SELECT title, price FROM book WHERE id = 1'
        )).one()
    assert row == ('Existing book', 500)
