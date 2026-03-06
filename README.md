# 🏥 Medicate — Disease Prediction & Doctor Consultation Platform

**Be your own doctor** — AI-powered disease prediction, location-based doctor matching, real-time chat, video consultation, and AI medical assistant.

---

## 🚀 Quick Setup (PyCharm / Any IDE)

### 1. Create & activate virtual environment
```bash
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
# Optional: Download Kaggle dataset first (see below)
python ml/predictor.py
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
# Development (no WebSocket):
python manage.py runserver

# Production with WebSocket support:
pip install daphne
daphne -b 0.0.0.0 -p 8000 medicate.asgi:application
```

Visit: **http://127.0.0.1:8000**

---

## 📊 Better ML Accuracy with Kaggle Dataset

1. Go to: https://www.kaggle.com/datasets/kaushi268/disease-prediction-using-machine-learning
2. Download and extract `Training.csv` and `Testing.csv` to the `ml/` folder
3. Run: `python ml/predictor.py`

Without the CSV, the built-in dataset is used (still functional, ~42 diseases).

---

## 🎥 Enable Video Consultations (Agora)

1. Register free at https://console.agora.io
2. Create a project, get **App ID** and **App Certificate**
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

## 🔴 Enable Redis for Production WebSockets

```bash
# Install Redis
# Ubuntu: sudo apt install redis-server
# Mac: brew install redis
# Windows: use Docker: docker run -p 6379:6379 redis

# In settings.py, uncomment the Redis CHANNEL_LAYERS config
```

---

## 📂 Project Structure

```
medicate/
├── manage.py
├── requirements.txt
├── .env.example
├── medicate/           ← Django project config
│   ├── settings.py
│   ├── urls.py
│   └── asgi.py         ← WebSocket routing
├── accounts/           ← Auth, profiles
│   ├── models.py       ← PatientProfile, DoctorProfile
│   ├── views.py        ← Signup, login, profile
│   └── forms.py
├── core/               ← Main app
│   ├── models.py       ← Consultation, ChatMessage, Rating
│   ├── views.py        ← All main views + API endpoints
│   ├── consumers.py    ← WebSocket chat
│   ├── utils.py        ← Geocoding, doctor matching, AI, video tokens
│   └── urls.py
├── ml/                 ← Machine Learning
│   ├── predictor.py    ← Train & predict
│   ├── disease_data.py ← 42 diseases, 132 symptoms dataset
│   ├── Training.csv    ← (download from Kaggle)
│   └── Testing.csv     ← (download from Kaggle)
├── templates/          ← All HTML templates
│   ├── base.html       ← Master template (dark mode, navbar)
│   ├── core/
│   └── accounts/
└── static/             ← CSS, JS, images
```

---

## ✨ Features

| Feature | Status |
|---------|--------|
| ML Disease Prediction (42 diseases, 97% acc) | ✅ |
| 132-symptom interactive picker with search | ✅ |
| Top-5 predictions with confidence bars | ✅ |
| Location-based doctor matching (geocoding) | ✅ |
| Interactive Leaflet map of doctors | ✅ |
| Real-time WebSocket chat | ✅ |
| Video consultation (Agora SDK) | ✅ |
| AI Medical Assistant (Gemini via OpenRouter) | ✅ |
| Dark mode (persistent, system-aware) | ✅ |
| Doctor ratings & reviews | ✅ |
| Consultation history | ✅ |
| Role-based auth (Admin/Doctor/Patient) | ✅ |
| Profile with address → auto-geocoding | ✅ |

---

## 🛠 Tech Stack

- **Backend**: Django 4.2 + Django Channels (WebSocket)
- **ML**: scikit-learn RandomForest + Kaggle dataset
- **Geocoding**: geopy / Nominatim (OpenStreetMap)
- **Maps**: Leaflet.js + OpenStreetMap
- **Video**: Agora RTC SDK
- **AI**: OpenRouter → Gemini Flash
- **Frontend**: Django Templates + custom CSS design system
- **DB**: SQLite (dev) → PostgreSQL (prod)
