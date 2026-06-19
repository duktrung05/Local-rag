import logging
import json
import httpx
from typing import List, Dict, Any, AsyncGenerator, Optional

from core.config import settings
from core.embedding_manager import EmbeddingManager

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Bạn là trợ lý AI thông minh, trả lời câu hỏi dựa trên tài liệu được cung cấp.

Nguyên tắc:
1. Ưu tiên thông tin từ tài liệu được cung cấp
2. Nếu không có thông tin trong tài liệu, nói rõ và bổ sung kiến thức chung nếu cần
3. Trả lời bằng ngôn ngữ của câu hỏi (tiếng Việt hoặc tiếng Anh)
4. Câu trả lời rõ ràng, có cấu trúc, dùng markdown khi cần
5. Khi dùng thông tin từ tài liệu, đề cập tên file nguồn"""


class RAGEngine:
    def __init__(self, embedding_manager: EmbeddingManager):
        self.embedding_manager = embedding_manager
        self.provider = settings.llm_provider
        self._init_llm_client()
        
        # Tích hợp CrossEncoder cho bước Rerank nếu được bật
        self.reranker = None
        if getattr(settings, "use_reranker", True):
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"Loading Reranker model: {settings.reranker_model}...")
                self.reranker = CrossEncoder(settings.reranker_model)
                logger.info("Reranker model loaded successfully.")
            except Exception as e:
                logger.error(f"Lỗi khi load Reranker model: {e}. Tự động tắt Rerank.")
                self.reranker = None

    def _init_llm_client(self):
        if self.provider == "groq":
            from openai import OpenAI
            self.groq_client = OpenAI(
                api_key=settings.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
            )
            logger.info(f"LLM: Groq ({settings.groq_model}) - hoạt động tốt ở VN")

        elif self.provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=settings.gemini_api_key)
            self.gemini_client = genai.GenerativeModel(
                model_name=settings.gemini_model,
                system_instruction=SYSTEM_PROMPT,
                generation_config={
                    "temperature": settings.temperature,
                    "max_output_tokens": settings.max_tokens,
                }
            )
            logger.info(f"LLM: Gemini ({settings.gemini_model})")

        elif self.provider == "claude":
            import anthropic
            self.claude_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            logger.info(f"LLM: Claude ({settings.claude_model})")

        else:  # ollama
            logger.info(f"LLM: Ollama ({settings.ollama_model})")

    # ── Rerank Step ───────────────────────────────────────────────
    def rerank(self, query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sắp xếp lại các documents bằng Cross-Encoder"""
        if not documents or self.reranker is None:
            return documents

        logger.info(f"Reranking {len(documents)} documents for query: '{query}'")
        pairs = [[query, doc["content"]] for doc in documents]
        try:
            scores = self.reranker.predict(pairs)
            for doc, score in zip(documents, scores):
                doc["metadata"]["retrieval_score"] = doc.get("score", 0.0)
                doc["score"] = float(score)

            # Sắp xếp giảm dần theo điểm của reranker
            reranked_docs = sorted(documents, key=lambda x: x["score"], reverse=True)
            top_n = getattr(settings, "reranker_top_n", 3)
            final_docs = reranked_docs[:top_n]
            logger.info(f"Reranked: giữ lại {len(final_docs)}/{len(documents)} documents")
            return final_docs
        except Exception as e:
            logger.error(f"Lỗi khi thực hiện Rerank: {e}")
            return documents

    # ── Retrieve ──────────────────────────────────────────────────
    def retrieve_documents(self, query: str, top_k: int = None,
                           threshold: float = None) -> List[Dict]:
        k = top_k or settings.top_k_results
        min_score = threshold or settings.similarity_threshold

        logger.info(f"--- Bắt đầu retrieve tài liệu cho truy vấn: '{query}' ---")

        # 1. Tách biệt nhúng truy vấn
        logger.info("Bước 1: Nhúng câu hỏi thành vector")
        query_vector = self.embedding_manager.embed_text(query)
        logger.info(f"Đã tạo vector nhúng câu hỏi (chiều: {len(query_vector)})")

        # 2. Tìm kiếm ngữ nghĩa trong Vector DB
        use_rerank = getattr(settings, "use_reranker", True) and self.reranker is not None
        retrieve_k = max(k, 10) if use_rerank else k

        logger.info(f"Bước 2: Tìm kiếm ngữ nghĩa trong ChromaDB với retrieve_k={retrieve_k}")
        results = self.embedding_manager.search(top_k=retrieve_k, query_embedding=query_vector)

        # Lọc theo threshold ban đầu
        filtered_results = [r for r in results if r["score"] >= min_score]
        logger.info(f"Tìm thấy {len(filtered_results)} tài liệu vượt qua ngưỡng {min_score}")

        # 3. Rerank tài liệu
        if use_rerank and filtered_results:
            logger.info("Bước 3: Thực hiện Rerank tài liệu bằng Cross-Encoder")
            final_docs = self.rerank(query, filtered_results)
        else:
            if not use_rerank:
                logger.info("Bỏ qua bước Rerank (không được bật hoặc model chưa được tải)")
            final_docs = filtered_results[:k]

        logger.info(f"--- Hoàn thành retrieve. Trả về {len(final_docs)} tài liệu ---")
        return final_docs

    # ── Build Prompt ──────────────────────────────────────────────
    def build_prompt(self, query: str, documents: List[Dict], conversation_history: List[Dict] = None) -> List[Dict[str, str]]:
        """Xây dựng prompt chuẩn hóa thành 4 phần riêng biệt"""
        # 1. System Prompt
        system_content = SYSTEM_PROMPT

        # 2. Retrieved Context (Đã qua Rerank)
        parts = []
        for i, doc in enumerate(documents, 1):
            src = doc["metadata"].get("file_name", "?")
            page = doc["metadata"].get("page", "")
            page_str = f" trang {page}" if page else ""
            score_str = f"score: {doc['score']:.2f}" if "score" in doc else "N/A"
            parts.append(
                f"[Tài liệu {i} - {src}{page_str} | {score_str}]\n"
                f"{doc['content']}"
            )
        context_content = "\n\n---\n\n".join(parts) if parts else "Không tìm thấy tài liệu liên quan."

        # Cấu trúc rõ ràng 4 phần dưới dạng danh sách tin nhắn
        messages = [
            {"role": "system", "content": system_content},
            {"role": "context", "content": context_content}
        ]

        # 3. Chat History (N tin nhắn gần nhất)
        if conversation_history:
            limit = getattr(settings, "chat_history_limit", 10)
            for msg in conversation_history[-limit:]:
                messages.append({"role": msg["role"], "content": msg["content"]})

        # 4. User Query (Câu hỏi hiện tại)
        messages.append({"role": "user", "content": query})

        return messages

    # ── Chat (sync) ───────────────────────────────────────────────
    def chat(self, query: str, conversation_history: List[Dict] = None,
             top_k: int = None, threshold: float = None) -> Dict[str, Any]:
        documents = self.retrieve_documents(query, top_k, threshold)
        messages = self.build_prompt(query, documents, conversation_history)

        if self.provider == "groq":
            answer, usage = self._call_groq(messages)
        elif self.provider == "gemini":
            answer, usage = self._call_gemini(messages)
        elif self.provider == "claude":
            answer, usage = self._call_claude(messages)
        else:
            answer, usage = self._call_ollama(messages)

        return {
            "answer": answer,
            "sources": self._extract_sources(documents),
            "documents_found": len(documents),
            "usage": usage,
            "provider": self.provider,
        }

    # ── Groq sync (OpenAI-compatible) ─────────────────────────────
    def _call_groq(self, messages: List[Dict]) -> tuple:
        groq_messages = []
        for msg in messages:
            if msg["role"] == "context":
                groq_messages.append({"role": "system", "content": f"Ngữ cảnh tham khảo:\n\n{msg['content']}"})
            else:
                groq_messages.append(msg)

        try:
            resp = self.groq_client.chat.completions.create(
                model=settings.groq_model,
                messages=groq_messages,
                temperature=settings.temperature,
                max_tokens=settings.max_tokens,
            )
            return resp.choices[0].message.content, {
                "input_tokens": resp.usage.prompt_tokens,
                "output_tokens": resp.usage.completion_tokens,
            }
        except Exception as e:
            err_str = str(e)
            if "Connection error" in err_str or "APIConnectionError" in type(e).__name__ or "connect" in err_str.lower():
                raise ConnectionError(f"Không kết nối được đến Groq API: {e}")
            raise

    # ── Gemini sync ───────────────────────────────────────────────
    def _call_gemini(self, messages: List[Dict]) -> tuple:
        system_parts = []
        gemini_history = []
        for msg in messages[:-1]:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            elif msg["role"] == "context":
                system_parts.append(f"Ngữ cảnh tham khảo:\n\n{msg['content']}")
            else:
                role = "user" if msg["role"] == "user" else "model"
                gemini_history.append({"role": role, "parts": [msg["content"]]})

        combined_system = "\n\n---\n\n".join(system_parts)

        import google.generativeai as genai
        # Tạo model với system instruction động chứa System Prompt + Context
        model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=combined_system,
            generation_config={
                "temperature": settings.temperature,
                "max_output_tokens": settings.max_tokens,
            }
        )

        chat = model.start_chat(history=gemini_history)
        response = chat.send_message(messages[-1]["content"])
        usage = {
            "input_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
            "output_tokens": getattr(response.usage_metadata, "candidates_token_count", 0),
        }
        return response.text, usage

    # ── Claude sync ───────────────────────────────────────────────
    def _call_claude(self, messages: List[Dict]) -> tuple:
        system_parts = []
        claude_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            elif msg["role"] == "context":
                system_parts.append(f"Ngữ cảnh tham khảo:\n\n{msg['content']}")
            else:
                role = "assistant" if msg["role"] == "model" else msg["role"]
                claude_messages.append({"role": role, "content": msg["content"]})

        combined_system = "\n\n---\n\n".join(system_parts)

        resp = self.claude_client.messages.create(
            model=settings.claude_model,
            max_tokens=settings.max_tokens,
            system=combined_system,
            messages=claude_messages,
        )
        return resp.content[0].text, {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        }

    # ── Ollama sync ───────────────────────────────────────────────
    def _call_ollama(self, messages: List[Dict]) -> tuple:
        ollama_messages = []
        for msg in messages:
            if msg["role"] == "context":
                ollama_messages.append({"role": "system", "content": f"Ngữ cảnh tham khảo:\n\n{msg['content']}"})
            else:
                ollama_messages.append(msg)

        payload = {
            "model": settings.ollama_model,
            "messages": ollama_messages,
            "stream": False,
            "options": {"temperature": settings.temperature,
                        "num_predict": settings.max_tokens},
        }
        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(f"{settings.ollama_base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return (
                    data.get("message", {}).get("content", ""),
                    {"input_tokens": data.get("prompt_eval_count", 0),
                     "output_tokens": data.get("eval_count", 0)},
                )
        except httpx.ConnectError:
            raise ConnectionError(
                f"Không kết nối được Ollama tại {settings.ollama_base_url}. "
                "Hãy chạy: ollama serve"
            )

    # ── Streaming ─────────────────────────────────────────────────
    async def chat_stream(self, query: str, conversation_history: List[Dict] = None,
                          top_k: int = None,
                          threshold: float = None) -> AsyncGenerator[str, None]:
        documents = self.retrieve_documents(query, top_k, threshold)
        sources = self._extract_sources(documents)
        yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n"

        messages = self.build_prompt(query, documents, conversation_history)

        if self.provider == "groq":
            async for chunk in self._stream_groq(messages):
                yield chunk
        elif self.provider == "gemini":
            async for chunk in self._stream_gemini(messages):
                yield chunk
        elif self.provider == "claude":
            async for chunk in self._stream_claude(messages):
                yield chunk
        else:
            async for chunk in self._stream_ollama(messages):
                yield chunk

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    # ── Groq stream ───────────────────────────────────────────────
    async def _stream_groq(self, messages: List[Dict]):
        """Groq stream dùng asyncio.to_thread (openai sync SDK)"""
        import asyncio

        groq_messages = []
        for msg in messages:
            if msg["role"] == "context":
                groq_messages.append({"role": "system", "content": f"Ngữ cảnh tham khảo:\n\n{msg['content']}"})
            else:
                groq_messages.append(msg)

        def _sync():
            return self.groq_client.chat.completions.create(
                model=settings.groq_model,
                messages=groq_messages,
                temperature=settings.temperature,
                max_tokens=settings.max_tokens,
                stream=True,
            )

        try:
            stream = await asyncio.to_thread(_sync)
            for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                if token:
                    yield f"data: {json.dumps({'type': 'token', 'data': token})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"

    # ── Gemini stream ─────────────────────────────────────────────
    async def _stream_gemini(self, messages: List[Dict]):
        import asyncio

        system_parts = []
        gemini_history = []
        for msg in messages[:-1]:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            elif msg["role"] == "context":
                system_parts.append(f"Ngữ cảnh tham khảo:\n\n{msg['content']}")
            else:
                role = "user" if msg["role"] == "user" else "model"
                gemini_history.append({"role": role, "parts": [msg["content"]]})
        
        combined_system = "\n\n---\n\n".join(system_parts)
        last_msg = messages[-1]["content"]

        def _sync():
            import google.generativeai as genai
            model = genai.GenerativeModel(
                model_name=settings.gemini_model,
                system_instruction=combined_system,
                generation_config={
                    "temperature": settings.temperature,
                    "max_output_tokens": settings.max_tokens,
                }
            )
            chat = model.start_chat(history=gemini_history)
            return chat.send_message(last_msg, stream=True)

        try:
            response = await asyncio.to_thread(_sync)
            for chunk in response:
                if chunk.text:
                    yield f"data: {json.dumps({'type': 'token', 'data': chunk.text})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"

    # ── Claude stream ─────────────────────────────────────────────
    async def _stream_claude(self, messages: List[Dict]):
        import anthropic
        
        system_parts = []
        claude_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            elif msg["role"] == "context":
                system_parts.append(f"Ngữ cảnh tham khảo:\n\n{msg['content']}")
            else:
                role = "assistant" if msg["role"] == "model" else msg["role"]
                claude_messages.append({"role": role, "content": msg["content"]})
                
        combined_system = "\n\n---\n\n".join(system_parts)

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        async with client.messages.stream(
            model=settings.claude_model,
            max_tokens=settings.max_tokens,
            system=combined_system,
            messages=claude_messages,
        ) as stream:
            async for text in stream.text_stream:
                yield f"data: {json.dumps({'type': 'token', 'data': text})}\n\n"

    # ── Ollama stream ─────────────────────────────────────────────
    async def _stream_ollama(self, messages: List[Dict]):
        ollama_messages = []
        for msg in messages:
            if msg["role"] == "context":
                ollama_messages.append({"role": "system", "content": f"Ngữ cảnh tham khảo:\n\n{msg['content']}"})
            else:
                ollama_messages.append(msg)

        payload = {
            "model": settings.ollama_model,
            "messages": ollama_messages,
            "stream": True,
            "options": {"temperature": settings.temperature,
                        "num_predict": settings.max_tokens},
        }
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream("POST",
                                         f"{settings.ollama_base_url}/api/chat",
                                         json=payload) as resp:
                    async for line in resp.aiter_lines():
                        if line:
                            data = json.loads(line)
                            token = data.get("message", {}).get("content", "")
                            if token:
                                yield f"data: {json.dumps({'type': 'token', 'data': token})}\n\n"
        except httpx.ConnectError:
            yield f"data: {json.dumps({'type': 'error', 'data': 'Không kết nối Ollama'})}\n\n"

    # ── Helpers ───────────────────────────────────────────────────
    def _extract_sources(self, documents: List[Dict]) -> List[Dict]:
        sources, seen = [], set()
        for doc in documents:
            fn = doc["metadata"].get("file_name", "")
            if fn and fn not in seen:
                seen.add(fn)
                sources.append({
                    "file_name": fn,
                    "score": doc["score"],
                    "page": doc["metadata"].get("page"),
                })
        return sources
