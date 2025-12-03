from app.models.user import Users
from app.repositories.admin.crud_repository import CrudRepository
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc  # <-- Добавили импорты
from app.schemas.admin.users import UserCreate


class UserRepository(CrudRepository):
    def __init__(self, db: Session):
        super().__init__(db, Users)

    # Обновленный метод с сортировкой
    def get(self, filters: dict = None, sort_by: str = 'id', sort_order: str = 'desc'):
        users = self.db.query(self.model)

        if filters is not None:
            if 'query' in filters and filters['query'] != '':
                like_term = f"%{filters['query']}%"
                users = users.filter(
                    or_(
                        self.model.first_name.ilike(like_term),
                        self.model.last_name.ilike(like_term),
                        self.model.email.ilike(like_term),
                        self.model.phone_number.ilike(like_term),
                    )
                )

            if 'role' in filters and filters['role']:
                users = users.filter(self.model.role == filters['role'])

            if 'status' in filters and filters['status']:
                users = users.filter(self.model.status == filters['status'])

        # --- ЛОГИКА СОРТИРОВКИ ---
        # Проверяем, есть ли такое поле в модели, чтобы избежать ошибок
        if hasattr(self.model, sort_by):
            sort_attr = getattr(self.model, sort_by)
            if sort_order == 'asc':
                users = users.order_by(asc(sort_attr))
            else:
                users = users.order_by(desc(sort_attr))
        else:
            # Сортировка по умолчанию
            users = users.order_by(desc(self.model.id))
        # -------------------------

        users = self.paginate(users, filters)

        return users.all()

    def create(self, obj_in: UserCreate):
        user_dict = obj_in.model_dump(exclude={"password"})
        db_obj = self.model(**user_dict)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update_password(self, id: int, password: str):
        db_obj = self.db.query(Users).filter(Users.id == id).first()
        db_obj.hashed_password = password
        self.db.commit()
        self.db.refresh(db_obj)

    def hard_delete(self, id: int):
        db_obj = self.db.query(Users).filter(Users.id == id).first()
        if db_obj:
            self.db.delete(db_obj)
            self.db.commit()
            return True
        return False