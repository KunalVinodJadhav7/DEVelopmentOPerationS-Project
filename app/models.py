from enum import Enum

class UserRole(str, Enum):
    EMPLOYEE = 'employee'
    HR = 'hr'
    MANAGER = 'manager'
    ADMIN = 'admin'
    SUPER_ADMIN = 'super_admin'

class LeaveStatus(str, Enum):
    PENDING_HR = 'PENDING_HR'
    PENDING_MANAGER = 'PENDING_MANAGER'
    PENDING_ADMIN = 'PENDING_ADMIN'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
