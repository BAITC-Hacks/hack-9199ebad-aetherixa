"""Persistent UI placement models.

Import this module before Base.metadata.create_all() so these tables are
registered alongside the existing models.
"""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Numeric, Unicode as String, UnicodeText as Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class UIPlacementMode(Base):
    __tablename__ = "ui_placement_modes"

    id = Column(Integer, primary_key=True)
    code = Column(String(40), unique=True, nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    placements = relationship("TaskUIPlacement", back_populates="mode")


class TaskUIPlacement(Base):
    __tablename__ = "task_ui_placements"
    __table_args__ = (UniqueConstraint("task_id", "mode_id", name="uq_task_ui_mode"),)

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    mode_id = Column(Integer, ForeignKey("ui_placement_modes.id"), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    x = Column(Numeric(10, 2), nullable=True)
    y = Column(Numeric(10, 2), nullable=True)
    width = Column(Numeric(10, 2), nullable=True)
    height = Column(Numeric(10, 2), nullable=True)
    visual_asset_key = Column(String(200), nullable=True)
    visual_config_json = Column(Text, nullable=True)
    is_visible = Column(Boolean, nullable=False, default=True)

    task = relationship("Task")
    mode = relationship("UIPlacementMode", back_populates="placements")
