from sqlalchemy.orm import Session
from app.models.user import Users
from app.models.enums import UserRole, UserStatus  # <-- ДОБАВЛЕНО: UserStatus
from passlib.context import CryptContext

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

# Данные единственного супер-админа
data = [
    {
        "email": "super.admin@example.com",
        "first_name": "Super",
        "last_name": "Admin",
        # Пароль "Test123"
        "hashed_password": bcrypt_context.hash("Test123"),
        "role": UserRole.SUPER_ADMIN,  # <-- Роль SUPER_ADMIN
        "status": UserStatus.ACTIVE,  # <-- СТАТУС ACTIVE
        "is_active": True  # <-- Явно активный
    }
]


def run(db: Session):
    print("Cleaning users table...")
    try:
        # Удаляем всех существующих пользователей для чистой установки
        db.query(Users).delete()
        db.commit()
        print("All existing users deleted.")
    except Exception as e:
        # Выводим предупреждение, если что-то пошло не так при удалении
        print(f"Warning: Could not delete users: {e}")
        db.rollback()

    print("Seeding super admin...")
    for user_data in data:
        # Создаем нового пользователя
        existing_user = db.query(Users).filter(Users.email == user_data["email"]).first()
        if not existing_user:
            user = Users(**user_data)
            db.add(user)

    db.commit()
    print("Users seeding complete.")