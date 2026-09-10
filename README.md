# Company Chatbot — Setup

## 1. Backend

```bash
# from the backend folder
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Create a `.env` file in the same folder:

```env
OPENROUTER_API_KEY=your_api_key_here

GMAIL_ADDRESS=youraccount@gmail.com
GMAIL_APP_PASSWORD=your_16_character_app_password
HIRING_MANAGER_EMAIL=manager@yourcompany.com
```

(Get the App Password from https://myaccount.google.com/apppasswords — not your normal Gmail password.)

Run the server:

```bash
uvicorn main:app --reload
```

Backend is now running at `http://127.0.0.1:8000`.
No database setup needed — `chatbot.db` is created automatically on first run.

## 2. Frontend

```bash
# from the frontend folder
npm install
npm run dev
```

Frontend opens at `http://localhost:5173`.

## That's it

Open `http://localhost:5173` in your browser and start chatting.

- Restart the backend (`Ctrl+C` then re-run `uvicorn main:app --reload`) any time you edit a `.py` file, if auto-reload doesn't pick it up.
- To inspect the database: `sqlite3 chatbot.db` then `.tables` / `SELECT * FROM leads;`
