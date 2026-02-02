#!/bin/bash

# Get the directory where the script is located (Project Root)
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd "$PROJECT_ROOT"

# Load .env variables
if [ -f .env ]; then
  echo "📄 Loading .env configuration..."
  # Use set -a to automatically export variables defined in .env
  set -a
  source .env
  set +a
else
  echo "⚠️  .env file not found!"
fi

# Set defaults if not in .env
FRONTEND_PORT=${FRONTEND_PORT:-3000}
FLASK_PORT=${FLASK_PORT:-5001}

echo "🛑 Stopping existing processes..."

# Function to kill process on port
kill_port() {
  local port=$1
  local pid=$(lsof -ti :$port)
  if [ -n "$pid" ]; then
    echo "   Killing process on port $port (PID: $pid)..."
    kill -9 $pid
  else
    echo "   No process found on port $port."
  fi
}

kill_port $FRONTEND_PORT
kill_port $FLASK_PORT

echo "✅ Cleanup complete."
echo ""

# Ensure log directory exists
mkdir -p logs

# Start Backend
echo "🚀 Starting Backend (Flask) on port $FLASK_PORT..."
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "   (Virtual environment activated)"
else
    echo "⚠️  venv not found, using system python"
fi

# Run in background and redirect output
nohup python flask_app.py > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "   Backend started with PID: $BACKEND_PID"

# Start Frontend
echo "🚀 Starting Frontend (Next.js) on port $FRONTEND_PORT..."
cd frontend
# We use PORT env var which Next.js respects when passed to the start command (or we explicitly pass it)
# `npm run dev` typically runs `next dev`. We can append arguments or set PORT env var.
# Setting PORT env var works for `next dev`.
PORT=$FRONTEND_PORT nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "   Frontend started with PID: $FRONTEND_PID"

cd "$PROJECT_ROOT"

echo ""
echo "🎉 All services started!"
echo "   Backend: http://localhost:$FLASK_PORT"
echo "   Frontend: http://localhost:$FRONTEND_PORT"
echo "   Logs are being written to logs/backend.log and logs/frontend.log"
echo ""
echo "   To view logs, run: tail -f logs/backend.log logs/frontend.log"
