@echo off
:: ===================================================
:: RAG Chatbot v2 - Khởi chạy Streamlit Frontend
:: ===================================================
echo.
echo [RAG Chatbot v2] Dang khoi dong Streamlit Frontend...
echo ===================================================

cd /d "%~dp0"
call backend\venv\Scripts\activate.bat
streamlit run streamlit_app.py

pause
