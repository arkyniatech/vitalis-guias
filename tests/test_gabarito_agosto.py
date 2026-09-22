"""As 80 guias de agosto contra o gabarito revisado à mão.

Se uma regra mudar e uma guia cair em outro lugar, este teste aponta qual.
Referência de data = data de lançamento de cada guia: a guia acabou de ser lançada e ainda
não foi enviada (esclarecimento 2 da Expert). É o padrão, ninguém precisa passar parâmetro.
"""
import csv
import json
import random
from pathlib import Path

from app.validador import motor

RAIZ = Path(__file__).resolve().parent.parent


def _carregar():
    linhas = list(csv.DictReader(open(RAIZ / "dados" / "guias_agosto.csv", encoding="utf-8")))
    gabarito = json.loads((RAIZ / "tests" / "gabarito_agosto.json").read_text(encoding="utf-8"))
    return linhas, gabarito


def _compara(resultados, gabarito):
    diferencas = []
    for x in resultados:
        gid = x["guia"]["id_guia"]
        esperado = gabarito[gid]
        obtido = {"status": x["status"], "codigos": sorted(a["codigo"] for a in x["achados"])}
        if obtido["status"] != esperado["status"] or obtido["codigos"] != esperado["codigos"]:
            diferencas.append((gid, esperado, obtido))
    return diferencas


def test_todas_as_guias_batem_com_o_gabarito():
    linhas, gabarito = _carregar()
    r = motor.registrar_lote(linhas)
    assert r["com_erro_de_leitura"] == 0
    assert r["verificadas"] == 80
    diferencas = _compara(r["resultados"], gabarito)
    assert not diferencas, "\n".join(f"{g}: esperado {e} obtido {o}" for g, e, o in diferencas)


def test_totais_de_agosto():
    linhas, _ = _carregar()
    r = motor.registrar_lote(linhas)
    status = {}
    for x in r["resultados"]:
        status[x["status"]] = status.get(x["status"], 0) + 1
    assert status == {"ok": 36, "bloqueada": 32, "corrigir": 6, "pendente": 1, "atencao": 5}
    assert round(sum(x["valor_em_risco"] for x in r["resultados"]), 2) == 2642.0


def test_casos_que_so_a_observacao_revela():
    linhas, _ = _carregar()
    r = {x["guia"]["id_guia"]: x for x in motor.registrar_lote(linhas)["resultados"]}
    codigos = lambda gid: {a["codigo"] for a in r[gid]["achados"]}
    assert "OBS_FATURAR_PARTICULAR" in codigos("G-2608-0039")
    assert "OBS_CODIGO_ERRADO" in codigos("G-2608-0069")
    assert r["G-2608-0041"]["status"] == "pendente"           # protocolo verbal dentro dos 5 dias úteis
    assert r["G-2608-0030"]["status"] == "corrigir"           # vencida, mas paciente trouxe autorização nova
    assert r["G-2608-0034"]["status"] == "atencao"            # remarcada, autorização ainda cobre


def test_duplicadas():
    linhas, _ = _carregar()
    r = {x["guia"]["id_guia"]: x for x in motor.registrar_lote(linhas)["resultados"]}
    dup = [a for a in r["G-2608-0057"]["achados"] if a["codigo"] == "GUIA_DUPLICADA"]
    assert dup and dup[0]["dados"]["duplicada_de"] == "G-2608-0027"
    dup = [a for a in r["G-2608-0076"]["achados"] if a["codigo"] == "GUIA_DUPLICADA"]
    assert dup and dup[0]["dados"]["duplicada_de"] == "G-2608-0059"
    # as originais não são marcadas
    assert not any(a["codigo"] == "GUIA_DUPLICADA" for a in r["G-2608-0027"]["achados"])
    assert r["G-2608-0059"]["status"] == "ok"
    # G-0060 e G-0017: mesmo código de paciente, mas carteirinha, unidade e autorização diferentes
    assert r["G-2608-0060"]["status"] == "ok"


def test_resultado_nao_depende_da_ordem_nem_de_reenvio():
    linhas, gabarito = _carregar()
    motor.registrar_lote(linhas)
    assert not _compara(motor.registrar_lote(linhas)["resultados"], gabarito)          # reenvio
    assert not _compara(motor.registrar_lote(list(reversed(linhas)))["resultados"], gabarito)
    embaralhadas = linhas[:]
    random.Random(42).shuffle(embaralhadas)
    assert not _compara(motor.registrar_lote(embaralhadas)["resultados"], gabarito)


def test_invertido_em_banco_vazio():
    linhas, gabarito = _carregar()
    r = motor.registrar_lote(list(reversed(linhas)))
    assert not _compara(r["resultados"], gabarito)


def test_registro_sugerido_a_partir_de_outras_guias():
    linhas, _ = _carregar()
    r = {x["guia"]["id_guia"]: x for x in motor.registrar_lote(linhas)["resultados"]}
    a = [a for a in r["G-2608-0013"]["achados"] if a["codigo"] == "CAMPO_OBRIGATORIO_AUSENTE"][0]
    assert a["severidade"] == "corrigir"
    assert a["dados"]["sugestao"] == "CRM-SP 84512"
