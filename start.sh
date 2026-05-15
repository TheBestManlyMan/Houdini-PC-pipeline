#!/bin/bash
cd "$(dirname "$0")"

echo "Starting pipeline API server..."
python3 python/api_server.py --host 0.0.0.0 &
API_PID=$!

echo "Starting web gallery..."
cd web && npm run dev -- --host &
WEB_PID=$!

echo ""
echo "API:     http://localhost:8765/api"
echo "Gallery: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both."

trap "kill $API_PID $WEB_PID 2>/dev/null; exit" INT TERM
wait
