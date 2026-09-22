"""Testes unitários das regras e da normalização, com guias inventadas."""
from datetime import date

from app.validador import motor
from app.validador.normalizador import ler_data, ler_valor, normalizar

BASE = {
    "id_guia": "T-1", "unidade": "Sul", "data_atendimento": "2026-09-10", "paciente": "P-9",
    "convenio": "Vitalcard", "carteirinha": "123456789", "cid": "M54.5",
    "procedimento_codigo": "50000470", "procedimento_descricao": "Sessão de fisioterapia musculoesquelética",
    "numero_autorizacao": "AUT1", "autorizacao_validade": "2026-09-30", "autorizacao_sessoes_limite": "10",
    "sessao_numero_na_autorizacao": "3", "profissional": "Ana", "profissional_registro": "CREFITO-3 1-F",
    "valor": "62.00", "observacao_recepcao": "", "data_lancamento": "2026-09-10",
}


def guia(**mudancas):
    g = dict(BASE)
    g.update(mudancas)
    return g


def codigos(res):
    return {a["codigo"] for a in res["achados"]}


def test_normalizacao_de_datas_e_valores():
    assert ler_data("2026-08-03") == (date(2026, 8, 3), False)
    assert ler_data("03/08/2026") == (date(2026, 8, 3), True)
    assert ler_data("não é data") == (None, True)
    assert ler_valor("62.00") == (62.0, False)
    assert ler_valor("62,00") == (62.0, True)
    assert ler_valor("R$ 1.300,00") == (1300.0, True)
    assert ler_valor("abc") == (None, True)
    g = normalizar(guia(data_atendimento="10/09/2026", valor="62,00", cid=" m54.5 "))
    assert g.data_atendimento == date(2026, 9, 10) and g.valor == 62.0 and g.cid == "M54.5"
    assert set(g.conversoes) == {"data_atendimento", "valor"}


def test_guia_certa_passa():
    res = motor.verificar(guia())
    assert res["status"] == "ok" and res["valor_em_risco"] == 0 and res["achados"] == []


def test_convenio_desconhecido_bloqueia_sem_quebrar():
    res = motor.verificar(guia(convenio="Unimed"), data_referencia=date(2026, 9, 11))
    assert res["status"] == "bloqueada" and "CONVENIO_DESCONHECIDO" in codigos(res)


def test_guia_sem_id_da_erro_claro():
    import pytest
    with pytest.raises(ValueError):
        motor.verificar(guia(id_guia=""))


def test_autorizacao_vencida_e_nova_autorizacao_na_observacao():
    v = motor.verificar(guia(autorizacao_validade="2026-09-01"), data_referencia=date(2026, 9, 11))
    assert v["status"] == "bloqueada" and v["valor_em_risco"] == 62.0
    n = motor.verificar(guia(autorizacao_validade="2026-09-01",
                             observacao_recepcao="Paciente trouxe autorização nova, validade 30/10."),
                        data_referencia=date(2026, 9, 11))
    assert n["status"] == "corrigir" and n["obs"]["intencao"] == "nova_autorizacao"


def test_protocolo_verbal_pendente_depois_vence():
    g = guia(convenio="Saúde Interior", numero_autorizacao="", cid="",
             observacao_recepcao="Autorizado por telefone, protocolo 55, aguardando número.")
    dentro = motor.verificar(g, data_referencia=date(2026, 9, 14))   # 2 dias úteis depois
    fora = motor.verificar(g, data_referencia=date(2026, 9, 25))     # bem depois dos 5 dias úteis
    assert dentro["status"] == "pendente" and "AUTORIZACAO_VERBAL_PENDENTE" in codigos(dentro)
    assert fora["status"] == "bloqueada" and "AUTORIZACAO_VERBAL_VENCIDA" in codigos(fora)
    # Plano Bem não aceita verbal: bloqueia direto
    pb = motor.verificar(guia(convenio="Plano Bem", numero_autorizacao="", autorizacao_sessoes_limite="12",
                              observacao_recepcao="Autorizado por telefone, protocolo 55."),
                         data_referencia=date(2026, 9, 11))
    assert pb["status"] == "bloqueada" and "CAMPO_OBRIGATORIO_AUSENTE" in codigos(pb)


def test_sessao_acima_do_limite_e_limite_divergente():
    res = motor.verificar(guia(sessao_numero_na_autorizacao="11", autorizacao_sessoes_limite="12"),
                          data_referencia=date(2026, 9, 11))
    assert {"SESSAO_EXCEDE_LIMITE", "LIMITE_SESSOES_DIVERGE"} <= codigos(res)


def test_procedimento_nao_coberto_manda_faturar_particular_no_plano_bem():
    res = motor.verificar(guia(convenio="Plano Bem", procedimento_codigo="20103301",
                               procedimento_descricao="Consulta ortopédica", valor="90.00",
                               profissional_registro="CRM-SP 1", autorizacao_sessoes_limite="12"),
                          data_referencia=date(2026, 9, 11))
    a = [a for a in res["achados"] if a["codigo"] == "PROCEDIMENTO_NAO_COBERTO"][0]
    assert "particular" in a["acao"].lower()


