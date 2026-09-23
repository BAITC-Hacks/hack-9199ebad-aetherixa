from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.post("", response_model=schemas.TeamOut, status_code=201)
def create_team(payload: schemas.TeamCreate, db: Session = Depends(get_db)):
    if not payload.name.strip():
        raise HTTPException(422, "Название команды не может быть пустым")
    team = models.Team(**payload.model_dump(exclude={"members"}))
    team.members = [models.TeamMember(**member.model_dump()) for member in payload.members]
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.get("", response_model=list[schemas.TeamOut])
def list_teams(db: Session = Depends(get_db)):
    return db.query(models.Team).all()


@router.get("/{team_id}", response_model=schemas.TeamOut)
def get_team(team_id: int, db: Session = Depends(get_db)):
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(404, "Команда не найдена")
    return team


@router.get("/{team_id}/collection/{task_id}", response_model=list[schemas.CollectionPieceOut])
def get_collection(team_id: int, task_id: int, db: Session = Depends(get_db)):
    """Коллекция из пяти частей по конкретному проекту — статус найденных/скрытых частей."""
    from app.enums import CollectionPieceType

    existing = {
        p.type: p.unlocked
        for p in db.query(models.CollectionPiece).filter_by(team_id=team_id, task_id=task_id).all()
    }
    return [
        schemas.CollectionPieceOut(type=t, unlocked=existing.get(t, False))
        for t in CollectionPieceType
    ]
