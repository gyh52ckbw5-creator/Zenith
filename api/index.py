"""Vercel Serverless Function entry point.

Zenith'i Vercel'de çalıştırmak için giriş noktası.
"""

from zenith.server import app

# Vercel Serverless Function
handler = app
