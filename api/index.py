"""Vercel Python runtime giris noktasi.

Vercel, api/ altindaki bu dosyada `app` adinda bir ASGI uygulamasi arar ve
vercel.json'daki rewrite kurali tum istekleri buraya yonlendirir. Boylece
FastAPI uygulamasi (statik PWA dosyalari dahil) serverless olarak calisir.
"""

from zenith.server import app  # noqa: F401
