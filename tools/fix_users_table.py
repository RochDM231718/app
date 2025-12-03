import sys
import os
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.append(os.getcwd())
load_dotenv()

from app.infrastructure.database.connection import get_database_connection


def fix():
    print("🔧 Adding 'created_at' column to users table...")
    db = get_database_connection().get_session()

    try:
        # Команда для добавления колонки с дефолтным значением (текущее время)
        sql = "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();"
        db.execute(text(sql))
        db.commit()
        print("✅ Success: Column 'created_at' added.")
    except Exception as e:
        db.rollback()
        print(f"⚠️ Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    fix()