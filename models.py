"""
ORM-модели. Семь текстовых полей Task — это ровно те поля, что участвуют
в формуле рейтинга (см. app/rating.py); вес каждого поля закреплён
в одном месте, чтобы формула оставалась прозрачной и легко проверяемой.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.enums import CollectionPieceType, QuestStepStatus, RatingLevel, ResponseStatus


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    tag = Column(String, nullable=False, index=True)

    context_need = Column(Text, default="")       # Контекст и потребность — 20
    data_sources = Column(Text, default="")        # Данные и материалы — 20
    expected_result = Column(Text, default="")     # Ожидаемый результат — 15
    success_criteria = Column(Text, default="")    # Критерии успеха — 15
    constraints = Column(Text, default="")         # Ограничения — 10
    users = Column(Text, default="")               # Пользователи — 10
    contact_format = Column(Text, default="")      # Связь с бизнесом — 10

    score = Column(Integer, nullable=False, default=0)
    level = Column(Enum(RatingLevel), nullable=False, default=RatingLevel.draft)

    selected_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    selected_team_name = Column(String, nullable=True)
    boss_completed = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    responses = relationship("TeamResponse", back_populates="task", cascade="all, delete-orphan")
    quest_steps = relationship("QuestStep", back_populates="task", cascade="all, delete-orphan",
                                order_by="QuestStep.step_order")
    boss_criteria = relationship("BossCriterion", back_populates="task", cascade="all, delete-orphan",
                                  order_by="BossCriterion.order_index")


class TeamResponse(Base):
    __tablename__ = "team_responses"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)  # необязательная привязка

    team_name = Column(String, nullable=False)
    idea = Column(Text, nullable=False)
    plan = Column(Text, default="")
    prototype_link = Column(String, default="")

    status = Column(Enum(ResponseStatus), nullable=False, default=ResponseStatus.pending)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="responses")


class QuestStep(Base):
    __tablename__ = "quest_steps"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)

    step_order = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    status = Column(Enum(QuestStepStatus), nullable=False, default=QuestStepStatus.locked)
    hint_level = Column(Integer, nullable=False, default=0)
    path_choice = Column(String, nullable=True)

    task = relationship("Task", back_populates="quest_steps")


class BossCriterion(Base):
    __tablename__ = "boss_criteria"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)

    order_index = Column(Integer, nullable=False)
    text = Column(String, nullable=False)
    confirmed = Column(Boolean, nullable=False, default=False)

    task = relationship("Task", back_populates="boss_criteria")


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    avatar_emoji = Column(String, default="🚀")
    coins = Column(Integer, nullable=False, default=0)
    experience = Column(Integer, nullable=False, default=0)

    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    shop_items = relationship("TeamShopItem", back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    name = Column(String, nullable=False)
    title = Column(String, nullable=True)  # титул за подтверждённый вклад

    team = relationship("Team", back_populates="members")


class ShopItem(Base):
    __tablename__ = "shop_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    icon = Column(String, default="🎁")
    cost = Column(Integer, nullable=False)
    category = Column(String, default="decor")


class TeamShopItem(Base):
    __tablename__ = "team_shop_items"
    __table_args__ = (UniqueConstraint("team_id", "shop_item_id", name="uq_team_shop_item"),)

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    shop_item_id = Column(Integer, ForeignKey("shop_items.id"), nullable=False)
    equipped = Column(Boolean, nullable=False, default=False)

    team = relationship("Team", back_populates="shop_items")
    shop_item = relationship("ShopItem")


class CollectionPiece(Base):
    __tablename__ = "collection_pieces"
    __table_args__ = (UniqueConstraint("team_id", "task_id", "type", name="uq_collection_piece"),)

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    type = Column(Enum(CollectionPieceType), nullable=False)
    unlocked = Column(Boolean, nullable=False, default=False)
