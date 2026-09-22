"""Os números da terça: o que o Dr. Renato vê. Tudo sai de consultas simples nas tabelas guias e achados."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date

from sqlalchemy import select

from app import db

COM_PROBLEMA = ("bloqueada", "pendente", "corrigir")
ORDEM = {"bloqueada": 0, "pendente": 1, "corrigir": 2, "atencao": 3, "ok": 4}

ROTULO = {
    "AUTORIZACAO_VENCIDA": "Autorização vencida",
    "AUTORIZACAO_VERBAL_PENDENTE": "Autorização verbal aguardando número",
    "AUTORIZACAO_VERBAL_VENCIDA": "Autorização verbal fora do prazo",
    "SESSAO_EXCEDE_LIMITE": "Sessão acima do limite da autorização",
    "PROCEDIMENTO_NAO_COBERTO": "Procedimento não coberto pelo convênio",
    "PROCEDIMENTO_DESCONHECIDO": "Código de procedimento desconhecido",
    "CAMPO_OBRIGATORIO_AUSENTE": "Campo obrigatório vazio",
    "REGISTRO_INCOMPATIVEL": "Profissional incompatível com o procedimento",
    "REGISTRO_FORMATO": "Registro profissional fora do padrão",
    "GUIA_DUPLICADA": "Guia duplicada",
    "OBS_FATURAR_PARTICULAR": "Paciente pediu particular (observação)",
    "OBS_CODIGO_ERRADO": "Código errado (observação)",
    "OBS_REMARCACAO": "Sessão remarcada (observação)",
    "OBS_REEMBOLSO": "Pediu recibo pra reembolso (observação)",
    "OBS_NOVA_AUTORIZACAO": "Autorização nova anotada (observação)",
    "FORMATO": "Formato de data ou valor",
    "CAMPO_ILEGIVEL": "Campo ilegível",
    "VALOR_DIVERGE": "Valor diferente da referência",
    "VALOR_AUSENTE": "Sem valor",
    "PRAZO_ENVIO_VENCIDO": "Prazo de envio vencido",
    "PRAZO_ENVIO_PROXIMO": "Prazo de envio próximo",
    "CONVENIO_DESCONHECIDO": "Convênio desconhecido",
    "LIMITE_SESSOES_DIVERGE": "Limite de sessões diverge da regra",
    "LANCAMENTO_ANTES_DO_ATENDIMENTO": "Lançada antes do atendimento",
    "SESSAO_AUSENTE": "Sessão sem número",
    "DESCRICAO_DIVERGE": "Descrição não bate com o código",
    "ERRO_INTERNO_REGRA": "Erro interno numa regra",
}


def rotulo(codigo: str) -> str:
    return ROTULO.get(codigo, codigo.replace("_", " ").capitalize())


def _carregar(desde: date | None, ate: date | None) -> list[dict]:
    """Filtra pela data da conferência (data_referencia), que é o dia do lançamento da guia."""
    q = select(db.guias)
    if desde:
        q = q.where(db.guias.c.data_referencia >= desde)
    if ate:
        q = q.where(db.guias.c.data_referencia <= ate)
    with db.engine().connect() as cx:
        linhas = [dict(r) for r in cx.execute(q).mappings().all()]
    for l in linhas:
        l["achados"] = json.loads(l.get("achados") or "[]")
        l.pop("dados_brutos", None)  # pesado e não entra no relatório; fica na página da guia
    return linhas


def gerar(desde: date | None = None, ate: date | None = None, hoje: date | None = None) -> dict:
    """Sem filtro = tudo que está no banco. O n8n de terça passa desde = 7 dias atrás."""
    hoje = hoje or date.today()
    guias = _carregar(desde, ate)
    total = len(guias)
    por_status = defaultdict(int)
    por_tipo, por_unidade, por_convenio = defaultdict(lambda: {"guias": 0, "valor_em_risco": 0.0}), {}, {}
    valor_total = risco = risco_bloqueadas = risco_corrigivel = 0.0
    datas = [g["data_referencia"] for g in guias if g.get("data_referencia")]

    for g in guias:
        por_status[g["status"]] += 1
        valor_total += g["valor"] or 0
        risco += g["valor_em_risco"] or 0
        if g["status"] == "bloqueada":
            risco_bloqueadas += g["valor_em_risco"] or 0
        elif g["status"] in ("corrigir", "pendente"):
            risco_corrigivel += g["valor_em_risco"] or 0
        vistos = set()
        for a in g["achados"]:
            if a["codigo"] in vistos:
                continue
            vistos.add(a["codigo"])
            por_tipo[a["codigo"]]["guias"] += 1
            if a["glosa_provavel"]:
                por_tipo[a["codigo"]]["valor_em_risco"] += g["valor"] or 0
        for chave, dic in (("unidade", por_unidade), ("convenio", por_convenio)):
            k = g[chave] or "?"
            d = dic.setdefault(k, {"guias": 0, "com_problema": 0, "valor_em_risco": 0.0})
            d["guias"] += 1
            d["com_problema"] += g["status"] in COM_PROBLEMA
            d["valor_em_risco"] += g["valor_em_risco"] or 0

    com_problema = sum(por_status[s] for s in COM_PROBLEMA)
    tipos = sorted(({"codigo": c, "rotulo": rotulo(c), **v} for c, v in por_tipo.items()),
                   key=lambda t: (-t["valor_em_risco"], -t["guias"]))
    pendentes = sorted((g for g in guias if g["status"] != "ok"),
                       key=lambda g: (ORDEM.get(g["status"], 9), -(g["valor"] or 0), g["id_guia"]))
    for g in pendentes:
        # Prazo contado do dia da conferência (lançamento), não de hoje: a guia acabou de ser
        # lançada e ainda não foi enviada. A data absoluta vai junto pra quem abrir depois.
        vence, ref = g.get("prazo_envio_vence_em"), g.get("data_referencia")
        g["dias_para_enviar"] = (vence - ref).days if vence and ref else None

    rel = {
        "gerado_em": hoje.isoformat(),
        "periodo": {"desde": desde.isoformat() if desde else None, "ate": ate.isoformat() if ate else None,
                    "primeira_conferencia": min(datas).isoformat() if datas else None,
                    "ultima_conferencia": max(datas).isoformat() if datas else None},
        "verificadas": total,
        "com_problema": com_problema,
        "pct_com_problema": round(100 * com_problema / total, 1) if total else 0.0,
        "por_status": dict(por_status),
        "valor_total": round(valor_total, 2),
        "valor_em_risco": round(risco, 2),
        "valor_em_risco_bloqueadas": round(risco_bloqueadas, 2),
        "valor_em_risco_corrigivel": round(risco_corrigivel, 2),
        "por_tipo": tipos,
        "por_unidade": dict(sorted(por_unidade.items())),
        "por_convenio": dict(sorted(por_convenio.items())),
        "pendentes": pendentes,
    }
    rel["mensagem_whatsapp"] = mensagem_whatsapp(rel)
    rel["mensagem_pendencias"] = mensagem_pendencias(rel)
    return rel


def brl(v: float | None) -> str:
    v = v or 0.0
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _ddmm(iso: str | None) -> str:
    return f"{iso[8:10]}/{iso[5:7]}" if iso else "?"


def mensagem_whatsapp(rel: dict) -> str:
    """Resumo de terça pro Dr. Renato. O n8n só repassa este texto."""
    ps, per = rel["por_status"], rel["periodo"]
    if not rel["verificadas"]:
        return (f"*Guias de convênio, {_ddmm(rel['gerado_em'])}*\n"
                "Nenhuma guia conferida no período.")
    linhas = [
        f"*Guias de convênio, {_ddmm(rel['gerado_em'])}*",
        f"Conferidas: {rel['verificadas']} (lançadas de {_ddmm(per['primeira_conferencia'])} "
        f"a {_ddmm(per['ultima_conferencia'])})",
        f"Com problema: {rel['com_problema']} ({str(rel['pct_com_problema']).replace('.', ',')}%)",
        f"Em risco: {brl(rel['valor_em_risco'])} de {brl(rel['valor_total'])}",
        f"  travado (bloqueadas): {brl(rel['valor_em_risco_bloqueadas'])}",
        f"  recuperável (corrigir/pendente): {brl(rel['valor_em_risco_corrigivel'])}",
        "",
        f"Bloqueadas {ps.get('bloqueada', 0)} · Pendentes {ps.get('pendente', 0)} · "
        f"Corrigir {ps.get('corrigir', 0)} · Atenção {ps.get('atencao', 0)} · OK {ps.get('ok', 0)}",
        "",
        "*Principais problemas:*",
    ]
    for t in [t for t in rel["por_tipo"] if t["valor_em_risco"] > 0][:5]:
        linhas.append(f"- {t['rotulo']}: {t['guias']} guia(s), {brl(t['valor_em_risco'])}")
    linhas.append("")
    linhas.append("*Por unidade:*")
    for u, d in rel["por_unidade"].items():
        linhas.append(f"- {u}: {d['com_problema']} de {d['guias']} com problema, {brl(d['valor_em_risco'])}")
    return "\n".join(linhas)


def mensagem_pendencias(rel: dict, limite: int = 15) -> str:
    """Lista de trabalho pra Carla e a recepção: o que resolver antes de enviar, por unidade."""
    fila = [g for g in rel["pendentes"] if g["status"] in COM_PROBLEMA]
    if not fila:
        return "*Guias pra resolver antes do envio*\nNada pendente. Pode enviar tudo."
    linhas = [f"*Guias pra resolver antes do envio: {len(fila)}*",
              f"Em jogo: {brl(sum(g['valor_em_risco'] or 0 for g in fila))}"]
    por_unidade: dict[str, list] = {}
    for g in fila:
        por_unidade.setdefault(g["unidade"] or "?", []).append(g)
    mostradas = 0
    for unidade, gs in sorted(por_unidade.items()):
        linhas.append("")
        linhas.append(f"*{unidade}* ({len(gs)})")
        for g in gs:
            if mostradas >= limite:
                break
            principal = next((a for a in g["achados"] if a["severidade"] in ("bloqueia", "pendente", "corrigir")),
                             g["achados"][0] if g["achados"] else None)
            acao = principal["acao"] if principal else ""
            linhas.append(f"- {g['id_guia']} {g['convenio']} {brl(g['valor'])} ({g['status']}): {acao}")
            mostradas += 1
    if len(fila) > mostradas:
        linhas.append("")
        linhas.append(f"...e mais {len(fila) - mostradas}. Lista completa no painel.")
    return "\n".join(linhas)


def mensagem_guia(res: dict) -> str:
    """Alerta de uma guia só, pra recepção da unidade na hora do lançamento."""
    g = res["guia"]
    titulo = {"bloqueada": "NÃO ENVIAR", "pendente": "AGUARDANDO", "corrigir": "CORRIGIR ANTES DE ENVIAR",
              "atencao": "CONFERIR", "ok": "OK"}.get(res["status"], res["status"].upper())
    linhas = [f"*{titulo}: {g['id_guia']}*",
              f"{g['unidade']} · {g['convenio']} · paciente {g['paciente']} · {brl(g['valor'])}"]
    peso = {"bloqueia": 0, "pendente": 1, "corrigir": 2, "atencao": 3}
    for a in sorted(res["achados"], key=lambda a: peso.get(a["severidade"], 9)):  # o mais grave primeiro
        if a["severidade"] == "atencao" and res["status"] != "atencao":
            continue
        linhas.append(f"- {rotulo(a['codigo'])}: {a['acao']}")
    return "\n".join(linhas)
