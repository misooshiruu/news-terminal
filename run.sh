#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
mkdir -p data
echo "Starting Market Terminal at http://localhost:8000"
uvicorn src.main:app --host 0.0.0.0 --port 8000 --log-level info
