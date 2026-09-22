"""Junta tudo: normaliza, lê a observação, roda as regras, decide status e dinheiro em risco."""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from app import db
from app.validador import observacao
from app.validador.normalizador import GuiaNormalizada, normalizar
from app.validador.regras import (ATENCAO, BLOQUEIA, CORRIGIR, PENDENTE, REGRAS_BASE, REGRAS_CONVENIO,
                                  Achado, Contexto)
from app.validador.regras_convenio import Regras, carregar

log = logging.getLogger("vitalis.motor")

ORDEM_STATUS = [BLOQUEIA, PENDENTE, CORRIGIR, ATENCAO]
STATUS_POR_SEVERIDADE = {BLOQUEIA: "bloqueada", PENDENTE: "pendente", CORRIGIR: "corrigir", ATENCAO: "atencao"}


def _status(achados: list[Achado]) -> str:
    sev = {a.severidade for a in achados}
    for s in ORDEM_STATUS:
        if s in sev:
            return STATUS_POR_SEVERIDADE[s]
    return "ok"


def _resolver_referencia(data_referencia: date | str | None, g: GuiaNormalizada) -> date:
    """Que dia é "hoje" pra esta conferência.

    Padrão (None ou 'lancamento'): o dia em que a recepção lançou a guia. A conferência acontece
    no lançamento, antes do envio, então é essa a data que vale pra prazo de envio e pra
    autorização verbal. Vale igual pro lote de agosto e pra guia nova que entra pela API.
    'hoje': força a data de hoje (útil pra reconferir guia antiga que ainda não foi enviada).
    Uma data: essa data. Guia sem data de lançamento cai em hoje.
    """
    if isinstance(data_referencia, date):
        return data_referencia
    if data_referencia == "hoje":
        return date.today()
    return g.data_lancamento or date.today()


def _linha_para_banco(g: GuiaNormalizada, origem: str, data_ref: date, status: str, glosa: bool,
                      risco: float, obs: dict, conv) -> dict:
    vence = None
    if conv is not None and g.data_atendimento:
        vence = g.data_atendimento + timedelta(days=conv.prazo_envio_dias)
    return {
        "prazo_envio_vence_em": vence,
        "id_guia": g.id_guia, "unidade": g.unidade, "data_atendimento": g.data_atendimento,
        "paciente": g.paciente, "convenio": g.convenio, "carteirinha": g.carteirinha, "cid": g.cid,
        "procedimento_codigo": g.procedimento_codigo, "procedimento_descricao": g.procedimento_descricao,
        "numero_autorizacao": g.numero_autorizacao, "autorizacao_validade": g.autorizacao_validade,
        "autorizacao_sessoes_limite": g.autorizacao_sessoes_limite, "sessao_numero": g.sessao_numero,
        "profissional": g.profissional, "profissional_registro": g.profissional_registro, "valor": g.valor,
        "observacao_recepcao": g.observacao_recepcao, "data_lancamento": g.data_lancamento,
        "origem": origem, "status": status, "glosa_provavel": 1 if glosa else 0, "valor_em_risco": risco,
        "obs_intencao": obs.get("intencao"), "obs_fonte": obs.get("fonte"), "data_referencia": data_ref,
    }


