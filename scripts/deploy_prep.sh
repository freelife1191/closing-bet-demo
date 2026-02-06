#!/bin/bash

echo "🚀 Deployment Preparation Script"
echo "=============================="

# 1. Check Python Version
PYTHON_VERSION=$(python3 --version)
echo "✅ Detected: $PYTHON_VERSION"

# Create runtime.txt for Render/Heroku
echo "python-3.11.7" > runtime.txt
echo "✅ Created runtime.txt (python-3.11.7)"

# 2. Check Requirements
if [ -f "requirements.txt" ]; then
    echo "✅ requirements.txt exists."
else
    echo "❌ requirements.txt missing!"
    exit 1
fi

# 3. Check Vercel Config
if [ -f "frontend/vercel.json" ]; then
    echo "✅ frontend/vercel.json exists."
else
    echo "❌ frontend/vercel.json missing!"
fi

# 4. Check Procfile
if [ -f "Procfile" ]; then
    echo "✅ Procfile exists."
else
    echo "❌ Procfile missing!"
fi

echo ""
echo "🎉 Ready for Deployment!"
echo "---------------------------------------------------"
echo "1. Backend: Push to GitHub -> Connect to Render (Web Service)"
echo "   - Build Command: pip install -r requirements.txt"
echo "   - Start Command: gunicorn flask_app:app"
echo ""
echo "2. Frontend: Push to GitHub -> Connect to Vercel"
echo "   - Framework: Next.js"
echo "   - Root Directory: frontend"
echo "   - Ensure NEXT_PUBLIC_API_URL is set in Vercel."
echo "---------------------------------------------------"
