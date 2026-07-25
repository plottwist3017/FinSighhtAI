"""
utils/config.py
Reads config from environment variables first, then falls back to
st.secrets when running on Streamlit Community Cloud.

Import this instead of os.getenv() in any service module.
"""

from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv(override=True)


def get_config(key: str, default: str = "") -> str:
    """
    Return a config value by key.
    Priority:
      1. Environment variable (covers local .env and system env)
      2. st.secrets (Streamlit Community Cloud)
      3. default
    """
    value = os.getenv(key, "")
    if value:
        return value

    # Try Streamlit secrets (only available when running inside Streamlit)
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default
