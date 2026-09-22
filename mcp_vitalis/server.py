"""MCP da Clínica Vitalis: as regras dos convênios e as guias de agosto, pra qualquer cliente MCP.

Fonte dos dados: dados/regras_convenio.json e dados/guias_agosto.csv, lidos direto do repositório.
Na subida, as 80 guias vão pra um SQLite em memória (nada é gravado em disco nem no banco de produção).
É o mesmo motor de regras do app: a decisão que sai aqui é a mesma que sai no painel.

Ferramentas:
  consultar_regra        o que um convênio exige pra um procedimento
  verificar_guia         confere uma guia e devolve a decisão, o motivo e o que corrigir
  buscar_guia            uma guia de agosto pelo id, com a conferência
  listar_convenios       convênios e procedimentos conhecidos (pra traduzir o que a recepção escreve)
  relatorio_da_semana    os números do Dr. Renato num período
"""
from __future__ import annotations

import csv
import logging
import os
import sys
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# Sem banco externo e sem segredo: o MCP é autocontido. IA só se VITALIS_MCP_IA=1 e houver chave.
os.environ["DATABASE_URL"] = "sqlite://"
if os.getenv("VITALIS_MCP_IA") != "1":
    os.environ["OPENAI_API_KEY"] = ""

from mcp.server.mcpserver import MCPServer  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import config, db, relatorio  # noqa: E402
from app.validador import motor  # noqa: E402
from app.validador.regras_convenio import REGISTRO_POR_PROCEDIMENTO, carregar  # noqa: E402

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
log = logging.getLogger("vitalis.mcp")

GUIAS_CSV = Path(os.getenv("VITALIS_GUIAS_CSV") or RAIZ / "dados" / "guias_agosto.csv")

# O que a clínica precisa saber: pode mandar ou não. Os cinco status do motor viram duas respostas.
DECISAO = {"ok": "OK", "atencao": "OK", "bloqueada": "PENDENTE", "pendente": "PENDENTE", "corrigir": "PENDENTE"}
O_QUE_FAZER = {
    "ok": "Pode enviar ao convênio.",
    "atencao": "Pode enviar ao convênio. Tem um ponto pra alguém olhar, mas não trava.",
    "corrigir": "Corrigir no sistema antes de enviar. A informação existe, só foi lançada errado.",
    "pendente": "Segurar a guia até chegar o que falta (ex.: número da autorização verbal) dentro do prazo.",
    "bloqueada": "Não enviar assim: o convênio vai glosar. Precisa de documento novo ou de uma decisão.",
}


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower().strip()


def _carregar_agosto() -> int:
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    db.usar_engine(e)
    if not GUIAS_CSV.exists():
        log.warning("não achei %s; seguindo sem as guias de agosto", GUIAS_CSV)
        return 0
    with GUIAS_CSV.open(encoding="utf-8-sig") as f:
        linhas = list(csv.DictReader(f))
    return motor.registrar_lote(linhas, origem="lote")["verificadas"]


def _achar_convenio(nome: str):
    regras = carregar()
    alvo = _sem_acento(nome)
    for c in regras.convenios.values():
        if _sem_acento(c.nome) == alvo or alvo and alvo in _sem_acento(c.nome):
            return c
    return None


def _achar_procedimentos(texto: str) -> list[dict]:
    """Aceita o código (50000470) ou parte do nome ("infiltração", "consulta ortopédica")."""
    regras = carregar()
    t = (texto or "").strip()
    if t in regras.procedimentos:
        return [regras.procedimentos[t]]
    alvo = _sem_acento(t)
    return [p for p in regras.procedimentos.values() if alvo and alvo in _sem_acento(p["descricao"])]


