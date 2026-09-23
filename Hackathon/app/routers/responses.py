from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.enums import ResponseStatus
from app.workflow import selected_teams, ensure_mission

router = APIRouter(tags=["responses"])


@router.post("/api/tasks/{task_id}/responses", response_model=schemas.ResponseOut, status_code=201)
def create_response(task_id: int, payload: schemas.ResponseCreate, db: Session = Depends(get_db)):
    """Любая команда может отправить предложение — число откликов не ограничено."""
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(404, "Задача не найдена")
    if task.status != "published":
        raise HTTPException(409, "Сначала бизнес должен подтвердить и опубликовать карточку")
    team = db.get(models.Team, payload.team_id)
    if not team:
        raise HTTPException(404, "Команда не найдена")
    if not payload.idea.strip():
        raise HTTPException(422, "Опишите идею решения")
    resp = models.TeamResponse(
        task_id=task_id,
        team_id=payload.team_id,
        team_name=team.name,
        idea=payload.idea,
        plan=payload.plan,
        prototype_link=payload.prototype_link,
        deadline_days=payload.deadline_days,
        status=ResponseStatus.pending,
    )
    db.add(resp)
    db.commit()
    db.refresh(resp)
    return resp


@router.get("/api/tasks/{task_id}/responses", response_model=list[schemas.ResponseOut])
def list_responses(task_id: int, db: Session = Depends(get_db)):
    return db.query(models.TeamResponse).filter(models.TeamResponse.task_id == task_id).all()


@router.patch("/api/responses/{response_id}/select", response_model=schemas.ResponseOut)
def select_response(response_id: int, db: Session = Depends(get_db)):
    """Бизнес выбирает команду вручную. Автоматическое назначение запрещено регламентом."""
    resp = db.get(models.TeamResponse, response_id)
    if not resp:
        raise HTTPException(404, "Отклик не найден")
    resp.status = ResponseStatus.selected
    task = db.get(models.Task, resp.task_id)
    if task.status != "published":
        raise HTTPException(409, "Сначала опубликуйте карточку задачи")
    task.selected_team_id = resp.team_id
    task.selected_team_name = resp.team_name
    ensure_mission(db, task)
    db.commit()
    db.refresh(resp)
    return resp


@router.patch("/api/responses/{response_id}/reject", response_model=schemas.ResponseOut)
def reject_response(response_id: int, db: Session = Depends(get_db)):
    resp = db.get(models.TeamResponse, response_id)
    if not resp:
        raise HTTPException(404, "Отклик не найден")
    resp.status = ResponseStatus.rejected
    db.flush()
    task = db.get(models.Task, resp.task_id)
    remaining = selected_teams(db, task.id)
    task.selected_team_id = remaining[0].id if remaining else None
    task.selected_team_name = remaining[0].name if remaining else None
    db.commit()
    db.refresh(resp)
    return resp
