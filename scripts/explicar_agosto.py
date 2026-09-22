"""Gera docs/agosto_guia_a_guia.md: onde cada uma das 80 guias caiu e por quê.

Roda o motor de verdade (sem IA, só o fallback, pra ser reproduzível) num banco em memória.
Uso: python scripts/explicar_agosto.py
"""
import csv
import os
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ["OPENAI_API_KEY"] = ""

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import config, db  # noqa: E402

config.OPENAI_API_KEY = ""
db.usar_engine(create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))

from app.relatorio import brl, rotulo  # noqa: E402
from app.validador import motor  # noqa: E402

ORDEM = {"bloqueada": 0, "pendente": 1, "corrigir": 2, "atencao": 3, "ok": 4}
TITULO = {"bloqueada": "Bloqueadas: não podem ir do jeito que estão",
          "pendente": "Pendente: esperando algo com prazo",
          "corrigir": "Corrigir: erro simples, conserta e envia",
          "atencao": "Atenção: podem ir, mas alguém deveria olhar",
          "ok": "OK: podem ir"}

linhas = list(csv.DictReader(open(RAIZ / "dados" / "guias_agosto.csv", encoding="utf-8")))
res = motor.registrar_lote(linhas)["resultados"]
res.sort(key=lambda x: (ORDEM[x["status"]], x["guia"]["id_guia"]))
cont = Counter(x["status"] for x in res)
risco = sum(x["valor_em_risco"] for x in res)
total = sum(x["guia"]["valor"] or 0 for x in res)

out = ["# Agosto, guia a guia",
       "",
       "Gerado por `scripts/explicar_agosto.py` rodando o motor de verdade (sem IA, só o fallback por "
       "palavra-chave, pra ser reproduzível). Conferência no dia do lançamento de cada guia.",
       "",
       f"**{len(res)} guias · {brl(total)} lançados · {brl(risco)} em risco ({100 * risco / total:.0f}% do lançado)**",
       "",
       " · ".join(f"{s}: {cont.get(s, 0)}" for s in ORDEM),
       "",
       "Nas bloqueadas, pendente e corrigir, cada achado mostra o que está errado e a ação. "
       "A observação da recepção aparece com a intenção que foi lida dela.",
       ""]
atual = None
for x in res:
    g, st = x["guia"], x["status"]
    if st != atual:
        atual = st
        out += ["", f"## {TITULO[st]} ({cont[st]})", ""]
        if st == "ok":
            out.append(", ".join(y["guia"]["id_guia"] for y in res if y["status"] == "ok"))
            break
    cab = (f"**{g['id_guia']}** · {g['unidade']} · {g['convenio']} · {g['procedimento_descricao']} · "
           f"sessão {g['sessao_numero']} · {brl(g['valor'])}")
    if x["valor_em_risco"]:
        cab += f" · **{brl(x['valor_em_risco'])} em risco**"
    out.append(f"- {cab}")
    if g["observacao_recepcao"]:
        out.append(f"  - Observação da recepção: \"{g['observacao_recepcao']}\" → lida como `{x['obs']['intencao']}`")
    for a in x["achados"]:
        out.append(f"  - {rotulo(a['codigo'])} ({a['severidade']}): {a['mensagem']} → {a['acao']}")

destino = RAIZ / "docs" / "agosto_guia_a_guia.md"
destino.parent.mkdir(exist_ok=True)
destino.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"ok: {destino.relative_to(RAIZ)} ({len(res)} guias)")
