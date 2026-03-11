#!/bin/bash
export PATH="/Users/miso/Desktop/Investing/Current Events/venv/bin:$PATH"
cd "/Users/miso/Desktop/Investing/Current Events"
exec uvicorn src.main:app --host 0.0.0.0 --port 8000 --log-level info
