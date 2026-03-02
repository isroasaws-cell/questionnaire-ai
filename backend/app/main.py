from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel

from .database import Base, engine, SessionLocal
from .models import User
from .auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_admin
)

app = FastAPI()

# Create tables
Base.metadata.create_all(bind=engine)


# -----------------------------
# Database Dependency
# -----------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------
# Schemas
# -----------------------------
class RegisterSchema(BaseModel):
    name: str
    email: str
    password: str


# -----------------------------
# Routes
# -----------------------------
@app.get("/")
def home():
    return {"message": "AI Outreach SaaS Running"}


# -----------------------------
# Register User
# -----------------------------
@app.post("/register")
def register(user: RegisterSchema, db: Session = Depends(get_db)):

    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        name=user.name,
        email=user.email,
        hashed_password=hash_password(user.password),
        is_admin=False
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User registered successfully"}


# -----------------------------
# Login (OAuth2 Compatible)
# -----------------------------
@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(User.email == form_data.username).first()

    if not db_user or not verify_password(form_data.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token({"sub": db_user.email})

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


# -----------------------------
# Admin Protected Route
# -----------------------------
@app.get("/admin-dashboard")
def admin_dashboard(current_admin: User = Depends(get_current_admin)):
    return {
        "message": f"Welcome Admin {current_admin.email}"
    }  