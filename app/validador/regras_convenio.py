"""Carrega regras_convenio.json. Trocar o arquivo = trocar as regras, sem mexer em código."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import REGRAS_PATH

# Que tipo de registro profissional cada procedimento exige.
# CREFITO = fisioterapeuta, CRM = médico. Não está no JSON, é regra da clínica.
REGISTRO_POR_PROCEDIMENTO = {
    "50000470": "CREFITO",
    "50000560": "CREFITO",
    "50000012": "CREFITO",
    "20103301": "CRM",
    "40201015": "CRM",
}


@dataclass(frozen=True)
class Convenio:
    nome: str
    campos_obrigatorios: tuple[str, ...]
    validade_maxima_autorizacao_dias: int
    limite_sessoes_por_autorizacao: int
    procedimentos_cobertos: tuple[str, ...]
    prazo_envio_dias: int
    observacao: str
    aceita_autorizacao_verbal_dias_uteis: int  # 0 = não aceita


@dataclass(frozen=True)
class Regras:
    versao: str
    procedimentos: dict[str, dict]
    convenios: dict[str, Convenio]

    def convenio(self, nome: str) -> Convenio | None:
        if not nome:
            return None
        # tolera diferença de caixa e acento simples
        chave = nome.strip().lower()
        for n, c in self.convenios.items():
            if n.lower() == chave:
                return c
        return None


@lru_cache(maxsize=4)
def carregar(caminho: str | Path = REGRAS_PATH) -> Regras:
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    procedimentos = {p["codigo"]: p for p in dados["procedimentos"]}
    convenios = {}
    for c in dados["convenios"]:
        obs = c.get("observacao", "")
        # "Aceita autorização verbal com protocolo por até 5 dias úteis" -> 5
        verbal = 0
        if "autorização verbal" in obs.lower():
            import re
            m = re.search(r"(\d+)\s*dias?\s*úteis", obs.lower())
            verbal = int(m.group(1)) if m else 5
        convenios[c["nome"]] = Convenio(
            nome=c["nome"],
            campos_obrigatorios=tuple(c["campos_obrigatorios"]),
            validade_maxima_autorizacao_dias=int(c["validade_maxima_autorizacao_dias"]),
            limite_sessoes_por_autorizacao=int(c["limite_sessoes_por_autorizacao"]),
            procedimentos_cobertos=tuple(c["procedimentos_cobertos"]),
            prazo_envio_dias=int(c["prazo_envio_dias"]),
            observacao=obs,
            aceita_autorizacao_verbal_dias_uteis=verbal,
        )
    return Regras(versao=dados.get("versao", ""), procedimentos=procedimentos, convenios=convenios)
