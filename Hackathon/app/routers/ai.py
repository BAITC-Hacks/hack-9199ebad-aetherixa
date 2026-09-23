from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import ai_service, schemas, models
from app.database import get_db
from app.workflow import invalidate_confirmation
from app.ui_seed import ensure_task_placements

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _draft(db, task_id, draft_text):
    if not draft_text.strip():
        raise HTTPException(422, "Введите описание задачи")
    if task_id:
        task = db.get(models.Task, task_id)
        if not task:
            raise HTTPException(404, "Задача не найдена")
    else:
        task = models.Task(title=draft_text[:80], tag="общее")
        db.add(task)
    task.draft_text = draft_text
    invalidate_confirmation(task)
    db.flush()
    ensure_task_placements(db, task)
    return task


@router.post("/analyze", response_model=schemas.AiAnalyzeOut)
async def analyze(payload: schemas.AiAnalyzeIn, db: Session = Depends(get_db)):
    result = await ai_service.analyze_draft(payload.draft_text)
    task = _draft(db, payload.task_id, payload.draft_text)
    # Keep old answers as part of task history; do not delete them on re-analysis.
    for question in result["questions"]:
        existing = db.query(models.ClarifyingQuestion).filter_by(task_id=task.id,
                        field=question["field"], question=question["question"]).first()
        if not existing:
            db.add(models.ClarifyingQuestion(task_id=task.id, ai_used=result["ai_used"], **question))
    db.commit()
    return {**result, "task_id": task.id}


@router.post("/assemble", response_model=schemas.AiAssembleOut)
async def assemble(payload: schemas.AiAssembleIn, db: Session = Depends(get_db)):
    for answer in payload.answers:
        if answer.field not in schemas.RATING_FIELD_KEYS:
            raise HTTPException(422, "Неизвестное поле карточки")
    result = await ai_service.assemble_card(payload.draft_text, [a.model_dump() for a in payload.answers])
    task = _draft(db, payload.task_id, payload.draft_text)
    task.title = result["title"]
    for key, value in result["fields"].items():
        setattr(task, key, value)
    for answer in payload.answers:
        question = db.query(models.ClarifyingQuestion).filter_by(task_id=task.id,
                       field=answer.field, question=answer.question).first()
        if not question:
            question = models.ClarifyingQuestion(task_id=task.id, field=answer.field,
                                                question=answer.question, ai_used=False)
            db.add(question)
        question.answer = answer.answer
        question.answered_at = datetime.utcnow() if answer.answer.strip() else None
    db.commit()
    return {**result, "task_id": task.id}
