import os
from datetime import datetime, timedelta, timezone
import bcrypt
from dotenv import load_dotenv

load_dotenv()
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from .database import get_db
from .models import UserRole
from .orm_models import User

SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY or len(SECRET_KEY.encode('utf-8')) < 32:
    raise RuntimeError('SECRET_KEY must be set to a value of at least 32 bytes')
ALGORITHM = 'HS256'
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/auth/login')

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user):
    payload={'sub':str(user.id),'role':user.role.role_name.value,'exp':datetime.now(timezone.utc)+timedelta(hours=8)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token=Depends(oauth2_scheme), db: Session=Depends(get_db)):
    try:
        payload=jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id=int(payload['sub'])
    except Exception:
        raise HTTPException(status_code=401, detail='Invalid authentication credentials')
    user=db.scalar(select(User).options(joinedload(User.role)).where(User.id==user_id))
    if not user:
        raise HTTPException(status_code=401, detail='User not found')
    return user

def require_roles(*roles):
    def checker(user=Depends(get_current_user)):
        if user.role.role_name not in roles:
            raise HTTPException(status_code=403, detail='Insufficient permissions')
        return user
    return checker
