"""Leitura da observação: fallback por palavra-chave, caminho da IA (simulado) e cache."""
import json
import types

from app import config
from app.validador import observacao


def test_palavra_chave_cobre_os_casos_de_agosto():
    casos = {
        "Paciente trouxe autorização nova, número ainda não lançado. Validade 30/09.": "nova_autorizacao",
        "Autorizado por telefone, protocolo 771203, aguardando número.": "protocolo_verbal",
        "Paciente pediu para faturar como particular, não quer usar o convênio.": "faturar_particular",
        "Procedimento realizado foi drenagem linfática, lançar o código certo.": "codigo_errado",
        "Sessão remarcada de 12/08 para hoje, autorização era da data original.": "remarcacao",
        "Pediu recibo para reembolso do plano.": "reembolso",
        "Paciente chegou 10 min atrasado.": "sem_acao",
        "Confirmado pelo WhatsApp na véspera.": "sem_acao",
        "Trouxe exame novo, anexado ao prontuário.": "sem_acao",
        "": "sem_acao",
    }
    for texto, esperado in casos.items():
        assert observacao.classificar(texto)["intencao"] == esperado, texto
    d = observacao.por_palavra_chave("Autorizado por telefone, protocolo 771203, aguardando número.")["detalhes"]
    assert d["protocolo"] == "771203"
    d = observacao.por_palavra_chave("Procedimento realizado foi drenagem linfática, lançar o código certo.")["detalhes"]
    assert d["procedimento_realizado"] == "drenagem linfática"


def _cliente_falso(resposta: str):
    class Msg:  # imita openai.chat.completions.create(...).choices[0].message.content
        content = resposta
    class Choice:
        message = Msg()
    class Resp:
        choices = [Choice()]
    class Completions:
        def create(self, **kw):
            return Resp()
    class Chat:
        completions = Completions()
    class Cliente:
        def __init__(self, **kw):
            self.chat = Chat()
    return Cliente


def test_caminho_da_ia_simulado(monkeypatch):
    import openai
    monkeypatch.setattr(config, "OPENAI_API_KEY", "chave-falsa")
    monkeypatch.setattr(openai, "OpenAI", _cliente_falso(json.dumps(
        {"intencao": "protocolo_verbal", "protocolo": "771203", "validade_informada": None, "confianca": 0.95})))
    r = observacao.classificar("Autorizado por telefone, protocolo 771203, aguardando número.", usar_cache=False)
    assert r == {"intencao": "protocolo_verbal", "fonte": "llm", "detalhes": {"protocolo": "771203", "confianca": 0.95}}


def test_ia_respondendo_lixo_cai_no_fallback(monkeypatch):
    import openai
    monkeypatch.setattr(config, "OPENAI_API_KEY", "chave-falsa")
    monkeypatch.setattr(openai, "OpenAI", _cliente_falso("isso não é json"))
    r = observacao.classificar("Paciente pediu para faturar como particular.", usar_cache=False)
    assert r["intencao"] == "faturar_particular" and r["fonte"] == "palavra_chave"


def test_ia_fora_do_ar_cai_no_fallback(monkeypatch):
    import openai
    monkeypatch.setattr(config, "OPENAI_API_KEY", "chave-falsa")
    def explode(**kw):
        raise ConnectionError("api fora")
    monkeypatch.setattr(openai, "OpenAI", explode)
    r = observacao.classificar("Sessão remarcada de 12/08 para hoje.", usar_cache=False)
    assert r["intencao"] == "remarcacao" and r["fonte"] == "palavra_chave"


def test_cache_evita_segunda_chamada(monkeypatch):
    chamadas = {"n": 0}
    def contar(texto):
        chamadas["n"] += 1
        return {"intencao": "reembolso", "fonte": "llm", "detalhes": {}}
    monkeypatch.setattr(observacao, "por_ia", contar)
    observacao.classificar("Pediu recibo para reembolso do plano.")
    observacao.classificar("Pediu recibo para reembolso do plano.")
    assert chamadas["n"] == 1
