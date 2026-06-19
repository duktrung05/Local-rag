#!/bin/bash
set -e
echo ""
echo "🤖 RAG Chatbot v2 - Backend"
echo "==================================="
cd "$(dirname "$0")/backend"

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "📝 Đã tạo .env - hãy điền GEMINI_API_KEY"
    echo "   Lấy key miễn phí tại: https://aistudio.google.com/apikey"
    echo ""
fi

[ ! -d "venv" ] && python3 -m venv venv
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null

echo "📦 Cài dependencies..."
pip install -r requirements.txt -q

LLM=$(grep "^LLM_PROVIDER" .env 2>/dev/null | cut -d= -f2 | tr -d ' ')
case "$LLM" in
  gemini) echo "🟡 Dùng Google Gemini ($(grep '^GEMINI_MODEL' .env | cut -d= -f2 | tr -d ' '))" ;;
  claude) echo "🟣 Dùng Anthropic Claude" ;;
  ollama) echo "🟢 Dùng Ollama local" ;;
  *)      echo "🟡 Dùng Gemini (mặc định)" ;;
esac

echo "🚀 Server: http://localhost:8000 | Docs: http://localhost:8000/docs"
echo "==================================="
python main.py
