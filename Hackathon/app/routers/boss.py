from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.progress import reward_boss_completion
from app.workflow import selected_teams
from app.enums import QuestStepStatus

router = APIRouter(prefix="/api/tasks/{task_id}/boss-criteria", tags=["boss"])


def _status(db: Session, task_id: int) -> schemas.BossStatusOut:
    criteria = (
        db.query(models.BossCriterion)
        .filter(models.BossCriterion.task_id == task_id)
        .order_by(models.BossCriterion.order_index)
        .all()
    )
    confirmed = sum(1 for c in criteria if c.confirmed)
    return schemas.BossStatusOut(
        criteria=criteria, confirmed_count=confirmed, total=len(criteria),
        completed=len(criteria) > 0 and confirmed == len(criteria),
    )


@router.get("", response_model=schemas.BossStatusOut)
def get_boss_status(task_id: int, db: Session = Depends(get_db)):
    return _status(db, task_id)


@router.patch("/{criterion_id}/toggle", response_model=schemas.BossStatusOut)
def toggle_criterion(task_id: int, criterion_id: int, db: Session = Depends(get_db)):
    """Каждая подтверждённая проверка ослабляет проблему. Когда все критерии
    подтверждены — задача считается закрытой, здание открывается, команда получает бонус."""
    criterion = db.get(models.BossCriterion, criterion_id)
    if not criterion or criterion.task_id != task_id:
        raise HTTPException(404, "Критерий не найден")
    if not selected_teams(db, task_id):
        raise HTTPException(409, "Бизнес ещё не выбрал команду")
    if db.query(models.QuestStep).filter(models.QuestStep.task_id == task_id,
                                        models.QuestStep.status != QuestStepStatus.done).first():
        raise HTTPException(409, "Сначала подтвердите все этапы миссии")
    criterion.confirmed = not criterion.confirmed
    db.flush()

    result = _status(db, task_id)
    task = db.get(models.Task, task_id)
    was_completed = task.boss_completed
    task.boss_completed = result.completed
    if result.completed and not was_completed:
        reward_boss_completion(db, task)
    db.commit()
    return result
