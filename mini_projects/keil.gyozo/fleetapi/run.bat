@echo off
echo Starting Fleet API Client...
uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause
