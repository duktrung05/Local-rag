from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import core.chat_history as ch

router = APIRouter()


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    sources: List[Dict]
    provider: str
    created_at: str


class UpdateTitleRequest(BaseModel):
    title: str


@router.get("/conversations", response_model=List[ConversationOut])
def list_conversations(limit: int = 50):
    return ch.get_conversations(limit)


@router.post("/conversations", response_model=ConversationOut)
def create_conversation(title: str = "Cuộc trò chuyện mới"):
    return ch.create_conversation(title)


@router.get("/conversations/{conv_id}", response_model=ConversationOut)
def get_conversation(conv_id: str):
    conv = ch.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Không tìm thấy conversation")
    return conv


@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    if not ch.delete_conversation(conv_id):
        raise HTTPException(status_code=404, detail="Không tìm thấy conversation")
    return {"message": "Đã xóa"}


@router.get("/conversations/{conv_id}/messages", response_model=List[MessageOut])
def get_messages(conv_id: str):
    if not ch.get_conversation(conv_id):
        raise HTTPException(status_code=404, detail="Không tìm thấy conversation")
    return ch.get_messages(conv_id)


@router.patch("/conversations/{conv_id}/title")
def update_title(conv_id: str, body: UpdateTitleRequest):
    ch.update_conversation_title(conv_id, body.title)
    return {"message": "Đã cập nhật"}


@router.delete("/conversations")
def clear_all_conversations():
    ch.clear_all_conversations()
    return {"message": "Đã xóa toàn bộ cuộc trò chuyện"}
