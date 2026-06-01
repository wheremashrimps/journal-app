# Folio — Personal Journal

A dark, moody personal journal app. Upload entries with text, photos, and metadata. Sort and filter by date, event, or place.

## Stack
- **Backend**: Python / Flask
- **Database**: SQLite (file-based, zero config)
- **Frontend**: Vanilla JS + HTML/CSS (no build step)
- **Hosting**: Railway

---

## Local Development

```bash
# 1. Create a virtual environment
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python app.py
# → Open http://localhost:5000
```

---

## Deploy to Railway

### Option A — GitHub (recommended)

1. Push this folder to a new GitHub repo
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
3. Select your repo — Railway auto-detects Python/Nixpacks
4. It will build and deploy automatically. Done!

### Option B — Railway CLI

```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

---

## ⚠️ Persistent Storage on Railway

SQLite writes to disk. By default Railway's filesystem is **ephemeral** — it resets on redeploy.

**To keep your data between deploys:**

1. In your Railway project → click your service → **Volumes**
2. Add a volume mounted at `/app/data`
3. Update `app.py` line ~14:
   ```python
   app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:////app/data/journal.db"
   ```
4. Also update `UPLOAD_FOLDER`:
   ```python
   UPLOAD_FOLDER = '/app/data/uploads'
   ```

This ensures your entries and photos survive redeploys.

---

## Features
- Create, edit, delete journal entries
- Attach multiple photos per entry (drag & drop or click to upload)
- Tag each entry with an **Event** and **Place**
- Sort by Date, Event, or Place
- Filter by event or place using dropdowns
- Full-text search across title, body, event, and place
- Photo lightbox viewer
