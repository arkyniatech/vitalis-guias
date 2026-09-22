"""Leitura da observação livre da recepção.

É o único lugar onde entra IA. A regra continua sendo código: a IA só transforma
"Autorizado por telefone, protocolo 771203, aguardando número" em
{"intencao": "protocolo_verbal", "protocolo": "771203"}.

Ordem: cache no banco -> OpenAI (se tiver chave) -> palavra-chave (sempre funciona).
Se a API cair, o fallback assume e nada quebra.
"""
from __future__ import annotations

import json
import logging
import re

from app import config, db

log = logging.getLogger("vitalis.observacao")

INTENCOES = {
    "nova_autorizacao": "paciente trouxe/tem autorização nova que ainda não foi lançada",
    "protocolo_verbal": "autorização foi dada por telefone/verbal com número de protocolo, aguardando número oficial",
    "faturar_particular": "paciente pediu pra não usar o convênio, cobrar como particular",
    "codigo_errado": "o procedimento realizado é diferente do lançado, precisa trocar o código",
    "remarcacao": "sessão foi remarcada de outra data, autorização era da data original",
    "reembolso": "paciente pediu recibo pra pedir reembolso ao plano",
    "sem_acao": "nada que mude a guia (atraso, confirmação, exame anexado, comentário geral)",
}

# Fallback determinístico. Ordem importa: o primeiro que bater ganha.
PALAVRAS_CHAVE = [
    ("protocolo_verbal", r"protocolo|por telefone|verbal|aguardando n[uú]mero"),
    ("nova_autorizacao", r"autoriza[cç][aã]o nova|nova autoriza[cç][aã]o|trouxe autoriza"),
    ("faturar_particular", r"particular|n[aã]o quer usar o conv[eê]nio"),
    ("codigo_errado", r"c[oó]digo (certo|errado|correto)|procedimento realizado|lan[cç]ar o c[oó]digo"),
    ("remarcacao", r"remarcad|remarca[cç][aã]o|data original"),
    ("reembolso", r"reembolso"),
]


def _detalhes_por_regex(texto: str) -> dict:
    d = {}
    m = re.search(r"protocolo\s*(\d+)", texto, re.I)
    if m:
        d["protocolo"] = m.group(1)
    m = re.search(r"validade\s*(\d{1,2}/\d{1,2}(?:/\d{2,4})?)", texto, re.I)
    if m:
        d["validade_informada"] = m.group(1)
    m = re.search(r"realizado foi ([^,.]+)", texto, re.I)
    if m:
        d["procedimento_realizado"] = m.group(1).strip()
    return d


def por_palavra_chave(texto: str) -> dict:
    t = texto.lower()
    for intencao, padrao in PALAVRAS_CHAVE:
        if re.search(padrao, t):
            return {"intencao": intencao, "fonte": "palavra_chave", "detalhes": _detalhes_por_regex(texto)}
    return {"intencao": "sem_acao", "fonte": "palavra_chave", "detalhes": {}}


PROMPT = """Você lê a observação livre que uma recepcionista de clínica de fisioterapia escreveu ao lançar uma guia de convênio.
Classifique em UMA intenção e extraia detalhes. Responda só JSON, no formato:
{"intencao": "<uma das opções>", "protocolo": "<número ou null>", "validade_informada": "<data como escrita ou null>", "procedimento_realizado": "<texto ou null>", "confianca": <0 a 1>}

Intenções possíveis:
""" + "\n".join(f"- {k}: {v}" for k, v in INTENCOES.items()) + """

Regras: se não tiver certeza, use "sem_acao". Não invente detalhes que não estão no texto."""


def por_ia(texto: str) -> dict | None:
    if not config.OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        cliente = OpenAI(api_key=config.OPENAI_API_KEY, timeout=15)
        resp = cliente.chat.completions.create(
            model=config.OPENAI_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": PROMPT},
                      {"role": "user", "content": f"Observação: {texto}"}],
        )
        dados = json.loads(resp.choices[0].message.content or "{}")
        intencao = dados.get("intencao")
        if intencao not in INTENCOES:
            return None
        detalhes = {k: v for k, v in dados.items() if k != "intencao" and v not in (None, "", "null")}
        return {"intencao": intencao, "fonte": "llm", "detalhes": detalhes}
    except Exception as exc:  # API fora, chave inválida, JSON quebrado: cai no fallback
        log.warning("IA indisponível pra observação, usando palavra-chave: %s", exc)
        return None


def classificar(texto: str, usar_cache: bool = True) -> dict:
    texto = (texto or "").strip()
    if not texto:
        return {"intencao": "sem_acao", "fonte": "vazio", "detalhes": {}}
    chave = texto[:500]
    if usar_cache:
        try:
            cache = db.buscar_observacao(chave)
        except Exception as exc:
            log.warning("cache de observação indisponível: %s", exc)
            cache = None
        if cache:
            return {"intencao": cache["intencao"], "fonte": cache["fonte"],
                    "detalhes": json.loads(cache["detalhes"] or "{}")}
    res = por_ia(texto) or por_palavra_chave(texto)
    if usar_cache:
        try:
            db.guardar_observacao(chave, res["intencao"], res["fonte"], res["detalhes"])
        except Exception as exc:
            log.warning("não consegui gravar cache de observação: %s", exc)
    return res
