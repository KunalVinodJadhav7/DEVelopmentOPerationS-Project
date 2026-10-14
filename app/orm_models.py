from datetime import datetime, date
from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base
from .models import UserRole, LeaveStatus


class Role(Base):
    __tablename__ = 'roles'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_name: Mapped[UserRole] = mapped_column(Enum(UserRole, native_enum=False), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey('roles.id', ondelete='CASCADE'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    role = relationship('Role')


class LeavePolicy(Base):
    __tablename__ = 'leave_policies'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    annual_allowance: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LeaveRequest(Base):
    __tablename__ = 'leave_requests'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(250), nullable=False)
    status: Mapped[LeaveStatus] = mapped_column(Enum(LeaveStatus, native_enum=False), default=LeaveStatus.PENDING_MANAGER)
    # The policy code is kept as a string so existing databases can be upgraded
    # safely with a simple additive migration.
    leave_type_code: Mapped[str] = mapped_column(String(10), nullable=False, default='CL', server_default='CL')
    document_name: Mapped[str | None] = mapped_column(String(255))
    document_path: Mapped[str | None] = mapped_column(String(500))
    hr_comments: Mapped[str | None] = mapped_column(Text)
    # Structured category is populated only when HR vetoes a Manager approval.
    hr_veto_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    manager_comments: Mapped[str | None] = mapped_column(Text)
    manager_approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    leave_request_id: Mapped[int] = mapped_column(ForeignKey('leave_requests.id', ondelete='CASCADE'))
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    action_performed: Mapped[str] = mapped_column(String(100))
    comments: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
