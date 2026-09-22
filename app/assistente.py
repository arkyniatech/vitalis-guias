"""Assistente do painel: um chat que é cliente do MCP vitalis-guias e segue a Skill conferir-guia.

Não tem regra nova aqui. A cada mensagem:
  1. sobe o MCP (mcp_vitalis/server.py) por stdio e pede a lista de ferramentas;
  2. manda a conversa pro Claude com o SKILL.md como instrução e essas ferramentas;
  3. quando o Claude pede uma ferramenta, chama no MCP e devolve o resultado;
  4. repete até o Claude responder em texto.

É o mesmo caminho de quem usa a Skill no Claude Desktop, só que dentro do sistema.
"""
from __future__ import annotations

import json
import logging
import sys

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app import config

log = logging.getLogger("vitalis.assistente")

SERVIDOR_MCP = config.RAIZ / "mcp_vitalis" / "server.py"
SKILL = config.RAIZ / "skills" / "conferir-guia" / "SKILL.md"
MAX_VOLTAS = 8          # chamadas de ferramenta por mensagem, no máximo
MAX_HISTORICO = 20      # mensagens de texto que voltam do navegador

NO_PAINEL = """

## Onde você está

Você está no chat do painel da Clínica Vitalis, falando com quem opera a clínica (recepção, Carla do faturamento, Dr. Renato).
As ferramentas do MCP vitalis-guias já estão conectadas. Responda em português, curto, no formato da seção "Passo 3".
Use só **negrito**, listas numeradas e quebras de linha: a tela não mostra tabela nem cabeçalho.
Se a pessoa pedir algo fora de guias, convênios e regras da clínica, diga em uma frase que aqui você só confere guias.
"""


def _instrucoes() -> str:
    texto = SKILL.read_text(encoding="utf-8")
    if texto.startswith("---"):           # tira o frontmatter (name/description), que é pro Claude Desktop
        texto = texto.split("---", 2)[2]
    return texto.strip() + NO_PAINEL


def _texto_do_resultado(res) -> str:
    partes = [c.text for c in res.content if getattr(c, "type", "") == "text"]
    return "\n".join(partes) or json.dumps(getattr(res, "structured_content", None) or {}, ensure_ascii=False)


def _limpar_historico(historico: list[dict]) -> list[dict]:
    """O navegador manda só texto. Aceita user/assistant alternados, começando e terminando em user."""
    msgs = [{"role": m["role"], "content": str(m["content"])[:8000]}
            for m in historico[-MAX_HISTORICO:]
            if m.get("role") in ("user", "assistant") and str(m.get("content", "")).strip()]
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    if not msgs or msgs[-1]["role"] != "user":
        raise ValueError("a última mensagem tem que ser da pessoa")
    return msgs


async def responder(historico: list[dict], cliente: anthropic.AsyncAnthropic | None = None) -> dict:
    """Devolve {"texto": resposta, "ferramentas": [{"nome", "entrada"}...]}."""
    if not config.ANTHROPIC_API_KEY and cliente is None:
        return {"texto": "O assistente está desligado: falta a ANTHROPIC_API_KEY no servidor.", "ferramentas": [],
                "erro": "sem_chave"}
    messages = _limpar_historico(historico)
    cliente = cliente or anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    usadas: list[dict] = []

    params = StdioServerParameters(command=sys.executable, args=[str(SERVIDOR_MCP)], cwd=str(config.RAIZ))
    async with stdio_client(params) as (leitura, escrita):
        async with ClientSession(leitura, escrita) as mcp:
            await mcp.initialize()
            ferramentas = [{"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
                           for t in (await mcp.list_tools()).tools]

            for _ in range(MAX_VOLTAS):
                resposta = await cliente.beta.messages.create(
                    model=config.ASSISTENTE_MODELO,
                    max_tokens=16000,
                    system=_instrucoes(),
                    tools=ferramentas,
                    messages=messages,
                    thinking={"type": "adaptive"},
                    output_config={"effort": "medium"},
                    cache_control={"type": "ephemeral"},
                    # se o modelo recusar por política, a API tenta de novo no modelo recomendado
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                )
                if resposta.stop_reason == "refusal":
                    return {"texto": "Não consegui responder essa. Tente reescrever a guia ou a pergunta.",
                            "ferramentas": usadas}
                if resposta.stop_reason != "tool_use":
                    texto = "\n".join(b.text for b in resposta.content if b.type == "text").strip()
                    return {"texto": texto or "(sem resposta)", "ferramentas": usadas}

                messages.append({"role": "assistant", "content": resposta.content})
                resultados = []
                for bloco in resposta.content:
                    if bloco.type != "tool_use":
                        continue
                    usadas.append({"nome": bloco.name, "entrada": bloco.input})
                    try:
                        res = await mcp.call_tool(bloco.name, bloco.input)
                        resultados.append({"type": "tool_result", "tool_use_id": bloco.id,
                                           "content": _texto_do_resultado(res), "is_error": bool(res.is_error)})
                    except Exception as exc:  # uma ferramenta quebrar não derruba o chat
                        log.exception("ferramenta %s falhou", bloco.name)
                        resultados.append({"type": "tool_result", "tool_use_id": bloco.id,
                                           "content": f"Erro ao chamar {bloco.name}: {exc}", "is_error": True})
                messages.append({"role": "user", "content": resultados})

    return {"texto": "A conferência deu muitas voltas e parei por segurança. Tente mandar a guia de novo.",
            "ferramentas": usadas}
