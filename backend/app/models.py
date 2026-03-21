from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


# -----------------------------
# USER MODEL
# -----------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    campaigns = relationship("Campaign", back_populates="owner")


# -----------------------------
# CAMPAIGN MODEL
# -----------------------------
class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String, nullable=False)
    description = Column(Text)
    resume_text = Column(Text)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user_id = Column(Integer, ForeignKey("users.id"))

    # Relationship
    owner = relationship("User", back_populates="campaigns")