from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(tags=["shop"])


@router.get("/api/shop-items", response_model=list[schemas.ShopItemOut])
def list_shop_items(db: Session = Depends(get_db)):
    return db.query(models.ShopItem).all()


@router.get("/api/teams/{team_id}/shop-items", response_model=list[schemas.OwnedShopItemOut])
def list_team_shop_items(team_id: int, db: Session = Depends(get_db)):
    """Весь каталог магазина + отметка, что команда уже открыла и что сейчас надето."""
    items = db.query(models.ShopItem).all()
    owned = {
        tsi.shop_item_id: tsi
        for tsi in db.query(models.TeamShopItem).filter_by(team_id=team_id).all()
    }
    return [
        schemas.OwnedShopItemOut(
            item=item,
            owned=item.id in owned,
            equipped=owned[item.id].equipped if item.id in owned else False,
        )
        for item in items
    ]


@router.post("/api/teams/{team_id}/shop-items/{item_id}/purchase", response_model=schemas.OwnedShopItemOut)
def purchase_item(team_id: int, item_id: int, db: Session = Depends(get_db)):
    team = db.get(models.Team, team_id)
    item = db.get(models.ShopItem, item_id)
    if not team or not item:
        raise HTTPException(404, "Команда или предмет не найдены")
    already = db.query(models.TeamShopItem).filter_by(team_id=team_id, shop_item_id=item_id).first()
    if already:
        raise HTTPException(400, "Предмет уже открыт")
    if team.coins < item.cost:
        raise HTTPException(400, "Недостаточно монет")
    team.coins -= item.cost
    tsi = models.TeamShopItem(team_id=team_id, shop_item_id=item_id, equipped=False)
    db.add(tsi)
    db.commit()
    return schemas.OwnedShopItemOut(item=item, owned=True, equipped=False)


@router.post("/api/teams/{team_id}/shop-items/{item_id}/equip", response_model=schemas.OwnedShopItemOut)
def equip_item(team_id: int, item_id: int, db: Session = Depends(get_db)):
    tsi = db.query(models.TeamShopItem).filter_by(team_id=team_id, shop_item_id=item_id).first()
    if not tsi:
        raise HTTPException(400, "Сначала откройте предмет за монеты")
    # снимаем остальные предметы той же категории, чтобы был надет только один
    same_category = (
        db.query(models.TeamShopItem)
        .join(models.ShopItem)
        .filter(models.TeamShopItem.team_id == team_id, models.ShopItem.category == tsi.shop_item.category)
        .all()
    )
    for other in same_category:
        other.equipped = False
    tsi.equipped = True
    db.commit()
    return schemas.OwnedShopItemOut(item=tsi.shop_item, owned=True, equipped=True)
