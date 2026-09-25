import os
from datetime import date
from pathlib import Path
from fastapi import Depends, FastAPI, Form, HTTPException, UploadFile, File, status
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from .models import UserRole, LeaveStatus
from .orm_models import Role, User, LeaveRequest, AuditLog
from .schemas import UserCreate, LeaveSubmitInput, ReviewInput
from .security import hash_password, verify_password, create_token, require_roles

app=FastAPI(title='Employee Leave Approval System', version='1.2.0')
UPLOAD_DIR=Path(os.getenv('UPLOAD_DIR','uploads')); UPLOAD_DIR.mkdir(exist_ok=True)

@app.on_event('startup')
def startup():
    Base.metadata.create_all(engine)
    db=next(get_db())
    try:
        descriptions={UserRole.EMPLOYEE:'Employee',UserRole.HR:'HR reviewer',UserRole.MANAGER:'Manager reviewer',UserRole.ADMIN:'Admin reviewer',UserRole.SUPER_ADMIN:'Super Admin'}
        for role,desc in descriptions.items():
            if not db.scalar(select(Role).where(Role.role_name==role)):
                db.add(Role(role_name=role,description=desc))
        db.commit()
    finally: db.close()

def audit(db, leave, actor, action, comments):
    db.add(AuditLog(leave_request_id=leave.id, actor_id=actor.id, action_performed=action, comments=comments))

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
def submit_leave(start_date:date=Form(...),end_date:date=Form(...),reason:str=Form(...,min_length=5,max_length=250),supporting_document:UploadFile|None=File(None),current_user=Depends(require_roles(UserRole.EMPLOYEE)),db:Session=Depends(get_db)):
    data=LeaveSubmitInput(start_date=start_date,end_date=end_date,reason=reason)
    document_name=document_path=None
    if supporting_document:
        name=Path(supporting_document.filename or 'document.bin').name
        if Path(name).suffix.lower() not in {'.pdf','.png','.jpg','.jpeg','.doc','.docx'}: raise HTTPException(400,'Unsupported document type')
        target=UPLOAD_DIR/(os.urandom(8).hex()+Path(name).suffix.lower()); target.write_bytes(supporting_document.file.read()); document_name=name; document_path=str(target)
    leave=LeaveRequest(employee_id=current_user.id,start_date=data.start_date,end_date=data.end_date,reason=data.reason,status=LeaveStatus.PENDING_HR,document_name=document_name,document_path=document_path); db.add(leave); db.flush(); audit(db,leave,current_user,'LEAVE_SUBMITTED',reason); db.commit(); db.refresh(leave)
    return {'id':leave.id,'status':leave.status.value}

@app.get('/api/leave/requests')
def list_requests(current_user=Depends(require_roles(UserRole.EMPLOYEE,UserRole.HR,UserRole.MANAGER,UserRole.ADMIN,UserRole.SUPER_ADMIN)),db:Session=Depends(get_db)):
    stmt=select(LeaveRequest).order_by(LeaveRequest.created_at.desc())
    if current_user.role.role_name == UserRole.EMPLOYEE:
        stmt=stmt.where(LeaveRequest.employee_id==current_user.id)
    rows=db.scalars(stmt).all()
    return [{
        'id':x.id,
        'employee_id':x.employee_id,
        'start_date':x.start_date.isoformat(),
        'end_date':x.end_date.isoformat(),
        'reason':x.reason,
        'status':x.status.value,
        'document_name':x.document_name,
        'document_path':x.document_path,
        'hr_comments':x.hr_comments,
        'manager_comments':x.manager_comments,
        'admin_notes':x.admin_notes,
        'created_at':x.created_at.isoformat() if x.created_at else None,
        'updated_at':x.updated_at.isoformat() if x.updated_at else None
    } for x in rows]

