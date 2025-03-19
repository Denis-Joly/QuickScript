#!/bin/bash

# Kill existing processes
echo "Cleaning up any existing processes..."
pkill -f 'uvicorn app.main:app' || true
pkill -f 'npm run tauri dev' || true
pkill -f 'tauri dev' || true

# Wait for processes to terminate
sleep 1

# Start backend
echo "Starting backend..."
cd /Users/genericlcsb/GIT_perso/QuickScript/backend
source venv/bin/activate
uvicorn app.main:app --reload > /tmp/quickscript-backend.log 2>&1 &

# Start frontend
echo "Starting frontend..."
cd /Users/genericlcsb/GIT_perso/QuickScript/frontend
npm run tauri dev > /tmp/quickscript-frontend.log 2>&1 &

echo "QuickScript development environment is now running!"
echo "Backend logs: /tmp/quickscript-backend.log"
echo "Frontend logs: /tmp/quickscript-frontend.log"