# 🏥 Medicate — Disease Prediction & Doctor Consultation Platform

**Be your own doctor** — AI-powered disease prediction, location-based doctor matching, real-time OSM doctor discovery, WebSocket chat, video consultation, and AI medical assistant.

🌐 **Live Demo**: [web-production-e2451.up.railway.app](https://web-production-e2451.up.railway.app)

---

## ✨ Features

| Feature | Status |
|---------|--------|
| ML Disease Prediction (42 diseases, 97% accuracy) | ✅ |
| 132-symptom interactive picker with search | ✅ |
| Top-5 predictions with confidence bars | ✅ |
| Location-based doctor matching (geocoding) | ✅ |
| **Real doctors from OpenStreetMap (live, no API key needed)** | ✅ |
| **3-tier OSM fallback: speciality → broad healthcare → Nominatim** | ✅ |
| **Hindi + English hospital name search** | ✅ |
| Interactive Leaflet map (patient + registered + real doctors) | ✅ |
| Real-time WebSocket chat | ✅ |
| Video consultation (Agora SDK) | ✅ |
| AI Medical Assistant (Gemini via OpenRouter) | ✅ |
| Dark mode (persistent, system-aware) | ✅ |
| Doctor ratings & reviews | ✅ |
| Consultation history | ✅ |
| Role-based auth (Admin / Doctor / Patient) | ✅ |
| Profile with address → auto-geocoding | ✅ |
| **Deployed on Railway with PostgreSQL + Redis** | ✅ |

---

## 🚀 Quick Setup (Local Development)

### 1. Clone & create virtual environment
```bash
git clone https://github.com/YOUR_USERNAME/medicate.git
cd medicate
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Create your .env file
```bash
cp .env.example .env
# Edit .env with your settings
```

### 4. Train the ML model
```bash
python -m ml.predictor
```

### 5. Run migrations
```bash
python manage.py makemigrations accounts core
python manage.py migrate
```

### 6. Create admin superuser
```bash
python manage.py createsuperuser
```

### 7. Run the server
```bash
# Development:
python manage.py runserver

# With WebSocket support:
daphne -b 0.0.0.0 -p 8000 medicate.asgi:application
```

Visit: **http://127.0.0.1:8000**

---

## 📊 Better ML Accuracy with Kaggle Dataset

1. Go to: https://www.kaggle.com/datasets/kaushi268/disease-prediction-using-machine-learning
2. Download and extract `Training.csv` and `Testing.csv` to the `ml/` folder
3. Run: `python -m ml.predictor`

Without the CSV, the built-in dataset is used (still functional, ~42 diseases).

---

## 🗺️ Real Doctors via OpenStreetMap (No API Key Needed)

Medicate fetches real, live doctors near the patient using a **3-tier fallback strategy**:

1. **Speciality search** — queries `healthcare:speciality` tag (e.g. dermatologist, cardiologist)
2. **Broad healthcare search** — queries hospitals, clinics, and doctors within 20km
3. **Nominatim text search** — last resort, searches by city name

Results show distance, phone number, open/closed status, and a direct map link. No Google Maps API key required.

---

## 🎥 Enable Video Consultations (Agora)

1. Register free at https://console.agora.io
2. Create a project → get **App ID** and **App Certificate**
3. Add to `.env`:
```
AGORA_APP_ID=your_app_id
AGORA_APP_CERT=your_certificate
```

---

## 🤖 Enable AI Medical Assistant (OpenRouter)

1. Register free at https://openrouter.ai
2. Get your API key
3. Add to `.env`:
```
OPENROUTER_API_KEY=your_key
```

---

## ☁️ Deployment (Railway)

This project is deployed on [Railway](https://railway.app) with:
- **PostgreSQL** database (auto-provisioned)
- **Redis** for WebSocket channel layers (auto-provisioned)
- **Daphne** ASGI server for WebSocket support
- Migrations run automatically on every deploy

### Deploy your own
1. Fork this repo
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add PostgreSQL and Redis services
4. Set environment variables:
```
SECRET_KEY         = <generate with: python -c "import secrets; print(secrets.token_urlsafe(50))">
DEBUG              = False
DATABASE_URL       = ${{Postgres.DATABASE_URL}}
REDIS_URL          = ${{Redis.REDIS_URL}}
AGORA_APP_ID       = your_value
AGORA_APP_CERT     = your_value
OPENROUTER_API_KEY = your_value
```
5. Railway auto-deploys → runs migrations → starts server

---

## 📂 Project Structure

```
medicate/
├── manage.py
├── requirements.txt
├── railway.json          ← Railway deployment config
├── Procfile              ← Daphne start command
├── runtime.txt           ← Python 3.12.1
├── .env.example
├── medicate/             ← Django project config
│   ├── settings.py       ← PostgreSQL + Redis auto-detected via env vars
│   ├── urls.py
│   └── asgi.py           ← WebSocket routing
├── accounts/             ← Auth, profiles
│   ├── models.py         ← PatientProfile, DoctorProfile
│   ├── views.py          ← Signup, login, profile
│   └── forms.py
├── core/                 ← Main app
│   ├── models.py         ← Consultation, ChatMessage, Rating
│   ├── views.py          ← All main views + API endpoints + debug
│   ├── consumers.py      ← WebSocket chat
│   ├── utils.py          ← Geocoding, OSM doctor fetch, AI, video tokens
│   └── urls.py
├── ml/                   ← Machine Learning
│   ├── predictor.py      ← Train & predict
│   ├── disease_data.py   ← 42 diseases, 132 symptoms dataset
│   ├── Training.csv      ← (download from Kaggle, optional)
│   └── Testing.csv       ← (download from Kaggle, optional)
├── templates/            ← All HTML templates
│   ├── base.html         ← Master template (dark mode, navbar)
│   ├── core/
│   └── accounts/
└── static/               ← CSS, JS, images
```

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 4.2 + Django Channels (WebSocket) |
| ML | scikit-learn RandomForest + Kaggle dataset |
| Geocoding | geopy / Nominatim (OpenStreetMap) |
| Real Doctors | Overpass API (OpenStreetMap) — no key needed |
| Maps | Leaflet.js + OpenStreetMap |
| Video | Agora RTC SDK |
| AI Assistant | OpenRouter → Gemini Flash |
| Frontend | Django Templates + custom CSS |
| Database | SQLite (dev) → PostgreSQL (prod) |
| WebSockets | In-memory (dev) → Redis (prod) |
| Hosting | Railway |
