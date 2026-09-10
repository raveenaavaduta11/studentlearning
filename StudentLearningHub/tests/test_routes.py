import io

import pytest

from app import create_app
from models import db, Category


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
    })
    with app.app_context():
        db.session.add(Category(key="practical", name="Practical Programs", description="Practice resources"))
        db.session.commit()
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, name="Test Student", email="student@example.com", password="secret1"):
    return client.post("/auth", data={
        "register_submit": "1",
        "name": name,
        "email": email,
        "password": password,
        "confirm_password": password,
    }, follow_redirects=True)


def login(client, email="student@example.com", password="secret1"):
    return client.post("/auth", data={
        "login_submit": "1",
        "email": email,
        "password": password,
    }, follow_redirects=True)


def test_home_route(client):
    response = client.get("/")
    assert response.status_code == 200


def test_auth_route(client):
    response = client.get("/auth")
    assert response.status_code == 200


def test_resources_route(client):
    response = client.get("/resources")
    assert response.status_code == 200


def test_user_can_create_category_during_upload(client, app):
    register(client)
    login(client)

    response = client.post("/upload", data={
        "title": "Data Science Notes",
        "category": "",
        "new_category_name": "Data Science",
        "description": "Introductory notes.",
        "resource_file": (io.BytesIO(b"%PDF-1.4 category test"), "notes.pdf"),
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Resource uploaded successfully" in response.data
    with app.app_context():
        from models import Category
        category = Category.query.filter_by(key="data-science").first()
        assert category is not None
        assert category.description == "Resources about Data Science."


def test_duplicate_category_during_upload_is_rejected(client):
    register(client)
    login(client)

    response = client.post("/upload", data={
        "title": "Duplicate Category Test",
        "category": "",
        "new_category_name": "Practical Programs",
        "description": "Should not upload.",
        "resource_file": (io.BytesIO(b"%PDF-1.4 duplicate test"), "duplicate.pdf"),
    })

    assert b"already exists" in response.data
    assert b"Select it from the category list" in response.data


def test_categories_are_database_driven(app):
    with app.app_context():
        assert Category.query.count() == 1
        assert Category.query.filter_by(key="practical").first() is not None


def test_dashboard_requires_login(client):
    response = client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    assert b"Login to Your Account" in response.data


def test_admin_requires_admin_role(client):
    register(client)
    login(client)
    response = client.get("/admin", follow_redirects=True)
    assert response.status_code == 200
    assert b"Login to Your Account" in response.data


def test_register_and_login_flow(client):
    register_response = register(client)
    assert b"Registration successful" in register_response.data

    login_response = login(client)
    assert b"Login successful" in login_response.data

    dashboard_response = client.get("/dashboard")
    assert dashboard_response.status_code == 200
    assert b"Test Student" in dashboard_response.data


def test_duplicate_registration_is_rejected(client):
    register(client)
    second_attempt = register(client)
    assert b"Email already exists" in second_attempt.data


def test_upload_requires_login(client):
    response = client.get("/upload", follow_redirects=True)
    assert response.status_code == 200
    assert b"Login to Your Account" in response.data


def test_upload_rejects_disallowed_file_type(client):
    register(client)
    login(client)

    data = {
        "title": "Malicious File",
        "category": "practical",
        "description": "test",
        "resource_file": (io.BytesIO(b"fake binary content"), "malware.exe"),
    }
    response = client.post(
        "/upload", data=data, content_type="multipart/form-data", follow_redirects=True,
    )
    assert b"not allowed" in response.data


def test_upload_and_view_resource(client):
    register(client)
    login(client)

    data = {
        "title": "Python Notes",
        "category": "practical",
        "description": "Basic python notes",
        "resource_file": (io.BytesIO(b"%PDF-1.4 fake pdf content"), "notes.pdf"),
    }
    upload_response = client.post(
        "/upload", data=data, content_type="multipart/form-data", follow_redirects=True,
    )
    assert b"Resource uploaded successfully" in upload_response.data

    resources_response = client.get("/resources")
    assert b"Python Notes" in resources_response.data


def test_upload_rejects_mismatched_file_signature(client):
    register(client)
    login(client)

    data = {
        "title": "Not a PDF",
        "category": "practical",
        "description": "The extension does not match the content.",
        "resource_file": (io.BytesIO(b"plain text"), "notes.pdf"),
    }
    response = client.post(
        "/upload", data=data, content_type="multipart/form-data", follow_redirects=True,
    )
    assert b"does not match its extension" in response.data


def test_dashboard_search_filters_user_uploads(client):
    register(client)
    login(client)

    for title in ("Python Notes", "Database Guide"):
        data = {
            "title": title,
            "category": "practical",
            "description": title,
            "resource_file": (io.BytesIO(b"%PDF-1.4 test"), f"{title}.pdf"),
        }
        client.post("/upload", data=data, content_type="multipart/form-data")

    response = client.get("/dashboard?search=Python")
    assert b"Python Notes" in response.data
    assert b"Database Guide" not in response.data


def test_admin_resource_search(client, app):
    register(client)
    login(client)
    with app.app_context():
        from models import User
        user = User.query.filter_by(email="student@example.com").first()
        user.role = "admin"
        db.session.commit()

    response = client.get("/admin?resource_search=notes")
    assert response.status_code == 200


def test_admin_can_edit_and_delete_empty_category(client, app):
    register(client)
    login(client)
    with app.app_context():
        from models import User
        admin = User.query.filter_by(email="student@example.com").first()
        admin.role = "admin"
        category = Category(key="temporary", name="Temporary", description="Old")
        db.session.add(category)
        db.session.commit()
        category_id = category.id

    response = client.post(f"/admin/category/{category_id}/edit", data={
        "name": "Updated Category",
        "description": "Updated description",
    }, follow_redirects=True)
    assert b"Category updated successfully" in response.data

    with app.app_context():
        assert db.session.get(Category, category_id).name == "Updated Category"

    response = client.post(f"/admin/category/{category_id}/delete", follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Category, category_id) is None
