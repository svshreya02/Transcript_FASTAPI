#!/bin/sh
uvicorn app2:app --host=0.0.0.0 --port=${PORT:-8000}