def verificar(bruto: dict, data_referencia: date | str | None = None, origem: str = "api",
              regras: Regras | None = None, guias_do_lote: list[dict] | None = None,
              usar_banco: bool = True) -> dict:
    """Verifica UMA guia. Não grava; quem chama decide (ver `registrar`)."""
    regras = regras or carregar()
    g = normalizar(bruto)
    if not g.id_guia:
        raise ValueError("guia sem id_guia")
    data_ref = _resolver_referencia(data_referencia, g)

    obs = observacao.classificar(g.observacao_recepcao, usar_cache=usar_banco)

    # Contexto de outras guias. Só serve pra duas coisas, e nenhuma muda o status sozinha:
    #  - achar a mesma guia lançada duas vezes (mesma carteirinha e mesmo atendimento declarado);
    #  - sugerir o registro do profissional na ação, quando ele aparece em outra guia.
    registros, mesmo_atendimento = set(), []
    if usar_banco:
        try:
            if g.campo_vazio("profissional_registro"):
                registros = db.registros_conhecidos(g.profissional)
            mesmo_atendimento = db.guias_mesmo_atendimento(g.carteirinha, g.data_atendimento, g.id_guia)
        except Exception as exc:
            log.warning("banco indisponível pro contexto da guia %s: %s", g.id_guia, exc)
    ids_vistos = {o.get("id_guia") for o in mesmo_atendimento}
    for outra in guias_do_lote or []:
        if outra.get("carteirinha") == g.carteirinha and outra.get("data_atendimento") == g.data_atendimento \
                and outra.get("id_guia") != g.id_guia and outra.get("id_guia") not in ids_vistos:
            mesmo_atendimento.append(outra)
        if g.campo_vazio("profissional_registro") and outra.get("profissional") == g.profissional \
                and outra.get("profissional_registro"):
            registros.add(outra["profissional_registro"])

    ctx = Contexto(data_referencia=data_ref, obs=obs, registros_conhecidos=registros,
                   guias_mesmo_atendimento=mesmo_atendimento)
    conv = regras.convenio(g.convenio)

    achados: list[Achado] = []
    for regra in REGRAS_BASE:
        achados += regra(g, conv, regras, ctx)
    if conv is not None:
        for regra in REGRAS_CONVENIO:
            try:
                achados += regra(g, conv, regras, ctx)
            except Exception as exc:  # uma regra quebrar não pode derrubar a conferência inteira
                log.exception("regra %s falhou na guia %s", regra.__name__, g.id_guia)
                achados.append(Achado("ERRO_INTERNO_REGRA", ATENCAO, False,
                                      f"A regra {regra.__name__} falhou: {exc}", "Avisar quem mantém o sistema."))

    status = _status(achados)
    glosa = any(a.glosa_provavel for a in achados)
    risco = round(g.valor or 0.0, 2) if glosa else 0.0
    return {
        "guia": _linha_para_banco(g, origem, data_ref, status, glosa, risco, obs, conv),
        "bruto": g.bruto,
        "achados": [a.dict() for a in achados],
        "status": status,
        "glosa_provavel": glosa,
        "valor_em_risco": risco,
        "obs": obs,
    }


def _reconferir_lancadas_depois(res: dict) -> dict[str, dict]:
    """Se chegou uma guia lançada ANTES de outra do mesmo atendimento que já estava no banco
    (sincronização atrasada, lote fora de ordem), a outra é que vira duplicata. Reconfere as
    guias do mesmo atendimento lançadas depois desta, com a data de referência que elas tinham.
    Assim o resultado não depende da ordem em que as guias chegam."""
    g = res["guia"]
    try:
        irmas = db.guias_mesmo_atendimento(g["carteirinha"], g["data_atendimento"], g["id_guia"])
    except Exception as exc:
        log.warning("não consegui buscar guias do mesmo atendimento de %s: %s", g["id_guia"], exc)
        return {}
    minha_ordem = (g.get("data_lancamento") or date.max, g["id_guia"])
    refeitas = {}
    for outra in irmas:
        if (outra.get("data_lancamento") or date.max, outra["id_guia"]) <= minha_ordem:
            continue
        bruto = json.loads(outra.get("dados_brutos") or "{}")
        if not bruto:
            continue
        novo = verificar(bruto, outra.get("data_referencia"), outra.get("origem") or "api")
        db.salvar_resultado(novo)
        refeitas[outra["id_guia"]] = novo
    return refeitas


def registrar(bruto: dict, data_referencia: date | str | None = None, origem: str = "api") -> dict:
    """Verifica e grava. É o que a API chama."""
    res = verificar(bruto, data_referencia, origem)
    db.salvar_resultado(res)
    _reconferir_lancadas_depois(res)
    return res


def registrar_lote(linhas: list[dict], data_referencia: date | str | None = None,
                   origem: str = "lote") -> dict:
    """Verifica uma lista. Uma linha ruim não derruba as outras."""
    regras = carregar()
    ok, erros, ja_vistas = [], [], []
    for i, bruto in enumerate(linhas, start=1):
        try:
            res = verificar(bruto, data_referencia, origem, regras=regras, guias_do_lote=ja_vistas)
            db.salvar_resultado(res)
            ok.append(res)
            ja_vistas.append(res["guia"])
            refeitas = _reconferir_lancadas_depois(res)
            if refeitas:  # atualiza o retorno do lote com o resultado novo das que mudaram
                ok = [refeitas.get(x["guia"]["id_guia"], x) for x in ok]
        except Exception as exc:
            log.exception("linha %s do lote falhou", i)
            erros.append({"linha": i, "id_guia": (bruto or {}).get("id_guia"), "erro": str(exc)})
    return {"verificadas": len(ok), "com_erro_de_leitura": len(erros), "erros": erros, "resultados": ok}
