"""
Quick setup script — copies .env.example to .env if it doesn't exist,
then initializes the database.
"""
import os
import shutil

if not os.path.exists(".env"):
    shutil.copy(".env.example", ".env")
    print("[setup] Created .env from .env.example — fill in your credentials.")
else:
    print("[setup] .env already exists.")

from app.database import init_db
init_db()
print("[setup] Database initialized.")
print("[setup] Done! Run: python run.py")
