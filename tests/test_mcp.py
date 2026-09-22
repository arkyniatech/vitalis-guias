"""O MCP usa o mesmo motor do app: mesma decisão, mesmos números."""
import json
from pathlib import Path

from mcp_vitalis import server

RAIZ = Path(__file__).resolve().parent.parent


def test_consultar_regra():
    r = server.consultar_regra("plano bem", "consulta")
    assert r["cobre"] is False and r["registro_profissional_exigido"] == "CRM"
    assert server.consultar_regra("Saúde Interior", "40201015")["cobre"] is True
    assert "opcoes" in server.consultar_regra("Vitalcard", "fisioterapia")  # ambíguo: pergunta qual
    assert "erro" in server.consultar_regra("Unimed", "50000470")


def test_verificar_guia_devolve_decisao_e_motivo():
    server._carregar_agosto()
    guia = json.loads((RAIZ / "dados" / "exemplo_guia_nova.json").read_text())
    r = server.verificar_guia(guia)
    assert r["decisao"] == "PENDENTE" and r["status"] == "bloqueada"
    codigos = {m["codigo"] for m in r["motivos"]}
    assert {"SESSAO_EXCEDE_LIMITE", "CAMPO_OBRIGATORIO_AUSENTE", "FORMATO"} <= codigos
    # o registro que falta aparece sugerido, vindo das guias de agosto
    assert any("CREFITO" in m["corrigir"] for m in r["motivos"] if m["campo"] == "profissional_registro")


def test_agosto_bate_com_o_gabarito():
    server._carregar_agosto()
    rel = server.relatorio_da_semana()
    assert (rel["verificadas"], rel["com_problema"], rel["valor_em_risco"]) == (80, 39, 2642.0)
    assert server.buscar_guia("g-2608-0007")["conferencia"]["decisao"] == "PENDENTE"
