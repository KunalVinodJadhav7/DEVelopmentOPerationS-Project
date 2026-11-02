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



def test_super_admin_notification_is_recorded_in_request_audit():
    _, employee_token = _register_unique_user("employee")
    _, manager_token = _register_unique_user("manager")
    _, hr_token = _register_unique_user("hr")
    _, admin_token = _register_unique_user("admin")
    _, super_admin_token = _register_unique_user("super_admin")
    start, _ = _weekday_pair()

    submitted = client.post(
        "/api/leave/submit",
        data={
            "start_date": start.isoformat(),
            "end_date": start.isoformat(),
            "reason": "Notification audit regression test",
            "leave_type_code": "CL",
        },
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert submitted.status_code == 200, submitted.text
    leave_id = submitted.json()["id"]

    manager_result = client.patch(
        f"/api/leave/{leave_id}/manager-approve",
        json={"approved": True, "comments": "Approved based on workload and team coverage."},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert manager_result.status_code == 200, manager_result.text

    hr_result = client.patch(
        f"/api/leave/{leave_id}/hr-review",
        json={"approved": True, "comments": "No policy or compliance issue found."},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert hr_result.status_code == 200, hr_result.text

    admin_result = client.patch(
        f"/api/leave/{leave_id}/admin-finalize",
        json={"approved": True, "comments": "Final authorization approved."},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_result.status_code == 200, admin_result.text

    notification = client.post(
        f"/api/leave/{leave_id}/notify-employee",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert notification.status_code == 200, notification.text
    assert notification.json()["audit_action"] == "EMPLOYEE_NOTIFICATION_DISPATCHED"
    assert notification.json()["audit_event_id"]

    audit = client.get(
        f"/api/leave/{leave_id}/audit",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert audit.status_code == 200, audit.text
    notification_event = next(
        (row for row in audit.json() if "notif" in row["action_performed"].lower()),
        None,
    )
    assert notification_event is not None, audit.json()
    assert notification_event["action_performed"] == "EMPLOYEE_NOTIFICATION_DISPATCHED"
    assert notification_event["comments"] == "APPROVED"



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
        json={"approved": False, "comments": "The request conflicts with the documented leave policy.", "veto_category": "policy_violation"},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert hr_veto.status_code == 200, hr_veto.text
    assert hr_veto.json()["status"] == "REJECTED"
    assert hr_veto.json()["action"] == "HR_VETOED_MANAGER_APPROVAL"
    assert hr_veto.json()["hr_veto_category"] == "policy_violation"

    request_rows = client.get(
        "/api/leave/requests",
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert request_rows.status_code == 200, request_rows.text
    request_row = next(row for row in request_rows.json() if row["id"] == leave_id)
    assert request_row["hr_veto_category"] == "policy_violation"
    assert request_row["hr_comments"] == "The request conflicts with the documented leave policy."

    audit = client.get(
        f"/api/leave/{leave_id}/audit",
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert audit.status_code == 200, audit.text
    actions = [row["action_performed"] for row in audit.json()]
    assert "MANAGER_APPROVED_PENDING_HR_REVIEW" in actions
    assert "HR_VETOED_MANAGER_APPROVAL" in actions
    veto_event = next(row for row in audit.json() if row["action_performed"] == "HR_VETOED_MANAGER_APPROVAL")
    assert "Policy violation" in veto_event["comments"]
    assert "documented leave policy" in veto_event["comments"]


def test_hr_veto_requires_allowed_category_and_specific_reason():
    _, employee_token = _register_unique_user("employee")
    _, hr_token = _register_unique_user("hr")
    _, manager_token = _register_unique_user("manager")
    start, _ = _weekday_pair()

    submitted = client.post(
        "/api/leave/submit",
        data={"start_date": start.isoformat(), "end_date": start.isoformat(), "reason": "HR veto validation test", "leave_type_code": "CL"},
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert submitted.status_code == 200, submitted.text
    leave_id = submitted.json()["id"]

    blank_manager_reason = client.patch(
        f"/api/leave/{leave_id}/manager-approve",
        json={"approved": True, "comments": "          "},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert blank_manager_reason.status_code == 422

    manager_using_hr_veto_category = client.patch(
        f"/api/leave/{leave_id}/manager-approve",
        json={"approved": True, "comments": "Approved based on team coverage and workload.", "veto_category": "policy_violation"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert manager_using_hr_veto_category.status_code == 422

    manager = client.patch(
        f"/api/leave/{leave_id}/manager-approve",
        json={"approved": True, "comments": "Approved based on team coverage and workload."},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert manager.status_code == 200, manager.text

    missing_category = client.patch(
        f"/api/leave/{leave_id}/hr-review",
        json={"approved": False, "comments": "Detailed reason for veto is here."},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert missing_category.status_code == 422

    whitespace_reason = client.patch(
        f"/api/leave/{leave_id}/hr-review",
        json={"approved": False, "comments": "          ", "veto_category": "policy_violation"},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert whitespace_reason.status_code == 422

    short_reason = client.patch(
        f"/api/leave/{leave_id}/hr-review",
        json={"approved": False, "comments": "Policy", "veto_category": "policy_violation"},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert short_reason.status_code == 422

    invalid_category = client.patch(
        f"/api/leave/{leave_id}/hr-review",
        json={"approved": False, "comments": "This is a sufficiently specific reason.", "veto_category": "performance_concern"},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert invalid_category.status_code == 422

    valid_veto = client.patch(
        f"/api/leave/{leave_id}/hr-review",
        json={"approved": False, "comments": "There is insufficient available leave balance for this period.", "veto_category": "insufficient_leave_balance"},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert valid_veto.status_code == 200, valid_veto.text
    assert valid_veto.json()["status"] == "REJECTED"
    assert valid_veto.json()["hr_veto_category"] == "insufficient_leave_balance"


def test_hr_cannot_issue_a_veto_when_manager_rejected():
    _, employee_token = _register_unique_user("employee")
    _, hr_token = _register_unique_user("hr")
    _, manager_token = _register_unique_user("manager")
    start, _ = _weekday_pair()

    submitted = client.post(
        "/api/leave/submit",
        data={"start_date": start.isoformat(), "end_date": start.isoformat(), "reason": "Manager rejection cannot be vetoed", "leave_type_code": "CL"},
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert submitted.status_code == 200, submitted.text
    leave_id = submitted.json()["id"]

    manager = client.patch(
        f"/api/leave/{leave_id}/manager-approve",
        json={"approved": False, "comments": "Rejected due to staffing coverage requirements."},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert manager.status_code == 200, manager.text

    invalid_veto = client.patch(
        f"/api/leave/{leave_id}/hr-review",
        json={"approved": False, "comments": "This is a policy violation veto.", "veto_category": "policy_violation"},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert invalid_veto.status_code == 400

    confirmation = client.patch(
        f"/api/leave/{leave_id}/hr-review",
        json={"approved": True, "comments": "HR confirms the Manager rejection."},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert confirmation.status_code == 200, confirmation.text
    assert confirmation.json()["status"] == "REJECTED"
    assert confirmation.json()["action"] == "HR_CONFIRMED_MANAGER_REJECTION"


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
