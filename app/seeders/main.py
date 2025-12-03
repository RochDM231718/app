from dotenv import load_dotenv
load_dotenv()
from app.infrastructure.database.connection import get_database_connection
from app.seeders import users_table_seeder
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import os


def seed():
    print(f"Connecting to DB as: {os.getenv('DB_USERNAME')} on {os.getenv('DB_HOST')}")  # Для отладки

    db_connection = get_database_connection()
    db = db_connection.get_session()

    try:
        users_table_seeder.run(db)
        print("Database seeding completed successfully.")
    except Exception as e:
        db.rollback()
        print(f"An error occurred during seeding: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()