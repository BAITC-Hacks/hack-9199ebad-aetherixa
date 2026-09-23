"""
Опыт, монеты и коллекция — отдельный показатель от рейтинга задачи (0-100)
и не влияют ни на каталог, ни на решение бизнеса (раздел 4 UI-концепции).
Начисляются только за фактически подтверждённый прогресс.
"""
from sqlalchemy.orm import Session

from app import models
from app.enums import CollectionPieceType

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
    if not task.selected_team_id:
        return  # награда положена только команде, выбранной бизнесом
    team = db.get(models.Team, task.selected_team_id)
    if not team:
        return
    team.experience += XP_PER_STEP
    team.coins += COINS_PER_STEP

    piece_type = STEP_ORDER_TO_PIECE.get(step.step_order)
    if piece_type:
        piece = (
            db.query(models.CollectionPiece)
            .filter_by(team_id=team.id, task_id=task.id, type=piece_type)
            .first()
        )
        if not piece:
            piece = models.CollectionPiece(team_id=team.id, task_id=task.id, type=piece_type)
            db.add(piece)
        piece.unlocked = True


def reward_boss_completion(db: Session, task: models.Task) -> None:
    if not task.selected_team_id:
        return
    team = db.get(models.Team, task.selected_team_id)
    if not team:
        return
    team.experience += BOSS_BONUS_XP
    team.coins += BOSS_BONUS_COINS
