"""
Сид совпадает с примерами из UI-концепции: те же 5 «зданий», те же проценты
готовности, тот же маршрут миссии и магазин мастерской — чтобы бэкенд сразу
показывал ровно то, что нарисовано в макете.
"""
from sqlalchemy.orm import Session

from app import models
from app.enums import QuestStepStatus
from app.rating import apply_rating


def seed_if_empty(db: Session) -> None:
    if db.query(models.Task).count() > 0:
        return  # уже наполнено — не дублируем при перезапуске

    # ---------- Команда ----------
    team = models.Team(name="Команда «Кактус»", avatar_emoji="🌵", coins=240, experience=180)
    team.members = [
        models.TeamMember(name="Алина", title="Исследователь"),
        models.TeamMember(name="Данияр", title="Создатель прототипа"),
        models.TeamMember(name="Малика", title="Мастер проверки"),
    ]
    db.add(team)
    db.flush()

    # ---------- Задачи (проценты совпадают с макетом города) ----------
    def make_task(title, tag, fields, selected=False):
        t = models.Task(title=title, tag=tag, **fields)
        apply_rating(t)
        if selected:
            t.selected_team_id = team.id
            t.selected_team_name = team.name
        db.add(t)
        db.flush()
        return t

    make_task("Кофейня «Полдень»", "ритейл", {
        "context_need": "Очередь в кофейне растягивается в часы пик, гости уходят не дождавшись.",
        "data_sources": "Данные кассы за 3 месяца, тайминги заказов.",
        "expected_result": "Работающий экран приёма заказов с очередью на самообслуживании.",
        "success_criteria": "Среднее время ожидания сокращается вдвое.",
        "constraints": "Готово за 5 часов, без интеграции с кассовым ПО.",
        "users": "Бариста и гости кофейни.",
        "contact_format": "Созвон по итогам, контакт владельца в Telegram.",
    })

    make_task("Автосервис «Шина+»", "автосервис", {
        "context_need": "Клиенты записываются по телефону, часто путаются слоты записи.",
        "data_sources": "Экспорт записей за месяц в CSV.",
        "expected_result": "Онлайн-форма записи с подтверждением слота.",
        "success_criteria": "",
        "constraints": "",
        "users": "Администратор автосервиса и клиенты.",
        "contact_format": "",
    })

    resp_pro = make_task("Ответ.Про", "поддержка клиентов", {
        "context_need": "Операторы поддержки долго ищут релевантный ответ клиенту вручную.",
        "data_sources": "",
        "expected_result": "",
        "success_criteria": "",
        "constraints": "",
        "users": "Операторы службы поддержки.",
        "contact_format": "Контакт руководителя поддержки, еженедельный созвон.",
    }, selected=True)

    make_task("Школа «Ступени»", "образование", {
        "context_need": "Расписание меняется вручную и часто рассинхронизировано между классами.",
        "data_sources": "", "expected_result": "", "success_criteria": "",
        "constraints": "", "users": "", "contact_format": "",
    })

    make_task("ГрузПуть", "логистика", {
        "context_need": "", "data_sources": "", "expected_result": "", "success_criteria": "",
        "constraints": "", "users": "", "contact_format": "",
    })

    # ---------- Маршрут миссии для «Ответ.Про» (как в макете: 2 done, 1 review, 2 locked) ----------
    steps = [
        (1, "Выясните, кто будет пользоваться решением", QuestStepStatus.done),
        (2, "Согласуйте один основной сценарий", QuestStepStatus.done),
        (3, "Покажите первый работающий экран", QuestStepStatus.review),
        (4, "Проверьте прототип на трёх примерах", QuestStepStatus.locked),
        (5, "Продемонстрируйте результат бизнесу", QuestStepStatus.locked),
    ]
    for order, title, status in steps:
        db.add(models.QuestStep(task_id=resp_pro.id, step_order=order, title=title, status=status))

    # разблокированные части коллекции за первые два подтверждённых шага
    from app.enums import CollectionPieceType
    for piece_type in (CollectionPieceType.research, CollectionPieceType.plan, CollectionPieceType.prototype):
        db.add(models.CollectionPiece(team_id=team.id, task_id=resp_pro.id, type=piece_type, unlocked=True))

    # ---------- Критерии финальной проверки (как в макете: 2 из 3 подтверждены) ----------
    criteria = [
        (0, "Заявка сохраняется", True),
        (1, "Категория определяется", True),
        (2, "Сотрудник может исправить результат", False),
    ]
    for idx, text, confirmed in criteria:
        db.add(models.BossCriterion(task_id=resp_pro.id, order_index=idx, text=text, confirmed=confirmed))

    # ---------- Магазин мастерской ----------
    shop_items = [
        ("Робот-помощник", "🤖", 0, "companion"),
        ("Растения", "🪴", 80, "decor"),
        ("Флаг и эмблема", "🚩", 120, "decor"),
        ("Мебель", "🛋️", 60, "decor"),
        ("Эффект праздника", "✨", 150, "effect"),
        ("Модель проекта", "🖼️", 100, "decor"),
    ]
    for name, icon, cost, category in shop_items:
        item = models.ShopItem(name=name, icon=icon, cost=cost, category=category)
        db.add(item)
        db.flush()
        if name == "Робот-помощник":  # уже открыт и надет по умолчанию, как в макете
            db.add(models.TeamShopItem(team_id=team.id, shop_item_id=item.id, equipped=True))

    db.commit()
