#!/bin/bash
# ReasonScript Playground IDE — 起動スクリプト
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLAYGROUND="$REPO_ROOT/playground"
VENV="$PLAYGROUND/.venv"

echo "=== ReasonScript Playground IDE ==="

# --- backend ---
echo "▶ Backend 起動 (port 8000)..."
cd "$REPO_ROOT"
PYTHONPATH="$REPO_ROOT" "$VENV/bin/uvicorn" playground.backend.main:app \
  --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# --- frontend dev server ---
echo "▶ Frontend 起動 (port 5173)..."
cd "$PLAYGROUND/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✓ Playground IDE が起動しました"
echo "  → http://localhost:5173"
echo ""
echo "停止するには Ctrl+C を押してください"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" EXIT INT TERM
wait
