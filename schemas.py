from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.enums import CollectionPieceType, QuestStepStatus, RatingLevel, ResponseStatus

RATING_FIELD_KEYS = [
    "context_need", "data_sources", "expected_result",
    "success_criteria", "constraints", "users", "contact_format",
]


# ---------- Task ----------

class TaskFields(BaseModel):
    """Семь полей карточки, участвующих в рейтинге. Пустая строка = не заполнено."""
    context_need: str = ""
    data_sources: str = ""
    expected_result: str = ""
    success_criteria: str = ""
    constraints: str = ""
    users: str = ""
    contact_format: str = ""


class TaskCreate(BaseModel):
    title: str
    tag: str = "общее"
    fields: TaskFields = Field(default_factory=TaskFields)


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    tag: Optional[str] = None
    fields: Optional[TaskFields] = None


class RatingBreakdownItem(BaseModel):
    key: str
    label: str
    weight: int
    filled: bool


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    tag: str
    context_need: str
    data_sources: str
    expected_result: str
    success_criteria: str
    constraints: str
    users: str
    contact_format: str
    score: int
    level: RatingLevel
    selected_team_id: Optional[int]
    selected_team_name: Optional[str]
    boss_completed: bool
    created_at: datetime


class TaskRatingOut(BaseModel):
    score: int
    level: RatingLevel
    missing_fields: list[str]
    breakdown: list[RatingBreakdownItem]


# ---------- Responses ----------

class ResponseCreate(BaseModel):
    team_name: str
    idea: str
    plan: str = ""
    prototype_link: str = ""
    team_id: Optional[int] = None


class ResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    team_id: Optional[int]
    team_name: str
    idea: str
    plan: str
    prototype_link: str
    status: ResponseStatus
    created_at: datetime


# ---------- Quests ----------

class QuestStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    step_order: int
    title: str
    status: QuestStepStatus
    hint_level: int
    path_choice: Optional[str]


class PathChoiceIn(BaseModel):
    choice: str


# ---------- Boss ----------

class BossCriterionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    order_index: int
    text: str
    confirmed: bool


class BossStatusOut(BaseModel):
    criteria: list[BossCriterionOut]
    confirmed_count: int
    total: int
    completed: bool


# ---------- Team / Workshop ----------

class TeamMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    title: Optional[str]


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    avatar_emoji: str
    coins: int
    experience: int
    members: list[TeamMemberOut] = []


class TeamCreate(BaseModel):
    name: str
    avatar_emoji: str = "🚀"


class ShopItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    icon: str
    cost: int
    category: str


class OwnedShopItemOut(BaseModel):
    item: ShopItemOut
    owned: bool
    equipped: bool


class CollectionPieceOut(BaseModel):
    type: CollectionPieceType
    unlocked: bool


# ---------- AI ----------

class AiAnalyzeIn(BaseModel):
    draft_text: str


class AiQuestion(BaseModel):
    field: str
    question: str


class AiAnalyzeOut(BaseModel):
    ai_used: bool
    covered_fields: list[str]
    missing_fields: list[str]
    questions: list[AiQuestion]


class AiAnswer(BaseModel):
    field: str
    question: str
    answer: str


class AiAssembleIn(BaseModel):
    draft_text: str
    answers: list[AiAnswer]


class AiAssembleOut(BaseModel):
    ai_used: bool
    title: str
    fields: TaskFields
