"""O assistente é cliente do MCP de verdade: sobe o servidor, lista as ferramentas e chama verificar_guia.
O Claude é trocado por um falso que pede a ferramenta e depois responde, pra não gastar API no teste."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from app import assistente

RAIZ = Path(__file__).resolve().parent.parent
GUIA = json.loads((RAIZ / "dados" / "exemplo_guia_nova.json").read_text())


class ClaudeFalso:
    def __init__(self):
        self.chamadas = []
        self.beta = NS(messages=NS(create=self.create))

    async def create(self, **kw):
        self.chamadas.append(kw)
        if len(self.chamadas) == 1:
            return NS(stop_reason="tool_use", content=[
                NS(type="tool_use", id="t1", name="verificar_guia", input={"guia": GUIA})])
        resultado = kw["messages"][-1]["content"][0]
        return NS(stop_reason="end_turn", content=[NS(type="text", text=resultado["content"])])


def test_assistente_chama_o_mcp_e_segue_a_skill():
    falso = ClaudeFalso()
    r = asyncio.run(assistente.responder([{"role": "user", "content": "confere essa guia"}], cliente=falso))
    assert [f["nome"] for f in r["ferramentas"]] == ["verificar_guia"]
    assert json.loads(r["texto"])["decisao"] == "PENDENTE"            # veio do MCP, não do "modelo"
    primeira = falso.chamadas[0]
    assert {t["name"] for t in primeira["tools"]} >= {"consultar_regra", "verificar_guia"}
    assert "Conferir guia (Clínica Vitalis)" in primeira["system"]    # instruções = SKILL.md


def test_historico_invalido():
    with pytest.raises(ValueError):
        assistente._limpar_historico([{"role": "assistant", "content": "oi"}])


def test_erro_da_api_vira_mensagem_e_nao_500(monkeypatch):
    import anthropic
    import httpx
    from fastapi.testclient import TestClient
    from app import config
    from app.main import app

    class ClaudeFora(ClaudeFalso):
        async def create(self, **kw):
            raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))

    original = assistente.responder
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(assistente, "responder", lambda h: original(h, cliente=ClaudeFora()))
    r = TestClient(app).post("/assistente/mensagem", json={"historico": [{"role": "user", "content": "oi"}]})
    assert r.status_code == 502 and r.json()["erro"] == "conexao"
