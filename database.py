"""
database.py – Async MongoDB client using Motor.
Provides collection accessors and lifecycle hooks for FastAPI.
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "healthbot")

# Singleton client instance
_client: AsyncIOMotorClient = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URI)
    return _client


def get_db():
    return get_client()[MONGO_DB_NAME]


def get_users_collection():
    return get_db()["users"]


def get_chats_collection():
    return get_db()["chats"]


async def connect_db():
    """Called on FastAPI startup – verify the connection."""
    client = get_client()
    await client.admin.command("ping")
    print(f"[DB] Connected to MongoDB database: '{MONGO_DB_NAME}'")


async def close_db():
    """Called on FastAPI shutdown – cleanly close the connection."""
    global _client
    if _client:
        _client.close()
        _client = None
        print("[DB] MongoDB connection closed.")
