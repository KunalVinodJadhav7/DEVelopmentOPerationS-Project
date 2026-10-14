# Week 15 Enhancement Notes

## Scope

The FastAPI OpenAPI version is updated from `1.2.0` to `1.4.0` for this feature release.

This change set adds two post-review enhancements while preserving the existing FastAPI, PostgreSQL/SQLite, frontend, Gradle, Jenkins, Docker Compose, Nginx and Ansible structure:

1. Configurable leave types and annual entitlements (initial examples: CL and EL).
2. Model A: Manager decides first; HR has a limited, reason-required veto for policy, leave-balance, or legal/compliance concerns, followed by Admin finalization only after HR clears a Manager approval.

## 1. Configurable leave types and balances

On first startup, the application seeds these defaults only if the corresponding policy code does not already exist:

| Code | Name | Initial annual allowance |
|---|---|---:|
| `CL` | Casual Leave | 12 workdays |
| `EL` | Earned Leave | 15 workdays |

These are editable sample values and should be changed to match the organization's official policy. Allowances are stored in the `leave_policies` table, not hard-coded into the request route.

Admins and Super Admins can use the **Leave policies** page to create types, change the name and annual allowance, and enable/disable a type. The code remains stable after creation so requests and audit history keep their reference. Disabled types are hidden from new submissions but remain present for historical requests.

Employees can choose a type on the leave form and see their annual balance cards. Requests show their type code and requested workday count.

### Balance rules

- Workdays are counted inclusively from Monday to Friday.
- Public holidays are not excluded because a holiday calendar is not currently configured.
- Allowances reset by calendar year; requests spanning years are counted in each relevant year.
- Pending requests reserve their workdays to prevent oversubscription while they are under review.
- Rejected requests do not consume balance.
- A request containing no weekdays is rejected.
- Requests overlapping another approved or pending request for the same employee are rejected.
- Annual allowance can be configured from 0 to 260 workdays.

### API

- `GET /api/leave/types` — list enabled types for authenticated users.
- `GET /api/leave/balances?year=2026` — current user's balance for the requested calendar year; omitting `year` uses the current year.
- `GET /api/admin/leave-policies` — list all policies, including disabled types (Admin/Super Admin).
- `POST /api/admin/leave-policies` — create a type (Admin/Super Admin).
- `PATCH /api/admin/leave-policies/{code}` — update a type's name, allowance and enabled state (Admin/Super Admin).
- `POST /api/leave/submit` — accepts an additional `leave_type_code` form field. Existing clients that omit it continue to default to `CL`.

Example policy payload:

```json
{
  "code": "SL",
  "name": "Sick Leave",
  "annual_allowance": 10,
  "enabled": true
}
```

## 2. Manager decision followed by HR final review

The updated approval flow is:

```text
Employee submits
       |
       v
PENDING_MANAGER
       | Manager approves or rejects
       v
PENDING_HR_FINAL
       | HR final review
       |------------------------------|
       | Manager approved + HR passes| Manager rejected + HR confirms
       v                              v
PENDING_ADMIN                  REJECTED
       | Admin finalizes
       v
APPROVED or REJECTED
       | Super Admin notification
       v
Employee can see final result and audit history
```

The Manager can approve or reject immediately after submission; HR does not need to act first. Both Manager decisions advance to `PENDING_HR_FINAL`, so HR receives a separate final-review item regardless of the Manager outcome. If the Manager approved, HR may allow the request to proceed to Admin or veto it by rejecting. If the Manager rejected, HR must still record a final review, but an HR approval confirms the rejection rather than overriding it. The Admin endpoint accepts only `PENDING_ADMIN`, so it cannot bypass HR. Each decision is recorded in the audit trail, including `MANAGER_APPROVED_PENDING_HR_REVIEW`, `MANAGER_REJECTED_PENDING_HR_REVIEW`, `HR_FINAL_REVIEW_APPROVED`, `HR_VETOED_MANAGER_APPROVAL`, and `HR_CONFIRMED_MANAGER_REJECTION`.

