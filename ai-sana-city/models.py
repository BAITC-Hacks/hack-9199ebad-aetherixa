from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Building:
    name: str
    quest: str
    percent: int
    icon: str
    col: int
    row: int
    featured: bool = False
    view: str | None = None


@dataclass(frozen=True)
class MissionStep:
    id: str
    title: str
    state: str
    status: str | None = None
    supports_hints: bool = False
    choice_options: tuple[str, ...] = ()


@dataclass(frozen=True)
class Mission:
    id: str
    business: str
    title: str
    description: str
    flavor: str
    formal_description: str
    readiness: int
    steps: tuple[MissionStep, ...]
    hints: tuple[str, ...]
    mentor_name: str
    mentor_role: str
    mentor_message: str
    boss_name: str
    celebration: str


@dataclass(frozen=True)
class ShopItem:
    id: str
    name: str
    icon: str
    cost: int | None = None
    locked: bool = False
    equipped: bool = False


@dataclass(frozen=True)
class CollectionPiece:
    id: str
    name: str
    icon: str
    state: str


@dataclass(frozen=True)
class Criterion:
    id: str
    text: str
    confirmed: bool


BUILDINGS: tuple[Building, ...] = (
    Building("Кофейня «Полдень»", "Очередь без хаоса", 100, "☕", 0, 1),
    Building("Автосервис «Шина+»", "Запись без путаницы", 65, "🔧", 1, 0),
    Building("Ответ.Про", "Спасите службу поддержки", 40, "💬", 2, 1, True, "missions"),
    Building("Школа «Ступени»", "Расписание без сбоев", 20, "🏫", 1, 2),
    Building("ГрузПуть", "Маршруты без сюрпризов", 0, "🚚", 3, 1),
)

MISSION = Mission(
    id="support-rescue",
    business="Ответ.Про",
    title="Спасите службу поддержки",
    description="Помогите сотрудникам быстрее находить ответы клиентам.",
    flavor="Пройдите пять шагов, чтобы «Хаос в заявках» отступил, а здание Ответ.Про открылось в городе.",
    formal_description=(
        "Автоматизация обработки обращений: сократить время поиска релевантного ответа "
        "оператором и снизить долю повторных обращений по одному и тому же вопросу."
    ),
    readiness=40,
    steps=(
        MissionStep("audience", "Выясните, кто будет пользоваться решением", "done"),
        MissionStep("scenario", "Согласуйте один основной сценарий", "done"),
        MissionStep("first-screen", "Покажите первый работающий экран", "current", "На проверке", True),
        MissionStep(
            "test-three",
            "Проверьте прототип на трёх примерах",
            "locked",
            "Откроется после проверки",
            choice_options=("Интервью", "Интерактивный макет", "Технический эксперимент"),
        ),
        MissionStep("business-demo", "Продемонстрируйте результат бизнесу", "locked", "Откроется после проверки"),
    ),
    hints=(
        "Наводящий вопрос: что видит пользователь в первую секунду после открытия экрана?",
        "Пример: посмотрите, как похожая форма подтверждения сделана в другом сервисе поддержки.",
        "Разбор: разложите экран на три части — ввод, статус, следующий шаг — и постройте их по очереди.",
    ),
    mentor_name="Наставник Аи",
    mentor_role="Замечает прогресс, а не оценивает",
    mentor_message="Прототип уже принимает заявки. Следующий квест — показать, что произойдёт, если пользователь оставит поле пустым.",
    boss_name="Хаос в заявках",
    celebration="🎉 Хаос в заявках повержен! Здание Ответ.Про открыто, а мастерская получает нового робота-помощника.",
)

MISSIONS: dict[str, Mission] = {MISSION.id: MISSION}

SHOP_ITEMS: tuple[ShopItem, ...] = (
    ShopItem("robot", "Робот-помощник", "🤖", equipped=True),
    ShopItem("plants", "Растения", "🪴", 80),
    ShopItem("flag", "Флаг и эмблема", "🚩", 120, locked=True),
    ShopItem("furniture", "Мебель", "🛋️", 60),
    ShopItem("celebration", "Эффект праздника", "✨", 150, locked=True),
    ShopItem("project-model", "Модель проекта", "🖼️", 100, locked=True),
)

COLLECTION: tuple[CollectionPiece, ...] = (
    CollectionPiece("research", "Исследование", "🔎", "got"),
    CollectionPiece("plan", "План", "🗺️", "got"),
    CollectionPiece("prototype", "Прототип", "🧩", "got"),
    CollectionPiece("testing", "Проверка", "🔒", "locked"),
    CollectionPiece("result", "Результат", "🔒", "locked"),
)

CRITERIA: tuple[Criterion, ...] = (
    Criterion("request-saved", "Заявка сохраняется", True),
    Criterion("category-detected", "Категория определяется", True),
    Criterion("result-editable", "Сотрудник может исправить результат", False),
)

HINT_LABELS = ("Показать подсказку", "Показать пример", "Показать разбор", "Подсказки закончились")


def serialize(value: Any) -> Any:
    """Convert a dataclass (including nested dataclasses) to JSON-ready data."""
    return asdict(value)

