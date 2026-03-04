from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
import requests

from .database import engine, Base
from . import models
from .auth import (
    get_db,
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)

from .rag import (
    extract_questions,
    build_vector_index,
    retrieve_context
)

from .export import export_docx


app = FastAPI()

templates = Jinja2Templates(directory="app/templates")

Base.metadata.create_all(bind=engine)


# -------------------------
# LANDING PAGE
# -------------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )


# -------------------------
# SIGNUP
# -------------------------
@app.post("/signup")
def signup(email: str, password: str, db: Session = Depends(get_db)):

    existing_user = db.query(models.User).filter(models.User.email == email).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = models.User(
        email=email,
        hashed_password=hash_password(password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User created successfully"}


# -------------------------
# LOGIN
# -------------------------
@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):

    user = db.query(models.User).filter(models.User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    access_token = create_access_token({"user_id": user.id})

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


# -------------------------
# UPLOAD QUESTIONNAIRE
# -------------------------
@app.post("/upload-questionnaire")
def upload_questionnaire(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):

    user_folder = f"uploads/{current_user.id}/questionnaires"
    os.makedirs(user_folder, exist_ok=True)

    file_path = f"{user_folder}/{file.filename}"

    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())

    questionnaire = models.Questionnaire(
        file_path=file_path,
        user_id=current_user.id
    )

    db.add(questionnaire)
    db.commit()
    db.refresh(questionnaire)

    return {
        "message": "Questionnaire uploaded successfully",
        "questionnaire_id": questionnaire.id
    }


# -------------------------
# UPLOAD REFERENCE DOCUMENT
# -------------------------
@app.post("/upload-reference")
def upload_reference(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):

    user_folder = f"uploads/{current_user.id}/references"
    os.makedirs(user_folder, exist_ok=True)

    file_path = f"{user_folder}/{file.filename}"

    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())

    reference = models.ReferenceDocument(
        file_path=file_path,
        user_id=current_user.id
    )

    db.add(reference)
    db.commit()

    return {"message": "Reference document uploaded successfully"}


# -------------------------
# GENERATE ANSWERS (RAG)
# -------------------------
@app.post("/generate-answers/{questionnaire_id}")
def generate_answers(
    questionnaire_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):

    questionnaire = db.query(models.Questionnaire).filter(
        models.Questionnaire.id == questionnaire_id,
        models.Questionnaire.user_id == current_user.id
    ).first()

    if not questionnaire:
        raise HTTPException(status_code=404, detail="Questionnaire not found")

    questions = extract_questions(questionnaire.file_path)

    references = db.query(models.ReferenceDocument).filter(
        models.ReferenceDocument.user_id == current_user.id
    ).all()

    if not references:
        raise HTTPException(status_code=400, detail="No reference documents uploaded")

    reference_files = [ref.file_path for ref in references]

    index, metadata = build_vector_index(reference_files)

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise HTTPException(status_code=500, detail="OpenRouter API key not set")

    results = []

    for question in questions:

        context, citations, distances = retrieve_context(
            question,
            index,
            metadata
        )

        avg_distance = float(distances.mean())

        if avg_distance < 0.3:
            confidence = "High"
        elif avg_distance < 0.6:
            confidence = "Medium"
        else:
            confidence = "Low"

        prompt = f"""
You are answering a compliance questionnaire.

Use ONLY the reference text below.

If the answer is not supported, return exactly:
Not found in references.

Reference Text:
{context}

Question:
{question}

Answer:
"""

        try:

            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                }
            )

            data = response.json()

            if "choices" in data:
                answer_text = data["choices"][0]["message"]["content"]
            else:
                answer_text = f"Error: {data}"

        except Exception as e:
            answer_text = f"Error generating answer: {str(e)}"

        citation_text = "\n".join(citations)

        new_answer = models.Answer(
            questionnaire_id=questionnaire.id,
            question_text=question,
            answer_text=answer_text,
            citations=citation_text,
            confidence_score=confidence
        )

        db.add(new_answer)

        results.append({
            "question": question,
            "answer": answer_text,
            "citations": citation_text,
            "confidence": confidence
        })

    db.commit()

    return {"results": results}


# -------------------------
# REVIEW PAGE
# -------------------------
@app.get("/review/{questionnaire_id}", response_class=HTMLResponse)
def review_answers(
    questionnaire_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    answers = db.query(models.Answer).filter(
        models.Answer.questionnaire_id == questionnaire_id
    ).all()

    return templates.TemplateResponse(
        "review.html",
        {
            "request": request,
            "answers": answers
        }
    )


# -------------------------
# EXPORT DOCX
# -------------------------
@app.get("/export/{questionnaire_id}")
def export_answers(
    questionnaire_id: int,
    db: Session = Depends(get_db)
):

    answers = db.query(models.Answer).filter(
        models.Answer.questionnaire_id == questionnaire_id
    ).all()

    if not answers:
        raise HTTPException(status_code=404, detail="No answers found")

    file_path = export_docx(answers)

    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="answers.docx"
    )