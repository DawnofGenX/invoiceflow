"""Test bootstrap: force the offline LLM stub and an isolated database.

This module is imported by pytest before any test module, so the environment is set
before `app.config` is loaded and caches its settings.
"""
import os
from pathlib import Path

os.environ.setdefault("LLM_STUB", "1")
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite:///{(Path(__file__).resolve().parent / 'test_invoiceflow.db').as_posix()}",
)
