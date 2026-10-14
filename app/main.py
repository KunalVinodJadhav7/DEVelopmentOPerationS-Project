import os
from datetime import date, timedelta
from pathlib import Path
from fastapi import Depends, FastAPI, Form, HTTPException, UploadFile, File, status
from fastapi.responses import HTMLResponse, FileResponse, Response
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from .models import UserRole, LeaveStatus, HRVetoCategory
from .orm_models import Role, User, LeavePolicy, LeaveRequest, AuditLog
from .schemas import UserCreate, LeaveSubmitInput, ReviewInput, LeavePolicyCreate, LeavePolicyUpdate
from .security import hash_password, verify_password, create_token, require_roles

app=FastAPI(title='Employee Leave Approval System', version='1.4.0')
UPLOAD_DIR=Path(os.getenv('UPLOAD_DIR','uploads')); UPLOAD_DIR.mkdir(exist_ok=True)

@app.on_event('startup')
def startup():
    Base.metadata.create_all(engine)
    _migrate_existing_database()
    db=next(get_db())
    try:
        descriptions={UserRole.EMPLOYEE:'Employee',UserRole.HR:'HR reviewer',UserRole.MANAGER:'Manager reviewer',UserRole.ADMIN:'Admin reviewer',UserRole.SUPER_ADMIN:'Super Admin'}
        for role,desc in descriptions.items():
            if not db.scalar(select(Role).where(Role.role_name==role)):
                db.add(Role(role_name=role,description=desc))
        # These are initial defaults only. Authorized administrators can change
        # allowances and add/disable types through the policy management API.
        defaults = [
            ('CL', 'Casual Leave', 12),
            ('EL', 'Earned Leave', 15),
        ]
        for code, name, allowance in defaults:
            if not db.scalar(select(LeavePolicy).where(LeavePolicy.code == code)):
                db.add(LeavePolicy(code=code, name=name, annual_allowance=allowance, enabled=True))
        db.commit()
    finally: db.close()

def _migrate_existing_database():
    """Apply safe, versioned migrations for databases created by older releases."""
    inspected_columns = inspect(engine).get_columns('leave_requests')
    columns = {column['name'] for column in inspected_columns}
    status_column = next((column for column in inspected_columns if column['name'] == 'status'), None)
    with engine.begin() as connection:
        if 'leave_type_code' not in columns:
            connection.execute(text("ALTER TABLE leave_requests ADD COLUMN leave_type_code VARCHAR(10) NOT NULL DEFAULT 'CL'"))
        # PENDING_HR_FINAL is longer than the previous longest status. Older
        # PostgreSQL databases need the status column widened before it is stored.
        if engine.dialect.name == 'postgresql' and status_column is not None:
            old_length = getattr(status_column['type'], 'length', None)
            if old_length is not None and old_length < 20:
                connection.execute(text('ALTER TABLE leave_requests ALTER COLUMN status TYPE VARCHAR(20)'))
        connection.execute(text(
            "CREATE TABLE IF NOT EXISTS app_migrations ("
            "migration_key VARCHAR(100) PRIMARY KEY, "
            "applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL)"
        ))
        if 'manager_approved' not in columns:
            connection.execute(text('ALTER TABLE leave_requests ADD COLUMN manager_approved BOOLEAN NULL'))
        if 'hr_veto_category' not in columns:
            connection.execute(text('ALTER TABLE leave_requests ADD COLUMN hr_veto_category VARCHAR(50) NULL'))

        migration_key = 'week15_manager_first_hr_second_v2'
        applied = connection.execute(
            text('SELECT migration_key FROM app_migrations WHERE migration_key = :key'),
            {'key': migration_key},
        ).first()
        if not applied:
            # Requests from the old HR-first flow now enter the Manager queue.
            connection.execute(
                text("UPDATE leave_requests SET status = :new_status WHERE status = :old_status"),
                {'new_status': LeaveStatus.PENDING_MANAGER.value, 'old_status': LeaveStatus.PENDING_HR.value},
            )
            # Previously Admin-ready requests already passed Manager approval,
            # so send them through the new final HR check and preserve that fact.
            connection.execute(
                text("UPDATE leave_requests SET status = :new_status, manager_approved = TRUE WHERE status = :old_status"),
                {'new_status': LeaveStatus.PENDING_HR_FINAL.value, 'old_status': LeaveStatus.PENDING_ADMIN.value},
            )
            # Compatibility with databases that briefly ran the earlier Week 15
            # patch, where Manager approvals were in PENDING_HR_FINAL but the
            # decision had not yet been stored in its own column.
            connection.execute(
                text("UPDATE leave_requests SET manager_approved = TRUE WHERE status = :status AND manager_approved IS NULL"),
                {'status': LeaveStatus.PENDING_HR_FINAL.value},
            )
            connection.execute(
                text('INSERT INTO app_migrations (migration_key) VALUES (:key)'),
                {'key': migration_key},
            )

