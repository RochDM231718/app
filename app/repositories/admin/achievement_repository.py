from sqlalchemy.orm import Session
from app.repositories.admin.crud_repository import CrudRepository
from app.models.achievement import Achievement


class AchievementRepository(CrudRepository):
    def __init__(self, db: Session):
        super().__init__(db, Achievement)

    def get_by_user(self, user_id: int, page: int = 1):
        query = self.db.query(self.model).filter(self.model.user_id == user_id)
        query = query.order_by(self.model.created_at.desc())
        return self.paginate(query, {'page': page}).all()