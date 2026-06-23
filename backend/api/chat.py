from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import logging
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict]
    documents_found: int
    usage: Dict
    provider: str
    conversation_id: str
    message_id: str


def get_rag():
    from main import rag_engine
    if rag_engine is None:
        raise HTTPException(status_code=503, detail="RAG Engine chưa khởi tạo.")
    return rag_engine


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, engine=Depends(get_rag)):
    import core.chat_history as ch

    # Tạo hoặc lấy conversation
    conv_id = request.conversation_id
    if not conv_id:
        conv = ch.create_conversation()
        conv_id = conv["id"]
    elif not ch.get_conversation(conv_id):
        raise HTTPException(status_code=404, detail="Conversation không tồn tại")

    # Lấy lịch sử (giới hạn N tin nhắn)
    history = ch.get_messages(conv_id, limit=settings.chat_history_limit)
    history_fmt = [{"role": m["role"], "content": m["content"]} for m in history]

    # Lưu câu hỏi user
    ch.add_message(conv_id, "user", request.query)

    try:
        result = engine.chat(
            query=request.query,
            conversation_history=history_fmt,
            top_k=request.top_k,
            threshold=request.threshold
        )
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Lưu câu trả lời
    msg = ch.add_message(conv_id, "assistant", result["answer"],
                         sources=result["sources"], provider=result["provider"])

    # Auto-title nếu là tin đầu tiên
    msgs = ch.get_messages(conv_id)
    if len(msgs) == 2:
        title = request.query[:50] + ("..." if len(request.query) > 50 else "")
        ch.update_conversation_title(conv_id, title)

    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        documents_found=result["documents_found"],
        usage=result["usage"],
        provider=result["provider"],
        conversation_id=conv_id,
        message_id=msg["id"]
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, engine=Depends(get_rag)):
    import json
    import core.chat_history as ch

    conv_id = request.conversation_id
    if not conv_id:
        conv = ch.create_conversation()
        conv_id = conv["id"]

    history = ch.get_messages(conv_id, limit=settings.chat_history_limit)
    history_fmt = [{"role": m["role"], "content": m["content"]} for m in history]
    ch.add_message(conv_id, "user", request.query)

    full_answer = []

    async def generate():
        sources_list = []
        async for chunk in engine.chat_stream(
            query=request.query, conversation_history=history_fmt,
            top_k=request.top_k, threshold=request.threshold
        ):
            if chunk.startswith("data: "):
                try:
                    clean_chunk = chunk[6:].strip()
                    if clean_chunk:
                        data = json.loads(clean_chunk)
                        if data.get("type") == "token":
                            full_answer.append(data.get("data", ""))
                        elif data.get("type") == "sources":
                            sources_list = data.get("data", [])
                except Exception as e:
                    logger.error(f"Lỗi parse stream chunk: {e}")
            # Also send conv_id on first event
            yield chunk

        # Save assistant reply
        answer_text = "".join(full_answer)
        if answer_text:
            ch.add_message(conv_id, "assistant", answer_text, sources=sources_list, provider=engine.provider)
        
        # Auto-title nếu là tin đầu tiên
        msgs = ch.get_messages(conv_id)
        if len(msgs) == 2:
            title = request.query[:30] + ("..." if len(request.query) > 30 else "")
            ch.update_conversation_title(conv_id, title)

        yield f"data: {json.dumps({'type': 'conv_id', 'data': conv_id})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
