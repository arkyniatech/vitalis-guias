"""A API de ponta a ponta: chave, guia nova, lote em CSV, relatório e dashboard."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

RAIZ = Path(__file__).resolve().parent.parent
CHAVE = {"X-API-Key": "chave-de-teste"}

GUIA = {
    "id_guia": "API-1", "unidade": "Norte", "data_atendimento": "2026-09-15", "paciente": "P-77",
    "convenio": "Vitalcard", "carteirinha": "999999999", "cid": "", "procedimento_codigo": "50000470",
    "procedimento_descricao": "Sessão de fisioterapia musculoesquelética", "numero_autorizacao": "AUT7",
    "autorizacao_validade": "2026-09-30", "autorizacao_sessoes_limite": "10", "sessao_numero_na_autorizacao": "2",
    "profissional": "Ana", "profissional_registro": "CREFITO-3 1-F", "valor": "62.00",
    "observacao_recepcao": "", "data_lancamento": "2026-09-15",
}


def test_sem_chave_recusa():
    c = TestClient(app)
    assert c.post("/guias", json=GUIA).status_code == 401
    assert c.post("/guias", json=GUIA, headers={"X-API-Key": "errada"}).status_code == 401


def test_guia_nova_entra_e_volta_com_o_diagnostico():
    c = TestClient(app)
    r = c.post("/guias?data_referencia=2026-09-16", json=GUIA, headers=CHAVE)
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "bloqueada"
    assert any(a["codigo"] == "CAMPO_OBRIGATORIO_AUSENTE" and a["campo"] == "cid" for a in d["achados"])
    # aparece no dashboard e no relatório
    assert c.get("/guias/API-1").status_code == 200
    rel = c.get("/relatorio?desde=2026-09-01").json()
    assert rel["verificadas"] == 1 and rel["com_problema"] == 1 and rel["valor_em_risco"] == 62.0
    assert "mensagem_whatsapp" in rel


def test_corpo_invalido_e_sem_id():
    c = TestClient(app)
    assert c.post("/guias", content="isso não é json", headers=CHAVE).status_code == 422
    assert c.post("/guias", json={"convenio": "Vitalcard"}, headers=CHAVE).status_code == 422
    assert c.post("/guias", json="texto", headers=CHAVE).status_code == 422


def test_lote_csv_com_linha_ruim_nao_derruba_o_resto():
    c = TestClient(app)
    csv_bom = (RAIZ / "dados" / "guias_agosto.csv").read_text(encoding="utf-8")
    csv_ruim = csv_bom + ",Sul,2026-08-30,P-1,Vitalcard,1,,50000470,,,,,,,,62.00,,2026-08-30\n"  # sem id_guia
    r = c.post("/guias/lote", files={"arquivo": ("guias.csv", csv_ruim, "text/csv")}, headers=CHAVE)
    assert r.status_code == 200
    d = r.json()
    assert d["verificadas"] == 80 and d["com_erro_de_leitura"] == 1
    assert d["erros"][0]["linha"] == 81
    assert c.get("/").status_code == 200


def test_lote_sem_cabecalho_certo():
    c = TestClient(app)
    r = c.post("/guias/lote", files={"arquivo": ("x.csv", "a,b\n1,2\n", "text/csv")}, headers=CHAVE)
    assert r.status_code == 422


def test_saude_e_regras():
    c = TestClient(app)
    assert c.get("/saude").json()["banco"] == "ok"
    assert set(c.get("/regras").json()["convenios"]) == {"Vitalcard", "Saúde Interior", "Plano Bem"}


def test_guia_de_agosto_pela_api_sem_parametro_bate_com_o_lote():
    """O avaliador manda uma guia nova do jeito que ela vem do sistema. Sem parâmetro nenhum,
    o resultado tem que ser o mesmo que ela teve no lote (conferência no dia do lançamento)."""
    import csv
    import json
    c = TestClient(app)
    linhas = list(csv.DictReader(open(RAIZ / "dados" / "guias_agosto.csv", encoding="utf-8")))
    gabarito = json.loads((RAIZ / "tests" / "gabarito_agosto.json").read_text(encoding="utf-8"))
    for linha in linhas:                                   # uma por uma, como chegariam do n8n
        r = c.post("/guias", json=linha, headers=CHAVE)
        assert r.status_code == 200, linha["id_guia"]
    rel = c.get("/relatorio").json()
    por_id = {g["id_guia"]: g for g in rel["pendentes"]}
    for gid, esperado in gabarito.items():
        obtido = por_id.get(gid, {"status": "ok"})["status"]
        assert obtido == esperado["status"], (gid, esperado["status"], obtido)
    assert rel["valor_em_risco"] == 2642.0


def test_resposta_traz_mensagem_pronta_pro_whatsapp():
    c = TestClient(app)
    linha = {**GUIA, "id_guia": "API-MSG", "cid": "M54.5", "sessao_numero_na_autorizacao": "11"}
    d = c.post("/guias", json=linha, headers=CHAVE).json()
    assert d["status"] == "bloqueada"
    assert d["mensagem"].startswith("*NÃO ENVIAR: API-MSG*")
    assert "Sessão acima do limite" in d["mensagem"]
    assert d["data_referencia"] == "2026-09-15"           # data de lançamento da guia


def test_relatorio_traz_as_duas_mensagens():
    c = TestClient(app)
    c.post("/guias", json=GUIA, headers=CHAVE)
    rel = c.get("/relatorio").json()
    assert rel["mensagem_whatsapp"].startswith("*Guias de convênio")
    assert rel["mensagem_pendencias"].startswith("*Guias pra resolver antes do envio: 1*")


def test_data_referencia_invalida():
    c = TestClient(app)
    assert c.post("/guias?data_referencia=ontem", json=GUIA, headers=CHAVE).status_code == 422


def test_cancelar_guia_tira_do_painel():
    c = TestClient(app)
    c.post("/guias", json=GUIA, headers=CHAVE)
    assert c.delete("/guias/API-1").status_code == 401
    assert c.delete("/guias/API-1", headers=CHAVE).json() == {"cancelada": True, "id_guia": "API-1"}
    assert c.get("/relatorio").json()["verificadas"] == 0
    assert c.delete("/guias/API-1", headers=CHAVE).status_code == 404


def test_paginas_de_regras_e_integracao():
    c = TestClient(app)
    c.post("/guias", json=GUIA, headers=CHAVE)
    regras = c.get("/convenios").text
    assert all(n in regras for n in ("Vitalcard", "Saúde Interior", "Plano Bem", "5 dias úteis"))
    integ = c.get("/integracao").text
    assert "<b>Guias de convênio" in integ and "/guias/lote" in integ


def test_importar_pela_tela():
    c = TestClient(app)
    assert c.get("/importar").status_code == 200
    csv_ok = (RAIZ / "dados" / "guias_agosto.csv").read_bytes()
    r = c.post("/importar/csv", files={"arquivo": ("agosto.csv", csv_ok, "text/csv")})
    assert r.status_code == 200 and "80 guias conferidas" in r.text
    assert c.get("/relatorio").json()["com_problema"] == 39
    guia = dict(GUIA, id_guia="TELA-1", procedimento_descricao="")
    r = c.post("/importar/guia", data=guia)
    assert "PENDENTE" in r.text and "CID" in r.text
    # POST vindo de outro site é recusado
    assert c.post("/importar/guia", data=guia, headers={"origin": "https://outro.site"}).status_code == 403
