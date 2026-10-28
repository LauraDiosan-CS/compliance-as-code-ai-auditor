"""Vercel entrypoint: the Python runtime auto-detects the FastAPI `app` exported from this file.

Deploy as a separate Vercel project with Root Directory `app/backend`. On Vercel (env `VERCEL=1`)
the API runs in deterministic mode and fetches GitHub repositories as tarballs when `git` is missing.
Locally you can also run `uvicorn index:app` from this directory.
"""

from ccauditor.api import app

__all__ = ["app"]
