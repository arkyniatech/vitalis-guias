"""Deixa a guia num formato único antes das regras rodarem.

A recepção digita de tudo: data em dd/mm/aaaa, valor com vírgula, espaço sobrando.
Aqui a gente aceita o que vier, converte o que der, e anota o que precisou converter
pra regra de formato conseguir avisar a recepção.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

CAMPOS = [
    "id_guia", "unidade", "data_atendimento", "paciente", "convenio", "carteirinha", "cid",
    "procedimento_codigo", "procedimento_descricao", "numero_autorizacao", "autorizacao_validade",
    "autorizacao_sessoes_limite", "sessao_numero_na_autorizacao", "profissional",
    "profissional_registro", "valor", "observacao_recepcao", "data_lancamento",
]

FORMATOS_DATA = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d")


@dataclass
class GuiaNormalizada:
    """Guia com tipos certos + lista do que foi convertido."""
    bruto: dict[str, str]
    id_guia: str = ""
    unidade: str = ""
    paciente: str = ""
    convenio: str = ""
    carteirinha: str = ""
    cid: str = ""
    procedimento_codigo: str = ""
    procedimento_descricao: str = ""
    numero_autorizacao: str = ""
    profissional: str = ""
    profissional_registro: str = ""
    observacao_recepcao: str = ""
    data_atendimento: date | None = None
    autorizacao_validade: date | None = None
    data_lancamento: date | None = None
    autorizacao_sessoes_limite: int | None = None
    sessao_numero: int | None = None
    valor: float | None = None
    conversoes: list[str] = field(default_factory=list)   # o que foi ajustado
    invalidos: list[str] = field(default_factory=list)    # o que não deu pra ler

    def campo_vazio(self, nome: str) -> bool:
        return not (self.bruto.get(nome) or "").strip()


def _texto(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def ler_data(valor: Any) -> tuple[date | None, bool]:
    """Devolve (data, precisou_converter). Aceita aaaa-mm-dd e dd/mm/aaaa."""
    s = _texto(valor)
    if not s:
        return None, False
    if isinstance(valor, date):
        return valor, False
    for i, fmt in enumerate(FORMATOS_DATA):
        try:
            return datetime.strptime(s, fmt).date(), i != 0
        except ValueError:
            continue
    return None, True


def ler_valor(valor: Any) -> tuple[float | None, bool]:
    """Aceita 62.00, "62,00", "R$ 62,00", "1.300,00". Devolve (float, precisou_converter)."""
    if isinstance(valor, (int, float)):
        return float(valor), False
    s = _texto(valor)
    if not s:
        return None, False
    limpo = re.sub(r"[^\d,.\-]", "", s)
    convertido = limpo != s
    if "," in limpo:
        convertido = True
        limpo = limpo.replace(".", "").replace(",", ".")
    try:
        return float(limpo), convertido
    except ValueError:
        return None, True


def ler_inteiro(valor: Any) -> int | None:
    s = _texto(valor)
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def normalizar(bruto: dict[str, Any]) -> GuiaNormalizada:
    """Recebe o dict cru (CSV ou JSON) e devolve a guia tipada."""
    b = {c: _texto(bruto.get(c)) for c in CAMPOS}
    # campos extras que vierem do sistema não atrapalham, mas ficam guardados
    for k, v in bruto.items():
        if k not in b:
            b[k] = _texto(v)

    g = GuiaNormalizada(bruto=b)
    for nome in ("id_guia", "unidade", "paciente", "convenio", "carteirinha", "cid",
                 "procedimento_codigo", "procedimento_descricao", "numero_autorizacao",
                 "profissional", "profissional_registro", "observacao_recepcao"):
        setattr(g, nome, b[nome])
    g.convenio = g.convenio.strip()
    g.carteirinha = re.sub(r"\s", "", g.carteirinha)
    g.cid = g.cid.upper().replace(" ", "")

    for nome in ("data_atendimento", "autorizacao_validade", "data_lancamento"):
        d, convertida = ler_data(b[nome])
        setattr(g, nome, d)
        if d is None and b[nome]:
            g.invalidos.append(nome)
        elif convertida:
            g.conversoes.append(nome)

    v, convertido = ler_valor(b["valor"])
    g.valor = v
    if v is None and b["valor"]:
        g.invalidos.append("valor")
    elif convertido:
        g.conversoes.append("valor")

    g.autorizacao_sessoes_limite = ler_inteiro(b["autorizacao_sessoes_limite"])
    g.sessao_numero = ler_inteiro(b["sessao_numero_na_autorizacao"])
    if g.sessao_numero is None and b["sessao_numero_na_autorizacao"]:
        g.invalidos.append("sessao_numero_na_autorizacao")
    return g
