```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
#b2
cp .env.example .env
#b3 : lây api 
#b4
python main.py
```
---
1. Kích hoạt môi trường ảo:
   ```bash
   # Windows:
   .\backend\venv\Scripts\activate
   # macOS/Linux:
   source backend/venv/bin/activate
   ```
2. Chạy ứng dụng Streamlit:
   ```bash
   streamlit run streamlit_app.py
   ```
