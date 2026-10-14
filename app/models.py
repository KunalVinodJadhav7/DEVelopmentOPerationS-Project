from enum import Enum


class UserRole(str, Enum):
    EMPLOYEE = 'employee'
    HR = 'hr'
    MANAGER = 'manager'
    ADMIN = 'admin'
    SUPER_ADMIN = 'super_admin'


class HRVetoCategory(str, Enum):
    POLICY_VIOLATION = 'policy_violation'
    INSUFFICIENT_LEAVE_BALANCE = 'insufficient_leave_balance'
    LEGAL_COMPLIANCE = 'legal_compliance'


class LeaveStatus(str, Enum):
    PENDING_HR = 'PENDING_HR'
    PENDING_MANAGER = 'PENDING_MANAGER'
    PENDING_HR_FINAL = 'PENDING_HR_FINAL'
    PENDING_ADMIN = 'PENDING_ADMIN'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
