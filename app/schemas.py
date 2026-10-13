from datetime import date
from pydantic import BaseModel, EmailStr, Field, model_validator, field_validator
from .models import UserRole


class LeaveSubmitInput(BaseModel):
    start_date: date
    end_date: date
    reason: str = Field(min_length=5, max_length=250)
    leave_type_code: str = Field(default='CL', min_length=2, max_length=10)

    @model_validator(mode='after')
    def validate_dates(self):
        if self.start_date > self.end_date:
            raise ValueError('start_date cannot be later than end_date')
        return self

    @field_validator('leave_type_code')
    @classmethod
    def normalize_leave_type(cls, value: str) -> str:
        return value.strip().upper()


class ReviewInput(BaseModel):
    approved: bool
    comments: str = Field(min_length=1, max_length=2000)


class LeavePolicyCreate(BaseModel):
    code: str = Field(min_length=2, max_length=10, pattern=r'^[A-Z][A-Z0-9_]{1,9}$')
    name: str = Field(min_length=2, max_length=80)
    annual_allowance: int = Field(ge=0, le=260)
    enabled: bool = True

    @field_validator('code', mode='before')
    @classmethod
    def uppercase_code(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator('name')
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()


class LeavePolicyUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    annual_allowance: int = Field(ge=0, le=260)
    enabled: bool = True

    @field_validator('name')
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.EMPLOYEE
