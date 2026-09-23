"""Shared task publication and game initialization rules."""
from app import models
from app.enums import QuestStepStatus, ResponseStatus
from app.rating import apply_rating


def invalidate_confirmation(task):
    task.status = "draft"
    task.confirmed_at = None
    task.published_at = None
    apply_rating(task)


def selected_teams(db, task_id):
    return (db.query(models.Team).join(models.TeamResponse, models.TeamResponse.team_id == models.Team.id)
            .filter(models.TeamResponse.task_id == task_id, models.TeamResponse.status == ResponseStatus.selected)
            .distinct().all())


def ensure_mission(db, task):
    if not db.query(models.QuestStep).filter_by(task_id=task.id).first():
        names = ["Исследуйте потребность пользователей", "Согласуйте план и сценарий", "Создайте прототип",
                 "Проверьте решение на примерах", "Передайте результат бизнесу"]
        for order, title in enumerate(names, 1):
            db.add(models.QuestStep(task_id=task.id, step_order=order, title=title,
                                   status=QuestStepStatus.current if order == 1 else QuestStepStatus.locked))
    if not db.query(models.BossCriterion).filter_by(task_id=task.id).first():
        checks = [task.success_criteria or "Бизнес проверил результат по согласованному сценарию",
                  "Результат продемонстрирован бизнесу", "Материалы переданы команде заказчика"]
        for index, content in enumerate(checks):
            db.add(models.BossCriterion(task_id=task.id, order_index=index, text=content, confirmed=False))
