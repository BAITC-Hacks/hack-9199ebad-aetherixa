from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.enums import QuestStepStatus
from app.progress import reward_step_completion
from app.workflow import selected_teams

router = APIRouter(prefix="/api/tasks/{task_id}/quests", tags=["quests"])

# Три уровня подсказки, как в UI-концепции: наводящий вопрос → пример → разбор.
# Использование подсказок не уменьшает награду (раздел 8 концепции).
HINT_TEXTS = models.QUEST_HINTS


def _get_step(db: Session, task_id: int, step_id: int) -> models.QuestStep:
    step = db.get(models.QuestStep, step_id)
    if not step or step.task_id != task_id:
        raise HTTPException(404, "Шаг миссии не найден")
    return step


@router.get("", response_model=list[schemas.QuestStepOut])
def list_quest_steps(task_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.QuestStep)
        .filter(models.QuestStep.task_id == task_id)
        .order_by(models.QuestStep.step_order)
        .all()
    )


@router.post("/{step_id}/submit", response_model=schemas.QuestStepOut)
def submit_step(task_id: int, step_id: int, payload: schemas.QuestSubmitIn, db: Session = Depends(get_db)):
    """Команда отправляет результат по текущему шагу — статус переходит в «На проверке»."""
    step = _get_step(db, task_id, step_id)
    if not selected_teams(db, task_id):
        raise HTTPException(409, "Бизнес ещё не выбрал команду")
    if not payload.submission_text.strip():
        raise HTTPException(422, "Добавьте описание результата или ссылку")
    if step.status != QuestStepStatus.current:
        raise HTTPException(400, "Отправить на проверку можно только текущий активный шаг")
    step.status = QuestStepStatus.review
    step.submission_text = payload.submission_text
    db.commit()
    db.refresh(step)
    return step


@router.post("/{step_id}/confirm", response_model=schemas.QuestStepOut)
def confirm_step(task_id: int, step_id: int, db: Session = Depends(get_db)):
    """Бизнес подтверждает шаг: опыт начисляется только после этого подтверждения."""
    step = _get_step(db, task_id, step_id)
    if step.status == QuestStepStatus.done:
        return step
    if not selected_teams(db, task_id):
        raise HTTPException(409, "Бизнес ещё не выбрал команду")
    if step.status != QuestStepStatus.review:
        raise HTTPException(400, "Подтвердить можно только шаг, отправленный на проверку")
    step.status = QuestStepStatus.done

    task = db.get(models.Task, task_id)
    reward_step_completion(db, task, step)

    next_step = (
        db.query(models.QuestStep)
        .filter(models.QuestStep.task_id == task_id, models.QuestStep.step_order == step.step_order + 1)
        .first()
    )
    if next_step and next_step.status == QuestStepStatus.locked:
        next_step.status = QuestStepStatus.current

    db.commit()
    db.refresh(step)
    return step


@router.post("/{step_id}/hint")
def next_hint(task_id: int, step_id: int, db: Session = Depends(get_db)):
    """Возвращает следующий уровень подсказки. Максимум 3 уровня."""
    step = _get_step(db, task_id, step_id)
    if step.hint_level >= len(HINT_TEXTS):
        return {"hint": None, "hint_level": step.hint_level, "exhausted": True}
    hint_text = HINT_TEXTS[step.hint_level]
    step.hint_level += 1
    db.commit()
    return {"hint": hint_text, "hint_level": step.hint_level, "exhausted": step.hint_level >= len(HINT_TEXTS)}


@router.patch("/{step_id}/path-choice", response_model=schemas.QuestStepOut)
def set_path_choice(task_id: int, step_id: int, payload: schemas.PathChoiceIn, db: Session = Depends(get_db)):
    """Команда заранее выбирает способ прохождения этапа (равноценные пути, раздел 4 концепции)."""
    step = _get_step(db, task_id, step_id)
    step.path_choice = payload.choice
    db.commit()
    db.refresh(step)
    return step
