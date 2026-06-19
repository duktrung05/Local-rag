@echo off
:: ============================================
:: RAG Chatbot v2 - Start Backend (Windows)
:: ============================================
echo.
echo [RAG Chatbot v2] Khoi dong Backend...
echo ======================================

cd /d "%~dp0backend"

if not exist ".env" (
    echo [!] Tao file .env tu mau...
    copy .env.example .env
    echo.
    echo [*] Mo file backend\.env va chon LLM provider:
    echo     - Ollama (mien phi): LLM_PROVIDER=ollama
    echo     - Claude (cloud):    LLM_PROVIDER=claude + ANTHROPIC_API_KEY=sk-ant-...
    echo.
    pause
)

if not exist "venv" (
    echo [*] Tao virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo [*] Cai dat dependencies...
pip install -r requirements.txt -q

echo.
echo [*] Khoi dong server tai http://localhost:8000
echo     API Docs: http://localhost:8000/docs
echo     Nhan Ctrl+C de dung
echo ======================================
echo.

python main.py
pause
