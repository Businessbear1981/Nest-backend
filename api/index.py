"""Vercel serverless entry point — wraps the Flask app."""
import sys
import os

# Ensure backend root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Disable SocketIO ticker for serverless
os.environ["VERCEL"] = "1"

from app import app

# Vercel expects the WSGI app as `app`
app = app