@app.get('/api/leave/{leave_id}/audit')
def get_audit(leave_id:int,current_user=Depends(require_roles(UserRole.EMPLOYEE,UserRole.HR,UserRole.MANAGER,UserRole.ADMIN,UserRole.SUPER_ADMIN)),db:Session=Depends(get_db)):
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
        <div class="login-copy"><div class="eyebrow">5-tier approval workflow</div><h1>One place to request, review, approve, and track leave.</h1><p>Sign in to see the workspace designed for your role—from employee submission through final approval and notification.</p></div>
        <div class="auth-card"><div class="tabs"><button class="active" onclick="showTab('login')">Sign in</button><button onclick="showTab('register')">Create account</button></div>
          <form id="loginForm" class="form-grid" onsubmit="login(event)"><div class="field wide"><label>Username</label><input name="username" autocomplete="username" required placeholder="employee1"></div><div class="field wide"><label>Password</label><input name="password" type="password" autocomplete="current-password" required></div><div class="wide"><button class="btn primary" style="width:100%">Sign in</button></div></form>
          <form id="registerForm" class="form-grid hidden" onsubmit="register(event)"><div class="field"><label>Username</label><input name="username" required></div><div class="field"><label>Email</label><input name="email" type="email" required></div><div class="field wide"><label>Password</label><input name="password" type="password" minlength="8" required></div><div class="field wide"><label>Role</label><select name="role"><option value="employee">Employee</option><option value="hr">HR</option><option value="manager">Manager</option><option value="admin">Admin</option><option value="super_admin">Super Admin</option></select></div><div class="wide"><button class="btn primary" style="width:100%">Create account</button></div></form><div id="authAlert"></div></div>
      </section>
      <section class="login-art"><div class="login-art-card"><div class="eyebrow" style="color:#9ab6d8">Approval journey</div><h2 style="font-size:32px;margin:8px 0 20px">See exactly where every request is.</h2><div class="workflow-map"><div class="workflow-node"><strong>1 · Employee</strong><span>Submit a leave request and supporting document.</span></div><div class="workflow-node"><strong>2 · HR</strong><span>Verify policy, compliance, and documents.</span></div><div class="workflow-node"><strong>3 · Manager</strong><span>Review the team impact and approve or reject.</span></div><div class="workflow-node"><strong>4 · Admin</strong><span>Make the final authorization decision.</span></div><div class="workflow-node"><strong>5 · Super Admin</strong><span>Dispatch the employee notification.</span></div></div></div></section>
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
def manager_review(leave_id:int,payload:ReviewInput,current_user=Depends(require_roles(UserRole.MANAGER,UserRole.SUPER_ADMIN)),db:Session=Depends(get_db)):
    leave=db.get(LeaveRequest,leave_id)
    if not leave: raise HTTPException(404,'Leave request not found')
    if leave.status!=LeaveStatus.PENDING_MANAGER: raise HTTPException(400,'Request is not pending Manager review')
    leave.manager_comments=payload.comments; leave.status=LeaveStatus.PENDING_ADMIN if payload.approved else LeaveStatus.REJECTED; audit(db,leave,current_user,'MANAGER_APPROVED' if payload.approved else 'MANAGER_REJECTED',payload.comments); db.commit(); return {'id':leave.id,'status':leave.status.value}

@app.patch('/api/leave/{leave_id}/admin-finalize')
def admin_finalize(leave_id:int,payload:ReviewInput,current_user=Depends(require_roles(UserRole.ADMIN,UserRole.SUPER_ADMIN)),db:Session=Depends(get_db)):
    leave=db.get(LeaveRequest,leave_id)
    if not leave: raise HTTPException(404,'Leave request not found')
    if leave.status!=LeaveStatus.PENDING_ADMIN: raise HTTPException(400,'Request is not pending Admin oversight')
    leave.admin_notes=payload.comments; leave.status=LeaveStatus.APPROVED if payload.approved else LeaveStatus.REJECTED; audit(db,leave,current_user,'ADMIN_APPROVED' if payload.approved else 'ADMIN_REJECTED',payload.comments); db.commit(); return {'id':leave.id,'status':leave.status.value}

@app.post('/api/leave/{leave_id}/notify-employee')
def notify_employee(leave_id:int,current_user=Depends(require_roles(UserRole.SUPER_ADMIN)),db:Session=Depends(get_db)):
    leave=db.get(LeaveRequest,leave_id)
    if not leave: raise HTTPException(404,'Leave request not found')
    if leave.status not in {LeaveStatus.APPROVED,LeaveStatus.REJECTED}: raise HTTPException(400,'Final decision is required before notification')
    audit(db,leave,current_user,'EMPLOYEE_NOTIFICATION_DISPATCHED',leave.status.value); db.commit(); return {'message':'Notification dispatched','leave_id':leave.id,'status':leave.status.value}

@app.patch('/api/leave/{leave_id}/hr-review')
def hr_review(leave_id:int,payload:ReviewInput,current_user=Depends(require_roles(UserRole.HR,UserRole.SUPER_ADMIN)),db:Session=Depends(get_db)):
    leave=db.get(LeaveRequest,leave_id)
    if not leave: raise HTTPException(404,'Leave request not found')
    if leave.status!=LeaveStatus.PENDING_HR: raise HTTPException(400,'Request is not pending HR review')
    leave.hr_comments=payload.comments; leave.status=LeaveStatus.PENDING_MANAGER if payload.approved else LeaveStatus.REJECTED; audit(db,leave,current_user,'HR_APPROVED' if payload.approved else 'HR_REJECTED',payload.comments); db.commit(); return {'id':leave.id,'status':leave.status.value}