def audit(db, leave, actor, action, comments):
    db.add(AuditLog(leave_request_id=leave.id, actor_id=actor.id, action_performed=action, comments=comments))

def _workdays_by_year(start_date: date, end_date: date) -> dict[int, int]:
    """Count weekdays inclusively by calendar year; public holidays are not excluded."""
    counts = {}
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            counts[current.year] = counts.get(current.year, 0) + 1
        current += timedelta(days=1)
    return counts

def _workdays_in_year(start_date: date, end_date: date, year: int) -> int:
    first = max(start_date, date(year, 1, 1))
    last = min(end_date, date(year, 12, 31))
    if first > last:
        return 0
    return _workdays_by_year(first, last).get(year, 0)

def _policy_dict(policy: LeavePolicy) -> dict:
    return {
        'code': policy.code,
        'name': policy.name,
        'annual_allowance': policy.annual_allowance,
        'enabled': policy.enabled,
    }

def _leave_balances(db: Session, employee_id: int, year: int) -> list[dict]:
    policies = db.scalars(select(LeavePolicy).order_by(LeavePolicy.code.asc())).all()
    requests = db.scalars(
        select(LeaveRequest).where(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status != LeaveStatus.REJECTED,
        )
    ).all()
    balances = []
    for policy in policies:
        used = sum(
            _workdays_in_year(request.start_date, request.end_date, year)
            for request in requests
            if request.leave_type_code == policy.code
        )
        balances.append({
            **_policy_dict(policy),
            'year': year,
            'used_or_reserved_days': used,
            'remaining_days': max(0, policy.annual_allowance - used),
        })
    return balances

@app.get('/health')
def health(): return {'status':'ok','database':engine.url.get_backend_name()}

@app.post('/api/auth/register')
def register(payload:UserCreate,db:Session=Depends(get_db)):
    if db.scalar(select(User).where((User.username==payload.username)|(User.email==str(payload.email)))): raise HTTPException(409,'Username or email already exists')
    role=db.scalar(select(Role).where(Role.role_name==payload.role))
    user=User(username=payload.username,email=str(payload.email),password_hash=hash_password(payload.password),role=role); db.add(user); db.commit(); db.refresh(user)
    return {'id':user.id,'username':user.username,'email':user.email,'role':user.role.role_name.value}

@app.post('/api/auth/login')
def login(username:str=Form(...),password:str=Form(...),db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.username==username))
    if not user or not verify_password(password,user.password_hash): raise HTTPException(401,'Invalid username or password')
    return {'access_token':create_token(user),'token_type':'bearer'}

