#!/bin/bash
#
# NeuralForensics NSU — one-click launcher (macOS)
# Double-click this file, or run:  ./start.command
#
cd "$(dirname "$0")" || exit 1

PORT=8080
URL="http://localhost:$PORT"

if [ "$1" == "--restart" ] || [ "$1" == "-r" ]; then
  echo "[NeuralForensics] Stopping previous instance..."
  lsof -tiTCP:$PORT -sTCP:LISTEN -P 2>/dev/null | xargs kill -9 2>/dev/null || true
  sleep 1
elif lsof -tiTCP:$PORT -sTCP:LISTEN -P >/dev/null 2>&1; then
  echo "[NeuralForensics] Server is already running on $URL"
  echo "Opening browser..."
  open "$URL"
  exit 0
fi

echo "[NeuralForensics] Starting analysis server... (first launch may take a moment to load models)"
echo "Logs: $(pwd)/server.log"

nohup python3 detector_server.py > server.log 2>&1 &

# Wait until the server responds (models can take a while to load).
for i in $(seq 1 150); do
  if curl -s -o /dev/null "$URL/" 2>/dev/null; then
    break
  fi
  sleep 1
done

echo "[NeuralForensics] Server is ready: $URL"
open "$URL"

echo ""
echo "Keep this window open. To stop the server later, press Ctrl+C or run:"
echo "  lsof -tiTCP:$PORT -sTCP:LISTEN -P | xargs kill"
