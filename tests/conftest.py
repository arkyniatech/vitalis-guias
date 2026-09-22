"""Cada teste roda num SQLite em memória e sem IA (fallback por palavra-chave), pra ser determinístico."""
import os

os.environ["OPENAI_API_KEY"] = ""
os.environ["API_KEY"] = "chave-de-teste"
os.environ["DASH_USER"] = ""
os.environ["DASH_PASS"] = ""

import pytest
from sqlalchemy import create_engine

from app import config, db

config.OPENAI_API_KEY = ""
config.API_KEY = "chave-de-teste"
config.DASH_USER = ""


@pytest.fixture(autouse=True)
def banco_limpo():
    from sqlalchemy.pool import StaticPool
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    db.usar_engine(e)
    yield e
    e.dispose()
