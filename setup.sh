#!/bin/bash
# Medicate Quick Setup Script
set -e

echo "🏥 Setting up Medicate..."

# Virtual environment
if [ ! -d "venv" ]; then
  echo "📦 Creating virtual environment..."
  python3 -m venv venv
fi

# Activate
source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null

# Install deps
echo "📥 Installing dependencies..."
pip install -r requirements.txt -q

# .env
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "⚙️  Created .env from .env.example — edit it to add API keys"
fi

# Train ML model
echo "🧠 Training ML model..."
python ml/predictor.py

# Migrations
echo "🗄️  Running migrations..."
python manage.py makemigrations accounts core --no-input 2>/dev/null || true
python manage.py migrate --no-input

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. python manage.py createsuperuser"
echo "  2. python manage.py runserver"
echo "  3. Visit http://127.0.0.1:8000"
echo ""
echo "Optional:"
echo "  • Add Agora keys to .env for video calls"
echo "  • Add OpenRouter key to .env for AI assistant"
echo "  • Download Kaggle dataset to ml/ for better ML accuracy"