The frontend exposes Manager approve/reject actions for `PENDING_MANAGER` and the HR **Review** action for `PENDING_HR_FINAL`. Manager's independent decision is displayed in request cards and details.

## 3. Model A: limited HR veto contract

The Manager makes the operational decision first, considering workload, staffing, and team priorities. The Manager records a nonblank explanation of at least 10 characters. Each Manager decision is independently recorded in the audit trail.

HR does not make a second unrestricted business decision. If the Manager approved the request, HR may either pass it to Admin or veto only for one of these structured categories:

- `policy_violation` — conflict with a documented leave policy.
- `insufficient_leave_balance` — the employee lacks available entitlement for the requested period.
- `legal_compliance` — legal, regulatory, or compliance issue.

Every veto must select one permitted category and submit a specific, nonblank reason of at least 10 characters. The category is stored in `leave_requests.hr_veto_category`; the reason is stored in `hr_comments`; and both category and reason are included in the audit event `HR_VETOED_MANAGER_APPROVAL`. An unknown category, missing category, whitespace-only reason, or too-short reason is rejected by the API. UI checks are convenience only; the API is authoritative.

If the Manager rejected the request, HR can record a confirmation of that rejection but cannot turn it into an approval or issue a separate veto. The HR screen therefore offers only **Confirm rejection** in this case. A Manager approval that passes HR review moves to `PENDING_ADMIN`; an HR veto moves directly to `REJECTED` and cannot be overridden by Admin. Manager, HR, and Admin comment fields are trimmed and whitespace-only comments are rejected.

The leave-request migration adds `hr_veto_category` as a nullable column, preserving existing request history. Existing requests receive no invented category; the field remains `NULL` unless a new, qualifying HR veto is recorded.

## 4. Database compatibility

At startup, SQLAlchemy creates the new `leave_policies` table. An additive migration checks whether `leave_requests.leave_type_code` exists and adds it with the default value `CL` when an older database is detected. PostgreSQL's existing `status` column is widened to `VARCHAR(20)` when necessary for the new `PENDING_HR_FINAL` status. A versioned migration moves legacy `PENDING_HR` requests into the Manager queue, routes prior Admin-ready requests through the new HR final-review queue, and stores historical Manager approval where it can be inferred safely. The migration marker prevents requests from being re-queued on subsequent restarts. Existing requests therefore remain valid and are associated with CL unless an administrator updates records separately.

Before deploying against important data, take a normal database backup. The migration is additive and does not drop tables or volumes.

## 5. Modified files

- `app/models.py` — workflow statuses and the allow-listed HR veto category enum.
- `app/orm_models.py` — `LeavePolicy`, leave type code, Manager decision, and persisted HR veto category.
- `app/schemas.py` — leave-type/policy schemas, trimmed decision comments, and HR veto category validation.
- `app/main.py` — policy seeding/migration, balance enforcement, Model A server-side veto rules, and Manager-first/HR-final state transitions.
- `frontend/app.js` — type selector, balance display, admin policy page, limited HR veto category selector, and recorded-rationale display.
- `frontend/styles.css` — balance/policy layouts and new status styling.
- `tests/test_api.py` — tests for configurable policies/balances, Manager-first transitions, required HR veto categories/reasons, and Manager rejection confirmation.
- `selenium_tests/test_workflow.py` — CSS/XPath-compatible click helper, current Manager toast assertions, and HR veto category coverage.
- `README.md` — new behavior summarized.

The existing `Jenkinsfile`, `Dockerfile`, `docker-compose.yml`, Ansible playbook and Gradle build configuration were not changed by this patch. Keep those working files as-is.

## 6. Verification

Run locally from the repository root:

```powershell
py -m pytest tests/test_api.py -q
node --check frontend/app.js
py -m py_compile app/main.py app/models.py app/orm_models.py app/schemas.py
```

For the full project pipeline, run the existing Jenkins job with the normal project parameters and verify unit tests, Gradle, Docker deployment, Ansible's second-run idempotency gate, `/health` and Selenium. The updated Selenium workflow requires a new browser test to verify the mandatory HR veto screen; it should be run in the project's existing Selenium-capable environment.