@app.post('/api/leave/submit')
def submit_leave(start_date:date=Form(...),end_date:date=Form(...),reason:str=Form(...,min_length=5,max_length=250),leave_type_code:str=Form('CL'),supporting_document:UploadFile|None=File(None),current_user=Depends(require_roles(UserRole.EMPLOYEE)),db:Session=Depends(get_db)):
    data=LeaveSubmitInput(start_date=start_date,end_date=end_date,reason=reason,leave_type_code=leave_type_code)
    policy=db.scalar(select(LeavePolicy).where(LeavePolicy.code==data.leave_type_code))
    if not policy or not policy.enabled:
        raise HTTPException(400, f'Leave type {data.leave_type_code} is not available')
    requested_by_year=_workdays_by_year(data.start_date,data.end_date)
    if not requested_by_year:
        raise HTTPException(400,'Leave must include at least one weekday (Monday-Friday)')
    overlapping=db.scalar(select(LeaveRequest.id).where(
        LeaveRequest.employee_id==current_user.id,
        LeaveRequest.status!=LeaveStatus.REJECTED,
        LeaveRequest.start_date<=data.end_date,
        LeaveRequest.end_date>=data.start_date,
    ).limit(1))
    if overlapping:
        raise HTTPException(409,'This date range overlaps an existing approved or pending leave request')
    prior_requests=db.scalars(select(LeaveRequest).where(
        LeaveRequest.employee_id==current_user.id,
        LeaveRequest.leave_type_code==policy.code,
        LeaveRequest.status!=LeaveStatus.REJECTED,
    )).all()
    for year, requested_days in requested_by_year.items():
        reserved=sum(_workdays_in_year(item.start_date,item.end_date,year) for item in prior_requests)
        remaining=max(0,policy.annual_allowance-reserved)
        if requested_days > remaining:
            raise HTTPException(400, f'Insufficient {policy.code} balance for {year}: {requested_days} workday(s) requested, {remaining} remaining')
    document_name=document_path=None
    if supporting_document:
        name=Path(supporting_document.filename or 'document.bin').name
        if Path(name).suffix.lower() not in {'.pdf','.png','.jpg','.jpeg','.doc','.docx'}: raise HTTPException(400,'Unsupported document type')
        target=UPLOAD_DIR/(os.urandom(8).hex()+Path(name).suffix.lower()); target.write_bytes(supporting_document.file.read()); document_name=name; document_path=str(target)
    leave=LeaveRequest(employee_id=current_user.id,start_date=data.start_date,end_date=data.end_date,reason=data.reason,status=LeaveStatus.PENDING_MANAGER,leave_type_code=policy.code,document_name=document_name,document_path=document_path); db.add(leave); db.flush(); audit(db,leave,current_user,'LEAVE_SUBMITTED',f'{policy.code} ({sum(requested_by_year.values())} workday(s)): {reason}'); db.commit(); db.refresh(leave)
    return {'id':leave.id,'status':leave.status.value,'leave_type_code':leave.leave_type_code,'requested_days':sum(requested_by_year.values())}

@app.get('/api/leave/requests')
def list_requests(current_user=Depends(require_roles(UserRole.EMPLOYEE,UserRole.HR,UserRole.MANAGER,UserRole.ADMIN,UserRole.SUPER_ADMIN)),db:Session=Depends(get_db)):
    stmt=select(LeaveRequest).order_by(LeaveRequest.created_at.desc())
    if current_user.role.role_name == UserRole.EMPLOYEE:
        stmt=stmt.where(LeaveRequest.employee_id==current_user.id)
    rows=db.scalars(stmt).all()
    policy_names={p.code:p.name for p in db.scalars(select(LeavePolicy)).all()}
    return [{
        'id':x.id,
        'employee_id':x.employee_id,
        'start_date':x.start_date.isoformat(),
        'end_date':x.end_date.isoformat(),
        'reason':x.reason,
        'leave_type_code':x.leave_type_code,
        'leave_type_name':policy_names.get(x.leave_type_code, x.leave_type_code),
        'requested_days':sum(_workdays_by_year(x.start_date, x.end_date).values()),
        'status':x.status.value,
        'document_name':x.document_name,
        'document_path':x.document_path,
        'hr_comments':x.hr_comments,
        'hr_veto_category':x.hr_veto_category,
        'manager_comments':x.manager_comments,
        'manager_approved':x.manager_approved,
        'admin_notes':x.admin_notes,
        'created_at':x.created_at.isoformat() if x.created_at else None,
        'updated_at':x.updated_at.isoformat() if x.updated_at else None
    } for x in rows]

