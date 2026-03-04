from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    questionnaires = relationship("Questionnaire", back_populates="owner")


class Questionnaire(Base):
    __tablename__ = "questionnaires"

    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="questionnaires")
    answers = relationship("Answer", back_populates="questionnaire")


class ReferenceDocument(Base):
    __tablename__ = "reference_documents"

    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))


class Answer(Base):
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, index=True)
    questionnaire_id = Column(Integer, ForeignKey("questionnaires.id"))
    question_text = Column(Text)
    answer_text = Column(Text)
    citations = Column(Text)
    confidence_score = Column(String)

    questionnaire = relationship("Questionnaire", back_populates="answers")