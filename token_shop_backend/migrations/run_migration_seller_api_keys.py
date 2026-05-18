"""
Migration script: Create seller_api_keys table + drop old seller tables.
Run: python migrations/run_migration_seller_api_keys.py
"""
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

backend_env_path = os.path.join(project_root, ".env")
if os.path.exists(backend_env_path):
    from dotenv import load_dotenv
    load_dotenv(backend_env_path)

from sqlalchemy import create_engine, text
from app.config import settings


def run_migration():
    engine = create_engine(settings.DATABASE_URL)

    sql_path = os.path.join(os.path.dirname(__file__), "create_seller_api_keys.sql")
    with open(sql_path, "r", encoding="utf-8") as f:
        sql = f.read()

    print("Running migration: create_seller_api_keys...")

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                if stmt and not stmt.startswith("--"):
                    conn.execute(text(stmt))
            trans.commit()
            print("Migration completed successfully.")
        except Exception as e:
            trans.rollback()
            print(f"Migration failed: {e}")
            raise


if __name__ == "__main__":
    run_migration()
