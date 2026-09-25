import gc
import os
from pathlib import Path


# Test environment configuration
TEST_DB = Path("build/test_leave.db")
TEST_UPLOAD_DIR = Path("build/test-uploads")

TEST_DB.parent.mkdir(parents=True, exist_ok=True)
TEST_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.absolute()}"
os.environ["SECRET_KEY"] = "test-secret-key-32-bytes-minimum-value-123456"
os.environ["UPLOAD_DIR"] = str(TEST_UPLOAD_DIR.absolute())


# Application imports

from fastapi.testclient import TestClient

from app.database import engine
from app.main import app, startup


# Test client
startup()
client = TestClient(app)


# Test helpers
def token(username, password):
    response = client.post(
        "/api/auth/login",
        data={
            "username": username,
            "password": password,
        },
    )

    assert response.status_code == 200, response.text

    return response.json()["access_token"]


# Test setup / teardown
def setup_module():
    for username, role in [
        ("emp1", "employee"),
        ("hr1", "hr"),
    ]:
        response = client.post(
            "/api/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "Passw0rd!",
                "role": role,
            },
        )

        assert response.status_code in (200, 409), response.text


def teardown_module():
    # Release SQLAlchemy connections before deleting the SQLite file.
    engine.dispose()
    gc.collect()

    if TEST_DB.exists():
        TEST_DB.unlink()


# Tests
def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_employee_submission_and_hr_review():
    emp = token("emp1", "Passw0rd!")

    response = client.post(
        "/api/leave/submit",
        data={
            "start_date": "2026-10-01",
            "end_date": "2026-10-03",
            "reason": "Family trip",
        },
        headers={
            "Authorization": f"Bearer {emp}",
        },
    )

    assert response.status_code == 200

    leave_id = response.json()["id"]

    hr = token("hr1", "Passw0rd!")

    response = client.patch(
        f"/api/leave/{leave_id}/hr-review",
        json={
            "approved": True,
            "comments": "Checked",
        },
        headers={
            "Authorization": f"Bearer {hr}",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "PENDING_MANAGER"

def teardown_module():
    engine.dispose()
    gc.collect()

    if TEST_DB.exists():
        TEST_DB.unlink()