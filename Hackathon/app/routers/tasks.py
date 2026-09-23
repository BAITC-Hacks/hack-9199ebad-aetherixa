from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.rating import apply_rating, compute_rating
from app.workflow import ensure_mission, invalidate_confirmation, selected_teams
from app.ui_seed import ensure_task_placements

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _task(db, task_id):
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(404, "Задача не найдена")
    return task


def _apply_fields(task, fields):
    for key, value in fields.model_dump().items():
        setattr(task, key, value)


@router.post("", response_model=schemas.TaskOut, status_code=201)
def create_task(payload: schemas.TaskCreate, db: Session = Depends(get_db)):
    task = models.Task(title=payload.title.strip(), tag=payload.tag.strip(), draft_text=payload.draft_text)
    if not task.title or not task.tag:
        raise HTTPException(422, "Название и категория не могут быть пустыми")
    _apply_fields(task, payload.fields)
    invalidate_confirmation(task)
    db.add(task)
    db.flush()
    ensure_task_placements(db, task)
    db.commit()
    db.refresh(task)
    return task


@router.get("", response_model=list[schemas.TaskOut])
def list_tasks(tag: str | None = None, level: str | None = None,
               status: Literal["published", "draft", "all"] = "published",
               sort: str = Query("rating", pattern="^(rating|new)$"), db: Session = Depends(get_db)):
    query = db.query(models.Task)
    if status != "all":
        query = query.filter(models.Task.status == status)
    if tag:
        query = query.filter(models.Task.tag == tag)
    if level:
        query = query.filter(models.Task.level == level)
    return query.order_by(models.Task.created_at.desc() if sort == "new" else models.Task.score.desc(), models.Task.id.desc()).all()


@router.get("/{task_id}", response_model=schemas.TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    return _task(db, task_id)


@router.patch("/{task_id}", response_model=schemas.TaskOut)
def update_task(task_id: int, payload: schemas.TaskUpdate, db: Session = Depends(get_db)):
    task = _task(db, task_id)
    for key in ("title", "tag", "draft_text"):
        value = getattr(payload, key)
        if value is not None:
            if key != "draft_text" and not value.strip():
                raise HTTPException(422, "Название и категория не могут быть пустыми")
            setattr(task, key, value)
    if payload.fields is not None:
        for key, value in payload.fields.model_dump(exclude_unset=True).items():
            setattr(task, key, value)
    invalidate_confirmation(task)
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/publish", response_model=schemas.TaskOut)
def publish_task(task_id: int, payload: schemas.PublishIn, db: Session = Depends(get_db)):
    task = _task(db, task_id)
    task.confirmed_at = datetime.utcnow()
    task.published_at = task.published_at or datetime.utcnow()
    task.status = "published"
    apply_rating(task)
    ensure_mission(db, task)
    ensure_task_placements(db, task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}/rating", response_model=schemas.TaskRatingOut)
def get_task_rating(task_id: int, db: Session = Depends(get_db)):
    return compute_rating(_task(db, task_id))


@router.get("/{task_id}/questions")
def get_questions(task_id: int, db: Session = Depends(get_db)):
    _task(db, task_id)
    return [{"id": q.id, "field": q.field, "question": q.question, "answer": q.answer,
             "ai_used": q.ai_used, "answered_at": q.answered_at}
            for q in db.query(models.ClarifyingQuestion).filter_by(task_id=task_id).order_by(models.ClarifyingQuestion.id)]


@router.get("/{task_id}/selected-teams", response_model=list[schemas.TeamOut])
def get_selected_teams(task_id: int, db: Session = Depends(get_db)):
    _task(db, task_id)
    return selected_teams(db, task_id)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = _task(db, task_id)
    from app.ui_models import TaskUIPlacement
    for cls in (TaskUIPlacement, models.CollectionPiece, models.ProgressReward):
        db.query(cls).filter_by(task_id=task_id).delete(synchronize_session=False)
    db.delete(task)
    db.commit()
