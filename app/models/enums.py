from enum import Enum

class UserRole(str, Enum):
    GUEST = "guest"
    STUDENT = "student"
    MODERATOR = "moderator"
    SUPER_ADMIN = "super_admin"

class UserStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"
    DELETED = "deleted"

class AchievementStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class UserTokenType(str, Enum):
    RESET_PASSWORD = "reset_password"
    EMAIL_VERIFICATION = "email_verification"