@app.get('/api/leave/{leave_id}/audit')
def get_audit(leave_id: int, response: Response, current_user=Depends(require_roles(UserRole.EMPLOYEE, UserRole.HR, UserRole.MANAGER, UserRole.ADMIN, UserRole.SUPER_ADMIN)), db: Session=Depends(get_db)):
    # Audit data must be read fresh after each decision/notification.
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    leave=db.get(LeaveRequest,leave_id)
    if not leave:
        raise HTTPException(404,'Leave request not found')
    if current_user.role.role_name == UserRole.EMPLOYEE and leave.employee_id != current_user.id:
        raise HTTPException(403,'Cannot view another employee\'s audit')
    rows=db.scalars(select(AuditLog).where(AuditLog.leave_request_id==leave_id).order_by(AuditLog.timestamp.asc())).all()
    return [{'id':x.id,'leave_request_id':x.leave_request_id,'actor_id':x.actor_id,'action_performed':x.action_performed,'comments':x.comments,'timestamp':x.timestamp.isoformat() if x.timestamp else None} for x in rows]

@app.get('/api/leave/{leave_id}/document')
def get_document(leave_id: int, current_user=Depends(require_roles(
    UserRole.EMPLOYEE, UserRole.HR, UserRole.MANAGER, UserRole.ADMIN, UserRole.SUPER_ADMIN
)), db: Session = Depends(get_db)):
    leave=db.get(LeaveRequest, leave_id)
    if not leave:
        raise HTTPException(404, 'Leave request not found')
    if current_user.role.role_name == UserRole.EMPLOYEE and leave.employee_id != current_user.id:
        raise HTTPException(403, 'Cannot access another employee document')
    if not leave.document_path or not Path(leave.document_path).is_file():
        raise HTTPException(404, 'Supporting document not found')
    return FileResponse(leave.document_path, filename=leave.document_name or 'document')

def _frontend_shell():
    return Path('frontend/index.html').read_text()

@app.get('/employee', response_class=HTMLResponse)
def employee_page():
    return _frontend_shell()

@app.get('/hr', response_class=HTMLResponse)
def hr_page():
    return _frontend_shell()

@app.get('/manager', response_class=HTMLResponse)
def manager_page():
    return _frontend_shell()

@app.get('/admin', response_class=HTMLResponse)
def admin_page():
    return _frontend_shell()

@app.get('/super-admin', response_class=HTMLResponse)
def super_admin_page():
    return _frontend_shell()

