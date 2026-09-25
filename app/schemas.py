from datetime import date
from pydantic import BaseModel, EmailStr, Field, model_validator
from .models import LeaveStatus, UserRole

class LeaveSubmitInput(BaseModel):
    start_date: date
    end_date: date
    reason: str = Field(min_length=5, max_length=250)
    @model_validator(mode='after')
    def validate_dates(self):
        if self.start_date > self.end_date:
            raise ValueError('start_date cannot be later than end_date')
        return self

class ReviewInput(BaseModel):
    approved: bool
    comments: str = Field(min_length=1, max_length=2000)

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.EMPLOYEE