def _explicar(res: dict) -> dict[str, Any]:
    g = res["guia"]
    peso = {"bloqueia": 0, "pendente": 1, "corrigir": 2, "atencao": 3}
    achados = sorted(res["achados"], key=lambda a: peso.get(a["severidade"], 9))
    return {
        "id_guia": g["id_guia"],
        "decisao": DECISAO[res["status"]],
        "status": res["status"],
        "o_que_fazer": O_QUE_FAZER[res["status"]],
        "vai_glosar_se_enviar_assim": res["glosa_provavel"],
        "valor_em_risco": res["valor_em_risco"],
        "motivos": [{"problema": relatorio.rotulo(a["codigo"]), "codigo": a["codigo"], "gravidade": a["severidade"],
                     "campo": a.get("campo") or "", "motivo": a["mensagem"], "corrigir": a.get("acao") or ""}
                    for a in achados],
        "observacao_lida_como": res["obs"].get("intencao"),
        "conferida_com_data_de": str(g["data_referencia"]),
        "prazo_envio_vence_em": str(g["prazo_envio_vence_em"]) if g.get("prazo_envio_vence_em") else None,
        "dias_para_enviar": ((g["prazo_envio_vence_em"] - g["data_referencia"]).days
                             if g.get("prazo_envio_vence_em") and g.get("data_referencia") else None),
        "mensagem_pronta": relatorio.mensagem_guia(res),
    }


mcp = MCPServer(
    name="vitalis-guias",
    title="Clínica Vitalis · conferência de guias",
    instructions=(
        "Confere guias de convênio da Clínica Vitalis antes do envio. A decisão vem das regras dos convênios "
        "(regras_convenio.json), nunca de palpite: use verificar_guia pra decidir e consultar_regra pra explicar. "
        "Datas podem vir como dd/mm/aaaa e valores com vírgula; o verificador trata."
    ),
)


@mcp.tool()
def consultar_regra(convenio: str, procedimento: str) -> dict:
    """Consulta o que um convênio exige pra um procedimento.

    Args:
        convenio: nome do convênio (Vitalcard, Saúde Interior, Plano Bem). Aceita sem acento.
        procedimento: código TUSS (ex. 50000470) ou parte da descrição (ex. "infiltração").

    Devolve se o convênio cobre, o valor de referência, o registro profissional exigido,
    os campos obrigatórios, validade da autorização, limite de sessões, prazo de envio e a
    observação do convênio.
    """
    regras = carregar()
    conv = _achar_convenio(convenio)
    if conv is None:
        return {"erro": f"Convênio '{convenio}' não existe nas regras.", "convenios": list(regras.convenios)}
    procs = _achar_procedimentos(procedimento)
    if not procs:
        return {"erro": f"Procedimento '{procedimento}' não encontrado.",
                "procedimentos": {c: p["descricao"] for c, p in regras.procedimentos.items()}}
    if len(procs) > 1:
        return {"erro": f"'{procedimento}' bate com mais de um procedimento. Diga qual.",
                "opcoes": {p["codigo"]: p["descricao"] for p in procs}}
    p = procs[0]
    cobre = p["codigo"] in conv.procedimentos_cobertos
    return {
        "convenio": conv.nome,
        "procedimento": {"codigo": p["codigo"], "descricao": p["descricao"]},
        "cobre": cobre,
        "resumo": (f"{conv.nome} {'cobre' if cobre else 'NÃO cobre'} {p['descricao']} ({p['codigo']})."
                   + ("" if cobre else " Se for enviada, o convênio glosa.")),
        "valor_referencia": p["valor_referencia"],
        "registro_profissional_exigido": REGISTRO_POR_PROCEDIMENTO.get(p["codigo"]),
        "campos_obrigatorios": list(conv.campos_obrigatorios),
        "validade_maxima_autorizacao_dias": conv.validade_maxima_autorizacao_dias,
        "limite_sessoes_por_autorizacao": conv.limite_sessoes_por_autorizacao,
        "prazo_envio_dias": conv.prazo_envio_dias,
        "aceita_autorizacao_verbal_dias_uteis": conv.aceita_autorizacao_verbal_dias_uteis,
        "observacao_do_convenio": conv.observacao,
        "versao_das_regras": regras.versao,
    }


