"""Pytest bootstrap: load .env before test collection so LLM-dependent tests can run."""

from dotenv import load_dotenv

load_dotenv()
