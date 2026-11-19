"""
models.py – Pydantic request/response schemas for auth and chat persistence.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=40)
    email: EmailStr
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    email: str
    user_id: str


class UserProfile(BaseModel):
    user_id: str
    username: str
    email: str


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str                        # "user" | "assistant"
    content: str
    timestamp: Optional[datetime] = None
    is_vision: Optional[bool] = False


class SaveChatRequest(BaseModel):
    session_id: str                  # UUID generated client-side
    title: Optional[str] = "Chat"
    messages: List[ChatMessage]


class ChatSessionSummary(BaseModel):
    session_id: str
    title: str
    message_count: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class ChatSessionDetail(BaseModel):
    session_id: str
    title: str
    messages: List[ChatMessage]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
