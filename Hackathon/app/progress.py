"""
Опыт, монеты и коллекция — отдельный показатель от рейтинга задачи (0-100)
и не влияют ни на каталог, ни на решение бизнеса (раздел 4 UI-концепции).
Начисляются только за фактически подтверждённый прогресс.
"""
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app import models
from app.enums import CollectionPieceType
from app.workflow import selected_teams

STEP_ORDER_TO_PIECE = {
    1: CollectionPieceType.research,
    2: CollectionPieceType.plan,
    3: CollectionPieceType.prototype,
    4: CollectionPieceType.verification,
    5: CollectionPieceType.result,
}

XP_PER_STEP = 20
COINS_PER_STEP = 30
BOSS_BONUS_COINS = 100
BOSS_BONUS_XP = 80


def reward_step_completion(db: Session, task: models.Task, step: models.QuestStep) -> None:
    for team in selected_teams(db, task.id):
        if not _award_once(db, team, task, f"step:{step.id}", COINS_PER_STEP, XP_PER_STEP):
            continue
        piece_type = STEP_ORDER_TO_PIECE.get(step.step_order)
        if piece_type:
            piece = db.query(models.CollectionPiece).filter_by(team_id=team.id, task_id=task.id, type=piece_type).first()
            if not piece:
                piece = models.CollectionPiece(team_id=team.id, task_id=task.id, type=piece_type)
                db.add(piece)
            piece.unlocked = True


def reward_boss_completion(db: Session, task: models.Task) -> None:
    for team in selected_teams(db, task.id):
        _award_once(db, team, task, "boss", BOSS_BONUS_COINS, BOSS_BONUS_XP)


def _award_once(db, team, task, event_key, coins, experience):
    if db.query(models.ProgressReward).filter_by(team_id=team.id, task_id=task.id, event_key=event_key).first():
        return False
    # The unique ledger key also protects two overlapping confirmation requests.
    try:
        with db.begin_nested():
            db.add(models.ProgressReward(team_id=team.id, task_id=task.id, event_key=event_key,
                                         coins=coins, experience=experience))
            db.flush()
    except IntegrityError:
        return False
    db.query(models.Team).filter_by(id=team.id).update({
        models.Team.coins: models.Team.coins + coins,
        models.Team.experience: models.Team.experience + experience,
    }, synchronize_session="fetch")
    return True