def test_registro_incompativel_e_valor_divergente():
    res = motor.verificar(guia(profissional_registro="CRM-SP 99", valor="70.00"), data_referencia=date(2026, 9, 11))
    assert {"REGISTRO_INCOMPATIVEL", "VALOR_DIVERGE"} <= codigos(res)


def test_prazo_de_envio():
    perto = motor.verificar(guia(), data_referencia=date(2026, 10, 8))    # vence 10/10
    vencido = motor.verificar(guia(), data_referencia=date(2026, 10, 20))
    assert "PRAZO_ENVIO_PROXIMO" in codigos(perto)
    assert vencido["status"] == "bloqueada" and "PRAZO_ENVIO_VENCIDO" in codigos(vencido)


def test_duplicata_contra_o_banco():
    motor.registrar(guia(id_guia="T-1"), data_referencia=date(2026, 9, 11))
    dup = motor.registrar(guia(id_guia="T-2"), data_referencia=date(2026, 9, 11))
    assert dup["status"] == "bloqueada"
    assert [a for a in dup["achados"] if a["codigo"] == "GUIA_DUPLICADA"][0]["dados"]["duplicada_de"] == "T-1"


def test_regravar_a_mesma_guia_nao_duplica_no_banco():
    motor.registrar(guia(id_guia="T-1"), data_referencia=date(2026, 9, 11))
    motor.registrar(guia(id_guia="T-1", sessao_numero_na_autorizacao="4"), data_referencia=date(2026, 9, 11))
    from app import relatorio
    rel = relatorio.gerar(date(2026, 9, 1), date(2026, 9, 30), hoje=date(2026, 9, 11))
    assert rel["verificadas"] == 1


# ------------------------------------------------------------ esclarecimentos da Expert

def test_referencia_padrao_e_a_data_de_lancamento():
    # esclarecimento 2: sem parâmetro, a conferência é no dia do lançamento, nunca "hoje"
    g = guia(convenio="Saúde Interior", numero_autorizacao="", cid="", data_atendimento="2026-08-20",
             autorizacao_validade="2026-09-14", autorizacao_sessoes_limite="20", data_lancamento="2026-08-21",
             observacao_recepcao="Autorizado por telefone, protocolo 771203, aguardando número.")
    padrao = motor.verificar(g)
    assert padrao["guia"]["data_referencia"] == date(2026, 8, 21)
    assert padrao["status"] == "pendente"
    # forçando uma data bem depois, a mesma guia vira verbal vencida e prazo de envio vencido
    depois = motor.verificar(g, data_referencia=date(2026, 10, 20))
    assert depois["status"] == "bloqueada"
    assert {"AUTORIZACAO_VERBAL_VENCIDA", "PRAZO_ENVIO_VENCIDO"} <= codigos(depois)
    assert motor.verificar(g, data_referencia="hoje")["guia"]["data_referencia"] == date.today()


def test_guia_sem_data_de_lancamento_usa_hoje():
    res = motor.verificar(guia(data_lancamento=""))
    assert res["guia"]["data_referencia"] == date.today()


def test_validade_longa_nao_e_problema():
    # esclarecimento 1: não existe data de concessão; só validade contra atendimento
    res = motor.verificar(guia(autorizacao_validade="2027-01-31"))
    assert res["status"] == "ok"


def test_validade_no_proprio_dia_do_atendimento_vale():
    res = motor.verificar(guia(autorizacao_validade="2026-09-10"))
    assert "AUTORIZACAO_VENCIDA" not in codigos(res)


def test_registro_vazio_e_corrigir_mesmo_sem_outras_guias():
    # esclarecimento 3: o status só depende do que a própria guia declara
    res = motor.verificar(guia(profissional_registro=""))
    assert res["status"] == "corrigir"
    a = [a for a in res["achados"] if a["campo"] == "profissional_registro"][0]
    assert "CREFITO" in a["acao"]


def test_mesmo_paciente_com_carteirinha_diferente_nao_e_duplicata():
    motor.registrar(guia(id_guia="T-1"))
    outra = motor.registrar(guia(id_guia="T-2", carteirinha="999999999"))
    assert outra["status"] == "ok"


def test_duplicata_marca_a_lancada_depois_mesmo_chegando_antes():
    tarde = motor.registrar(guia(id_guia="T-9", data_lancamento="2026-09-12"))
    assert tarde["status"] == "ok"                       # ainda não tem com quem comparar
    cedo = motor.registrar(guia(id_guia="T-5", data_lancamento="2026-09-10"))
    assert cedo["status"] == "ok"                        # a original
    from app import db
    from sqlalchemy import select
    with db.engine().connect() as cx:
        st = cx.execute(select(db.guias.c.status).where(db.guias.c.id_guia == "T-9")).scalar()
    assert st == "bloqueada"                             # foi reconferida e virou duplicata
