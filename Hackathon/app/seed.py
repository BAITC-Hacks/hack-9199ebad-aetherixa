"""Repeatable fictional examples. Existing user rows are never replaced."""
from datetime import datetime
from sqlalchemy.orm import Session
from app import models
from app.enums import ResponseStatus
from app.rating import apply_rating
from app.workflow import ensure_mission
from app.ui_seed import ensure_task_placements

EXAMPLES = [
    ("Кофейня «Полдень»", "ритейл", "В кофейне длинная очередь, хотим ускорить выдачу заказов.",
     {"context_need": "В часы пик посетители долго ожидают выдачи заказов.",
      "data_sources": "Учебная таблица заказов и времени выдачи.",
      "expected_result": "Прототип экрана очереди заказов.", "success_criteria": "Заказ можно добавить, увидеть и отметить выданным.",
      "constraints": "Демонстрация на тестовых данных без связи с кассой.", "users": "Бариста и посетители.",
      "contact_format": "Обсуждение с представителем бизнеса на демонстрации."}),
    ("Автосервис «Шина+»", "автосервис", "Хотим удобную запись клиентов в автосервис.",
     {"context_need": "Администратор вручную согласует время записи.", "data_sources": "Учебный список свободных слотов.",
      "expected_result": "Форма записи на свободное время.", "users": "Клиенты и администратор."}),
    ("Ответ.Про", "поддержка", "Операторы долго ищут ответы на обращения.",
     {"context_need": "Ответы на типовые вопросы разбросаны по документам.", "users": "Операторы поддержки.",
      "contact_format": "Руководитель поддержки проверит демонстрацию."}),
    ("Школа «Ступени»", "образование", "Нужно удобнее показывать изменения расписания.",
     {"context_need": "Изменения расписания передаются вручную."}),
    ("ГрузПуть", "логистика", "Хотим улучшить работу с доставками, детали уточним.", {}),
]


def seed_if_empty(db: Session) -> None:
    # A version stamp prevents edited/deleted demo records from being recreated.
    if db.get(models.BootstrapState, "hackathon_demo_v2"):
        return
    teams = []
    for index, (name, emoji, skill) in enumerate([
        ("Кактус", "🌵", "Python, SQL"), ("Орбита", "🚀", "JavaScript, UX"),
        ("Искра", "⚡", "Аналитика, дизайн"), ("Маяк", "🔦", "Тестирование, Python"),
        ("Пиксель", "🎨", "HTML, CSS"),
    ]):
        title = f"[Демо] {name}"
        team = db.query(models.Team).filter_by(name=title).first()
        if not team:
            team = models.Team(name=title, avatar_emoji=emoji, coins=0, experience=0,
                               interests="Практические задачи бизнеса", skills=skill, technologies=skill)
            team.members = [models.TeamMember(name=f"Участник {index + 1}", title=None)]
            db.add(team)
            db.flush()
        teams.append(team)
    for index, (name, tag, raw, fields) in enumerate(EXAMPLES):
        draft_name = f"[Демо-черновик] {name}"
        if not db.query(models.Task).filter_by(title=draft_name).first():
            draft = models.Task(title=draft_name, tag=tag, draft_text=raw, status="draft")
            apply_rating(draft)
            db.add(draft)
            db.flush()
            ensure_task_placements(db, draft)
        name = f"[Демо] {name}"
        task = db.query(models.Task).filter_by(title=name).first()
        if not task:
            task = models.Task(title=name, tag=tag, draft_text=raw, status="published",
                               confirmed_at=datetime.utcnow(), published_at=datetime.utcnow(), **fields)
            apply_rating(task)
            db.add(task)
            db.flush()
            ensure_mission(db, task)
            ensure_task_placements(db, task)
        team = teams[index]
        if not db.query(models.TeamResponse).filter_by(task_id=task.id, team_id=team.id).first():
            db.add(models.TeamResponse(task_id=task.id, team_id=team.id, team_name=team.name,
                       idea="Подготовим учебный прототип и согласуем его с заказчиком.",
                       plan="Обсудить задачу, сделать прототип, проверить сценарий и показать результат.",
                       deadline_days=3, prototype_link=f"https://example.com/demo-prototype-{index + 1}",
                       status=ResponseStatus.pending))
    if not db.query(models.ShopItem).first():
        for name, icon, cost, category in [("Робот-помощник", "🤖", 0, "companion"), ("Растения", "🪴", 80, "decor"),
                     ("Флаг и эмблема", "🚩", 120, "decor"), ("Мебель", "🛋️", 60, "decor"),
                     ("Эффект праздника", "✨", 150, "effect"), ("Модель проекта", "🖼️", 100, "decor")]:
            db.add(models.ShopItem(name=name, icon=icon, cost=cost, category=category))
    db.add(models.BootstrapState(key="hackathon_demo_v2"))
    db.commit()
