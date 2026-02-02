#!/bin/bash

# Get the directory where the script is located (Project Root)
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd "$PROJECT_ROOT"

# Load .env variables
if [ -f .env ]; then
  echo "📄 Loading .env configuration..."
  set -a
  source .env
  set +a
else
  echo "⚠️  .env file not found!"
fi

# Set defaults if not in .env
FRONTEND_PORT=${FRONTEND_PORT:-3000}
FLASK_PORT=${FLASK_PORT:-5001}

echo "🛑 Stopping services..."

# Function to kill process on port
kill_port() {
  local port=$1
  local pid=$(lsof -ti :$port)
  if [ -n "$pid" ]; then
    echo "   Killing process on port $port (PID: $pid)..."
    kill -9 $pid
    echo "   ✅ Port $port cleared."
  else
    echo "   ℹ️  No process found on port $port."
  fi
}

kill_port $FRONTEND_PORT
kill_port $FLASK_PORT

echo ""
echo "✅ All services stopped safely."
