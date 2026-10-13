import gc
import os
import uuid
from datetime import date, timedelta
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
        ("manager1", "manager"),
        ("admin1", "admin"),
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


def test_employee_submission_requires_manager_before_hr_review():
    emp = token("emp1", "Passw0rd!")
    response = client.post(
        "/api/leave/submit",
        data={
            "start_date": "2026-10-01",
            "end_date": "2026-10-03",
            "reason": "Family trip",
        },
        headers={"Authorization": f"Bearer {emp}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "PENDING_MANAGER"
    leave_id = response.json()["id"]

    hr = token("hr1", "Passw0rd!")
    blocked_hr = client.patch(
        f"/api/leave/{leave_id}/hr-review",
        json={"approved": True, "comments": "HR cannot review first"},
        headers={"Authorization": f"Bearer {hr}"},
    )
    assert blocked_hr.status_code == 400

    manager = token("manager1", "Passw0rd!")
    manager_result = client.patch(
        f"/api/leave/{leave_id}/manager-approve",
        json={"approved": True, "comments": "Manager independently approved"},
        headers={"Authorization": f"Bearer {manager}"},
    )
    assert manager_result.status_code == 200, manager_result.text
    assert manager_result.json()["status"] == "PENDING_HR_FINAL"
    assert manager_result.json()["manager_approved"] is True

    hr_result = client.patch(
        f"/api/leave/{leave_id}/hr-review",
        json={"approved": True, "comments": "HR final review passed"},
        headers={"Authorization": f"Bearer {hr}"},
    )
    assert hr_result.status_code == 200, hr_result.text
    assert hr_result.json()["status"] == "PENDING_ADMIN"

def teardown_module():
    engine.dispose()
    gc.collect()

    if TEST_DB.exists():
        TEST_DB.unlink()

# Week 15 enhancement tests -------------------------------------------------

def _register_unique_user(role):
    username = f"w15_{role}_{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "Passw0rd!",
            "role": role,
        },
    )
    assert response.status_code == 200, response.text
    return username, token(username, "Passw0rd!")


def _weekday_pair():
    start = date.today() + timedelta(days=20)
    while start.weekday() >= 5:
        start += timedelta(days=1)
    end = start + timedelta(days=1)
    while end.weekday() >= 5:
        end += timedelta(days=1)
    return start, end


