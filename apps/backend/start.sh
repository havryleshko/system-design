#!/bin/bash
# Startup script for LangGraph API on Render
# This script ensures LangGraph Studio uses the correct public URL

# Render doesn't automatically provide the public URL, so we need to set it
# The service URL is: https://system-design-1m99.onrender.com
# Set this as an environment variable that can be used if needed
export PUBLIC_URL="${PUBLIC_URL:-https://system-design-1m99.onrender.com}"

# Start LangGraph dev server
# Note: LangGraph dev mode constructs baseUrl from host:port, which may not work in production
# For production, consider using LangGraph's production mode or setting up proper URL handling
exec langgraph dev \
    --host 0.0.0.0 \
    --port ${PORT:-10000} \
    --no-reload \
    --no-browser \
    --config langgraph.json

