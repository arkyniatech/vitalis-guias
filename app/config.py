"""Configuração por variável de ambiente. Nenhum segredo fica no código."""
import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")


def _env(nome: str, padrao: str = "") -> str:
    return (os.getenv(nome) or padrao).strip()


DATABASE_URL = _env("DATABASE_URL") or f"sqlite:///{RAIZ / 'dados' / 'vitalis.db'}"
# Schema próprio no Postgres (ex. "vitalis"), pra dividir um banco com outros sistemas. Vazio = public.
DB_SCHEMA = _env("DB_SCHEMA")
API_KEY = _env("API_KEY")
DASH_USER = _env("DASH_USER")
DASH_PASS = _env("DASH_PASS")
# Como o operador aparece no painel (ex. "Carla" / "Faturamento"). Vazio = o usuário do login.
DASH_NOME = _env("DASH_NOME")
DASH_PAPEL = _env("DASH_PAPEL", "Faturamento")
OPENAI_API_KEY = _env("OPENAI_API_KEY")
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o-mini")
REGRAS_PATH = RAIZ / _env("REGRAS_PATH", "dados/regras_convenio.json")
# Assistente do painel (chat que usa o MCP e a Skill). Sem chave, a aba avisa que está desligada.
ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
ASSISTENTE_MODELO = _env("ASSISTENTE_MODELO", "claude-opus-5")