def test_leave_policy_defaults_and_admin_can_add_policy():
    emp = token("emp1", "Passw0rd!")
    response = client.get("/api/leave/types", headers={"Authorization": f"Bearer {emp}"})
    assert response.status_code == 200, response.text
    codes = {row["code"] for row in response.json()}
    assert {"CL", "EL"}.issubset(codes)

    admin = token("admin1", "Passw0rd!")
    response = client.post(
        "/api/admin/leave-policies",
        json={"code": "TST", "name": "Test Leave", "annual_allowance": 1, "enabled": True},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["annual_allowance"] == 1


def test_leave_balance_reserves_pending_requests_and_prevents_overuse():
    employee_name, employee_token = _register_unique_user("employee")
    # Policy setup is idempotent for repeatable development runs.
    admin = token("admin1", "Passw0rd!")
    policy = client.get(
        "/api/admin/leave-policies",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert policy.status_code == 200, policy.text
    if not any(item["code"] == "TST" for item in policy.json()):
        created = client.post(
            "/api/admin/leave-policies",
            json={"code": "TST", "name": "Test Leave", "annual_allowance": 1, "enabled": True},
            headers={"Authorization": f"Bearer {admin}"},
        )
        assert created.status_code == 201, created.text

    start, next_weekday = _weekday_pair()
    first = client.post(
        "/api/leave/submit",
        data={"start_date": start.isoformat(), "end_date": start.isoformat(), "reason": "Test day off", "leave_type_code": "TST"},
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["requested_days"] == 1

    balances = client.get(
        "/api/leave/balances",
        params={"year": start.year},
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert balances.status_code == 200, balances.text
    test_balance = next(item for item in balances.json()["balances"] if item["code"] == "TST")
    assert test_balance["used_or_reserved_days"] == 1
    assert test_balance["remaining_days"] == 0

    second = client.post(
        "/api/leave/submit",
        data={"start_date": next_weekday.isoformat(), "end_date": next_weekday.isoformat(), "reason": "Another test day", "leave_type_code": "TST"},
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert second.status_code == 400
    assert "Insufficient TST balance" in second.json()["detail"]


def test_hr_can_veto_after_manager_approval_and_admin_cannot_bypass_it():
    _, employee_token = _register_unique_user("employee")
    _, hr_token = _register_unique_user("hr")
    _, manager_token = _register_unique_user("manager")
    _, admin_token = _register_unique_user("admin")
    start, _ = _weekday_pair()

    submitted = client.post(
        "/api/leave/submit",
        data={"start_date": start.isoformat(), "end_date": start.isoformat(), "reason": "Manager and HR veto test", "leave_type_code": "CL"},
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert submitted.status_code == 200, submitted.text
    leave_id = submitted.json()["id"]
    assert submitted.json()["status"] == "PENDING_MANAGER"

    manager = client.patch(
        f"/api/leave/{leave_id}/manager-approve",
        json={"approved": True, "comments": "Manager independently approved"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert manager.status_code == 200, manager.text
    assert manager.json()["status"] == "PENDING_HR_FINAL"
    assert manager.json()["manager_approved"] is True

    premature_admin = client.patch(
        f"/api/leave/{leave_id}/admin-finalize",
        json={"approved": True, "comments": "Should not bypass HR"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert premature_admin.status_code == 400

    hr_veto = client.patch(
        f"/api/leave/{leave_id}/hr-review",
        json={"approved": False, "comments": "HR veto: policy concern"},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert hr_veto.status_code == 200, hr_veto.text
    assert hr_veto.json()["status"] == "REJECTED"
    assert hr_veto.json()["action"] == "HR_FINAL_REVIEW_REJECTED"

    audit = client.get(
        f"/api/leave/{leave_id}/audit",
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert audit.status_code == 200, audit.text
    actions = [row["action_performed"] for row in audit.json()]
    assert "MANAGER_APPROVED_PENDING_HR_REVIEW" in actions
    assert "HR_FINAL_REVIEW_REJECTED" in actions


def test_manager_rejection_still_goes_to_hr_and_cannot_be_overridden():
    _, employee_token = _register_unique_user("employee")
    _, hr_token = _register_unique_user("hr")
    _, manager_token = _register_unique_user("manager")
    start, _ = _weekday_pair()
    submitted = client.post(
        "/api/leave/submit",
        data={"start_date": start.isoformat(), "end_date": start.isoformat(), "reason": "Manager rejection HR confirmation", "leave_type_code": "CL"},
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert submitted.status_code == 200, submitted.text
    leave_id = submitted.json()["id"]

    manager = client.patch(
        f"/api/leave/{leave_id}/manager-approve",
        json={"approved": False, "comments": "Manager rejected independently"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert manager.status_code == 200, manager.text
    assert manager.json()["status"] == "PENDING_HR_FINAL"
    assert manager.json()["manager_approved"] is False

    hr_confirm = client.patch(
        f"/api/leave/{leave_id}/hr-review",
        json={"approved": True, "comments": "HR confirms Manager rejection"},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert hr_confirm.status_code == 200, hr_confirm.text
    assert hr_confirm.json()["status"] == "REJECTED"
    assert hr_confirm.json()["action"] == "HR_CONFIRMED_MANAGER_REJECTION"

    # HR cannot reach an HR review again after the final decision.
    second_hr_review = client.patch(
        f"/api/leave/{leave_id}/hr-review",
        json={"approved": True, "comments": "Duplicate review"},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert second_hr_review.status_code == 400