@app.get('/dashboard', response_class=HTMLResponse)
def dashboard():
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LeaveFlow | Sign in</title><link rel="stylesheet" href="/frontend/styles.css"></head><body>
    <div class="login-shell">
      <section class="login-panel">
        <div class="login-brand"><div class="brand-mark">LF</div><div><strong style="font-size:18px">LeaveFlow</strong><div style="color:#6b7280;font-size:12px">Enterprise Leave Approval System</div></div></div>
        <div class="login-copy"><div class="eyebrow">Multi-stage approval workflow</div><h1>One place to request, review, approve, and track leave.</h1><p>Sign in to see the workspace designed for your role—from employee submission through final approval and notification.</p></div>
        <div class="auth-card"><div class="tabs"><button class="active" onclick="showTab('login')">Sign in</button><button onclick="showTab('register')">Create account</button></div>
          <form id="loginForm" class="form-grid" onsubmit="login(event)"><div class="field wide"><label>Username</label><input name="username" autocomplete="username" required placeholder="employee1"></div><div class="field wide"><label>Password</label><input name="password" type="password" autocomplete="current-password" required></div><div class="wide"><button class="btn primary" style="width:100%">Sign in</button></div></form>
          <form id="registerForm" class="form-grid hidden" onsubmit="register(event)"><div class="field"><label>Username</label><input name="username" required></div><div class="field"><label>Email</label><input name="email" type="email" required></div><div class="field wide"><label>Password</label><input name="password" type="password" minlength="8" required></div><div class="field wide"><label>Role</label><select name="role"><option value="employee">Employee</option><option value="hr">HR</option><option value="manager">Manager</option><option value="admin">Admin</option><option value="super_admin">Super Admin</option></select></div><div class="wide"><button class="btn primary" style="width:100%">Create account</button></div></form><div id="authAlert"></div></div>
      </section>
      <section class="login-art"><div class="login-art-card"><div class="eyebrow" style="color:#9ab6d8">Approval journey</div><h2 style="font-size:32px;margin:8px 0 20px">See exactly where every request is.</h2><div class="workflow-map"><div class="workflow-node"><strong>1 · Employee</strong><span>Submit a leave request and supporting document.</span></div><div class="workflow-node"><strong>2 · Manager</strong><span>Independently approve or reject first.</span></div><div class="workflow-node"><strong>3 · HR limited veto</strong><span>Veto a Manager approval only for policy, leave-balance, or legal/compliance reasons, with a specific explanation.</span></div><div class="workflow-node"><strong>4 · Admin</strong><span>Make the final authorization decision.</span></div><div class="workflow-node"><strong>5 · Super Admin</strong><span>Dispatch the employee notification.</span></div></div></div></section>
    </div><script>
      function showTab(t){document.querySelectorAll('.tabs button').forEach((b,i)=>b.classList.toggle('active',(t==='login'?i===0:i===1)));document.getElementById('loginForm').classList.toggle('hidden',t!=='login');document.getElementById('registerForm').classList.toggle('hidden',t!=='register')}
      async function login(e){e.preventDefault();const f=new FormData(e.target);const r=await fetch('/api/auth/login',{method:'POST',body:f});const j=await r.json();if(!r.ok){document.getElementById('authAlert').innerHTML='<div class="alert error">'+(j.detail||'Login failed')+'</div>';return}localStorage.setItem('leave_token',j.access_token);const m=await fetch('/api/auth/me',{headers:{Authorization:'Bearer '+j.access_token}});const u=await m.json();location.href=u.role==='employee'?'/employee':'/'+u.role.replace('_','-');}
      async function register(e){e.preventDefault();const f=new FormData(e.target);const p=Object.fromEntries(f.entries());const r=await fetch('/api/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});const j=await r.json();if(!r.ok){document.getElementById('authAlert').innerHTML='<div class="alert error">'+(j.detail||'Registration failed')+'</div>';return}showTab('login');document.getElementById('authAlert').innerHTML='<div class="alert ok">Account created. Sign in to continue.</div>';document.querySelector('#loginForm input[name=username]').value=p.username;}
    </script></body></html>'''

@app.get('/frontend/{file_path:path}')
def frontend_assets(file_path: str):
    root = Path('frontend').resolve()
    target = (root / file_path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise HTTPException(status_code=404, detail='Frontend asset not found')
    return FileResponse(target)

@app.get('/api/auth/me')
def current_user(current_user=Depends(require_roles(
    UserRole.EMPLOYEE, UserRole.HR, UserRole.MANAGER, UserRole.ADMIN, UserRole.SUPER_ADMIN
))):
    return {
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'role': current_user.role.role_name.value
    }

@app.patch('/api/leave/{leave_id}/manager-approve')
def manager_review(leave_id: int, payload: ReviewInput, current_user=Depends(require_roles(UserRole.MANAGER, UserRole.SUPER_ADMIN)), db: Session = Depends(get_db)):
    leave = db.get(LeaveRequest, leave_id)
    if not leave:
        raise HTTPException(404, 'Leave request not found')
    if leave.status != LeaveStatus.PENDING_MANAGER:
        raise HTTPException(400, 'Request is not pending Manager review')
    if payload.veto_category is not None:
        raise HTTPException(422, 'Veto categories are reserved for HR vetoes')
    if len(payload.comments) < 10:
        raise HTTPException(422, 'Provide a clear Manager rationale (at least 10 characters)')

    leave.manager_comments = payload.comments
    leave.manager_approved = payload.approved
    leave.status = LeaveStatus.PENDING_HR_FINAL
    action = 'MANAGER_APPROVED_PENDING_HR_REVIEW' if payload.approved else 'MANAGER_REJECTED_PENDING_HR_REVIEW'
    audit(db, leave, current_user, action, payload.comments)
    db.commit()
    return {
        'id': leave.id,
        'status': leave.status.value,
        'manager_approved': leave.manager_approved,
        'action': action,
    }


@app.patch('/api/leave/{leave_id}/admin-finalize')
def admin_finalize(leave_id: int, payload: ReviewInput, current_user=Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)), db: Session = Depends(get_db)):
    leave = db.get(LeaveRequest, leave_id)
    if not leave:
        raise HTTPException(404, 'Leave request not found')
    if leave.status != LeaveStatus.PENDING_ADMIN:
        raise HTTPException(400, 'Request is not pending Admin oversight')
    if payload.veto_category is not None:
        raise HTTPException(422, 'Veto categories are reserved for HR vetoes')

    leave.admin_notes = payload.comments
    leave.status = LeaveStatus.APPROVED if payload.approved else LeaveStatus.REJECTED
    action = 'ADMIN_APPROVED' if payload.approved else 'ADMIN_REJECTED'
    audit(db, leave, current_user, action, payload.comments)
    db.commit()
    return {'id': leave.id, 'status': leave.status.value, 'action': action}


@app.post('/api/leave/{leave_id}/notify-employee')
def notify_employee(leave_id: int, current_user=Depends(require_roles(UserRole.SUPER_ADMIN)), db: Session = Depends(get_db)):
    leave = db.get(LeaveRequest, leave_id)
    if not leave:
        raise HTTPException(404, 'Leave request not found')
    if leave.status not in {LeaveStatus.APPROVED, LeaveStatus.REJECTED}:
        raise HTTPException(400, 'Final decision is required before notification')

    # Persist the notification event explicitly and verify its values after
    # reloading the row. Do not return success for an incomplete audit event.
    notification_action = 'EMPLOYEE_NOTIFICATION_DISPATCHED'
    notification_status = leave.status.value
    event = AuditLog(
        leave_request_id=leave.id,
        actor_id=current_user.id,
        action_performed=notification_action,
        comments=notification_status,
    )
    db.add(event)
    db.flush()
    db.execute(
        text('UPDATE audit_logs SET action_performed = :action, comments = :comments WHERE id = :event_id'),
        {'action': notification_action, 'comments': notification_status, 'event_id': event.id},
    )
    db.commit()
    db.refresh(event)
    if event.action_performed != notification_action or event.comments != notification_status:
        raise HTTPException(500, 'Notification was processed but its audit event could not be verified')

    return {
        'message': 'Notification dispatched',
        'leave_id': leave.id,
        'status': leave.status.value,
        'audit_event_id': event.id,
        'audit_action': event.action_performed,
    }


@app.patch('/api/leave/{leave_id}/hr-review')
def hr_review(leave_id: int, payload: ReviewInput, current_user=Depends(require_roles(UserRole.HR, UserRole.SUPER_ADMIN)), db: Session = Depends(get_db)):
    leave = db.get(LeaveRequest, leave_id)
    if not leave:
        raise HTTPException(404, 'Leave request not found')
    if leave.status != LeaveStatus.PENDING_HR_FINAL:
        raise HTTPException(400, 'Manager must record an approve/reject decision before HR final review')
    if leave.manager_approved is None:
        raise HTTPException(409, 'Manager decision is missing; the request must be reviewed by Manager first')

    # Model A: HR is a limited compliance/policy veto, not a second Manager.
    # If Manager rejected, HR records a confirmation and cannot reopen it.
    if leave.manager_approved is False:
        if not payload.approved:
            raise HTTPException(400, 'HR cannot veto a Manager rejection; confirm the existing rejection')
        if payload.veto_category is not None:
            raise HTTPException(422, 'A veto category is only valid when vetoing a Manager approval')
        leave.status = LeaveStatus.REJECTED
        leave.hr_veto_category = None
        action = 'HR_CONFIRMED_MANAGER_REJECTION'
        audit_comments = payload.comments
    elif payload.approved:
        if payload.veto_category is not None:
            raise HTTPException(422, 'Do not supply a veto category when approving for Admin review')
        leave.status = LeaveStatus.PENDING_ADMIN
        leave.hr_veto_category = None
        action = 'HR_FINAL_REVIEW_APPROVED'
        audit_comments = payload.comments
    else:
        if payload.veto_category is None:
            raise HTTPException(
                422,
                'Choose a permitted HR veto category: policy violation, insufficient leave balance, or legal/compliance issue',
            )
        if len(payload.comments) < 10:
            raise HTTPException(422, 'Provide a specific HR veto reason (at least 10 characters)')

        category_labels = {
            HRVetoCategory.POLICY_VIOLATION: 'Policy violation',
            HRVetoCategory.INSUFFICIENT_LEAVE_BALANCE: 'Insufficient leave balance',
            HRVetoCategory.LEGAL_COMPLIANCE: 'Legal/compliance issue',
        }
        leave.status = LeaveStatus.REJECTED
        leave.hr_veto_category = payload.veto_category.value
        action = 'HR_VETOED_MANAGER_APPROVAL'
        audit_comments = f"Veto category: {category_labels[payload.veto_category]}. Reason: {payload.comments}"

    leave.hr_comments = payload.comments
    audit(db, leave, current_user, action, audit_comments)
    db.commit()
    return {
        'id': leave.id,
        'status': leave.status.value,
        'action': action,
        'manager_approved': leave.manager_approved,
        'hr_veto_category': leave.hr_veto_category,
    }


@app.get('/api/leave/types')
def list_leave_types(current_user=Depends(require_roles(UserRole.EMPLOYEE,UserRole.HR,UserRole.MANAGER,UserRole.ADMIN,UserRole.SUPER_ADMIN)),db:Session=Depends(get_db)):
    policies=db.scalars(select(LeavePolicy).where(LeavePolicy.enabled.is_(True)).order_by(LeavePolicy.code.asc())).all()
    return [_policy_dict(policy) for policy in policies]

@app.get('/api/leave/balances')
def get_leave_balances(year:int|None=None,current_user=Depends(require_roles(UserRole.EMPLOYEE,UserRole.HR,UserRole.MANAGER,UserRole.ADMIN,UserRole.SUPER_ADMIN)),db:Session=Depends(get_db)):
    balance_year=year or date.today().year
    if balance_year < 2000 or balance_year > 2200:
        raise HTTPException(400,'Year must be between 2000 and 2200')
    return {'employee_id':current_user.id,'year':balance_year,'balances':_leave_balances(db,current_user.id,balance_year)}

@app.get('/api/admin/leave-policies')
def admin_list_leave_policies(current_user=Depends(require_roles(UserRole.ADMIN,UserRole.SUPER_ADMIN)),db:Session=Depends(get_db)):
    return [_policy_dict(policy) for policy in db.scalars(select(LeavePolicy).order_by(LeavePolicy.code.asc())).all()]

@app.post('/api/admin/leave-policies',status_code=201)
def admin_create_leave_policy(payload:LeavePolicyCreate,current_user=Depends(require_roles(UserRole.ADMIN,UserRole.SUPER_ADMIN)),db:Session=Depends(get_db)):
    if db.scalar(select(LeavePolicy).where(LeavePolicy.code==payload.code)):
        raise HTTPException(409,f'Leave type {payload.code} already exists')
    policy=LeavePolicy(code=payload.code,name=payload.name,annual_allowance=payload.annual_allowance,enabled=payload.enabled)
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return _policy_dict(policy)

@app.patch('/api/admin/leave-policies/{code}')
def admin_update_leave_policy(code:str,payload:LeavePolicyUpdate,current_user=Depends(require_roles(UserRole.ADMIN,UserRole.SUPER_ADMIN)),db:Session=Depends(get_db)):
    normalized=code.strip().upper()
    policy=db.scalar(select(LeavePolicy).where(LeavePolicy.code==normalized))
    if not policy:
        raise HTTPException(404,'Leave policy not found')
    policy.name=payload.name
    policy.annual_allowance=payload.annual_allowance
    policy.enabled=payload.enabled
    db.commit()
    db.refresh(policy)
    return _policy_dict(policy)