@mcp.tool()
def verificar_guia(guia: dict[str, Any], data_referencia: str | None = None) -> dict:
    """Confere uma guia e devolve a decisão (OK ou PENDENTE), o motivo e o que corrigir.

    Args:
        guia: os campos da guia, com os nomes do CSV da clínica: id_guia, unidade, data_atendimento,
            paciente, convenio, carteirinha, cid, procedimento_codigo, procedimento_descricao,
            numero_autorizacao, autorizacao_validade, autorizacao_sessoes_limite,
            sessao_numero_na_autorizacao, profissional, profissional_registro, valor,
            observacao_recepcao, data_lancamento. Campo que a recepção não preencheu vai vazio ("").
            Não invente valor: campo vazio é justamente o que a conferência precisa ver.
        data_referencia: o "hoje" da conferência, AAAA-MM-DD. Padrão: a data de lançamento da guia
            (a conferência é no lançamento, antes do envio). "hoje" força a data de hoje.

    Nada é gravado: é só consulta. As guias de agosto servem de contexto (duplicata, registro do
    profissional que aparece em outras guias).
    """
    bruto = {k: ("" if v is None else str(v)) for k, v in (guia or {}).items()}
    bruto["id_guia"] = bruto.get("id_guia") or "GUIA-AVULSA"
    if not bruto.get("data_lancamento") and data_referencia is None:
        data_referencia = "hoje"
    ref: date | str | None = data_referencia
    if data_referencia and data_referencia not in ("hoje", "lancamento"):
        try:
            ref = date.fromisoformat(data_referencia)
        except ValueError:
            return {"erro": "data_referencia deve ser AAAA-MM-DD, 'hoje' ou 'lancamento'."}
    try:
        res = motor.verificar(bruto, ref, origem="mcp")
    except Exception as exc:
        log.exception("falha ao verificar %s", bruto.get("id_guia"))
        return {"erro": f"Não consegui verificar a guia: {exc}"}
    return _explicar(res)


@mcp.tool()
def buscar_guia(id_guia: str) -> dict:
    """Busca uma guia de agosto pelo id (ex. G-2608-0007) e devolve os dados e a conferência."""
    with db.engine().connect() as cx:
        g = cx.execute(select(db.guias).where(db.guias.c.id_guia == id_guia.strip().upper())).mappings().first()
    if not g:
        return {"erro": f"Guia {id_guia} não está entre as guias carregadas."}
    import json
    bruto = json.loads(g["dados_brutos"] or "{}")
    res = motor.verificar(bruto, g["data_referencia"], origem="lote")
    return {"dados_como_lancados": bruto, "conferencia": _explicar(res)}


@mcp.tool()
def listar_convenios() -> dict:
    """Lista os convênios e procedimentos das regras, pra traduzir o que a recepção escreveu."""
    regras = carregar()
    return {
        "versao_das_regras": regras.versao,
        "convenios": {c.nome: {"cobre": list(c.procedimentos_cobertos), "prazo_envio_dias": c.prazo_envio_dias}
                      for c in regras.convenios.values()},
        "procedimentos": {cod: {"descricao": p["descricao"], "valor_referencia": p["valor_referencia"],
                                "registro_exigido": REGISTRO_POR_PROCEDIMENTO.get(cod)}
                          for cod, p in regras.procedimentos.items()},
    }


@mcp.tool()
def relatorio_da_semana(desde: str | None = None, ate: str | None = None) -> dict:
    """Os números do Dr. Renato: verificadas, com problema, por tipo e dinheiro em risco.

    Args:
        desde / ate: AAAA-MM-DD, pela data de lançamento. Sem nada, pega todas as guias carregadas.
    """
    try:
        d = date.fromisoformat(desde) if desde else None
        a = date.fromisoformat(ate) if ate else None
    except ValueError:
        return {"erro": "Use datas AAAA-MM-DD."}
    rel = relatorio.gerar(d, a)
    return {k: rel[k] for k in ("verificadas", "com_problema", "pct_com_problema", "por_status", "valor_total",
                                 "valor_em_risco", "valor_em_risco_bloqueadas", "valor_em_risco_corrigivel",
                                 "por_tipo", "por_unidade", "por_convenio", "mensagem_whatsapp")}


def main() -> None:
    n = _carregar_agosto()
    log.warning("vitalis-guias MCP pronto: %s guias carregadas de %s (IA: %s)", n, GUIAS_CSV.name,
                "ligada" if config.OPENAI_API_KEY else "palavra-chave")
    mcp.run()


if __name__ == "__main__":
    main()
