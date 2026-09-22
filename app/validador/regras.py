"""As regras de conferência. Uma função por regra, todas com a mesma assinatura.

Cada regra devolve uma lista de Achado. O motor junta tudo e decide o status da guia.
Severidades:
  bloqueia  -> não pode ir pro convênio do jeito que está; precisa de decisão ou documento novo
  pendente  -> esperando algo com prazo (ex.: número de autorização verbal)
  corrigir  -> erro mecânico, a recepção corrige em um clique e envia
  atencao   -> não impede o envio, mas alguém deveria olhar
glosa_provavel -> True quando, enviada como está, a guia volta glosada.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from app.validador.normalizador import GuiaNormalizada
from app.validador.regras_convenio import REGISTRO_POR_PROCEDIMENTO, Convenio, Regras

BLOQUEIA, PENDENTE, CORRIGIR, ATENCAO = "bloqueia", "pendente", "corrigir", "atencao"


@dataclass
class Achado:
    codigo: str
    severidade: str
    glosa_provavel: bool
    mensagem: str
    acao: str = ""
    campo: str = ""
    dados: dict = field(default_factory=dict)

    def dict(self) -> dict:
        return asdict(self)


@dataclass
class Contexto:
    """O que a regra precisa saber além da guia em si."""
    data_referencia: date                      # "hoje" da verificação
    obs: dict                                  # resultado de observacao.classificar
    registros_conhecidos: set[str] = field(default_factory=set)       # só pra sugerir na ação
    guias_mesmo_atendimento: list[dict] = field(default_factory=list)  # mesma carteirinha+data (banco/lote)


NOME_CAMPO = {
    "numero_autorizacao": "número da autorização", "autorizacao_validade": "validade da autorização",
    "profissional_registro": "registro do profissional", "carteirinha": "carteirinha", "cid": "CID",
    "data_atendimento": "data do atendimento", "data_lancamento": "data de lançamento", "valor": "valor",
}
ACAO_CAMPO_VAZIO = {
    "numero_autorizacao": "Conseguir o número da autorização com o convênio antes de enviar. Sem ele, glosa.",
    "autorizacao_validade": "Lançar a validade que está na autorização.",
    "carteirinha": "Lançar a carteirinha do paciente (está no cadastro ou no cartão do convênio).",
    "cid": "Pedir o CID ao profissional que atendeu (está no pedido médico) e lançar antes de enviar.",
}


def _fmt(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "?"


def _dias_uteis_depois(inicio: date, n: int) -> date:
    d = inicio
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


# ----------------------------------------------------------------------------- regras

def regra_convenio_conhecido(g: GuiaNormalizada, c: Convenio | None, r: Regras, ctx: Contexto) -> list[Achado]:
    if c is None:
        nomes = ", ".join(r.convenios)
        return [Achado("CONVENIO_DESCONHECIDO", BLOQUEIA, True,
                       f"Convênio '{g.convenio or '(vazio)'}' não está nas regras. Conhecidos: {nomes}.",
                       "Conferir o nome do convênio na guia.", "convenio")]
    return []


def regra_campos_ilegiveis(g: GuiaNormalizada, c, r, ctx) -> list[Achado]:
    out = []
    for campo in g.invalidos:
        out.append(Achado("CAMPO_ILEGIVEL", CORRIGIR, True,
                          f"Não consegui ler {campo}: '{g.bruto.get(campo)}'.",
                          "Corrigir o valor no sistema antes de enviar.", campo))
    return out


def regra_formato(g: GuiaNormalizada, c, r, ctx) -> list[Achado]:
    """Data com barra, valor com vírgula. O conteúdo está certo, só o formato não:
    a regra já leu certo, mas no sistema o campo continua torto e é isso que vai pro convênio.
    Por isso é "corrigir", mas não conta como dinheiro em risco."""
    out = []
    for campo in g.conversoes:
        bruto = g.bruto.get(campo)
        nome = NOME_CAMPO.get(campo, campo)
        if campo == "valor":
            msg = f"Valor digitado como '{bruto}' (com vírgula). Li como {g.valor:.2f}."
            acao = f"Corrigir o valor no sistema para {g.valor:.2f}."
        else:
            certo = getattr(g, campo)
            msg = f"{nome.capitalize()} digitada como '{bruto}'. O padrão do sistema é AAAA-MM-DD."
            acao = f"Corrigir a {nome} no sistema para {certo.isoformat() if certo else '?'}."
        out.append(Achado("FORMATO", CORRIGIR, False, msg, acao, campo))
    return out


def regra_campos_obrigatorios(g: GuiaNormalizada, c: Convenio, r, ctx: Contexto) -> list[Achado]:
    out = []
    intencao = ctx.obs.get("intencao")
    det = ctx.obs.get("detalhes", {})
    for campo in c.campos_obrigatorios:
        if not g.campo_vazio(campo):
            continue

        if campo == "profissional_registro":
            # O profissional está na guia; o registro dele é cadastro, não documento novo.
            # Por isso é "corrigir" sempre. Outras guias só entram como dica na ação.
            tipo = REGISTRO_POR_PROCEDIMENTO.get(g.procedimento_codigo, "CREFITO/CRM")
            dados, acao = {}, f"Preencher com o {tipo} de {g.profissional or 'quem atendeu'}."
            if ctx.registros_conhecidos:
                sug = sorted(ctx.registros_conhecidos)[0]
                dados = {"sugestao": sug}
                acao = f"Preencher com o registro de {g.profissional}. Nas outras guias ele aparece como {sug}."
            out.append(Achado("CAMPO_OBRIGATORIO_AUSENTE", CORRIGIR, True,
                              f"Sem registro do profissional. {c.nome} exige.", acao, campo, dados))
            continue

        if campo == "numero_autorizacao" and intencao == "protocolo_verbal":
            if c.aceita_autorizacao_verbal_dias_uteis and g.data_atendimento:
                limite = _dias_uteis_depois(g.data_atendimento, c.aceita_autorizacao_verbal_dias_uteis)
                prot = det.get("protocolo", "?")
                if ctx.data_referencia <= limite:
                    out.append(Achado("AUTORIZACAO_VERBAL_PENDENTE", PENDENTE, True,
                                      f"Autorização verbal (protocolo {prot}). {c.nome} aceita por "
                                      f"{c.aceita_autorizacao_verbal_dias_uteis} dias úteis: até {_fmt(limite)}.",
                                      f"Ligar no convênio, pegar o número da autorização e lançar até {_fmt(limite)}. "
                                      "Não enviar antes disso.", campo, {"protocolo": prot, "limite": str(limite)}))
                else:
                    out.append(Achado("AUTORIZACAO_VERBAL_VENCIDA", BLOQUEIA, True,
                                      f"Autorização verbal (protocolo {prot}) passou do prazo de "
                                      f"{c.aceita_autorizacao_verbal_dias_uteis} dias úteis ({_fmt(limite)}) sem número lançado.",
                                      "Pedir nova autorização ao convênio.", campo))
            else:
                out.append(Achado("CAMPO_OBRIGATORIO_AUSENTE", BLOQUEIA, True,
                                  f"Sem número de autorização e {c.nome} não aceita autorização verbal.",
                                  "Pegar o número da autorização antes de enviar.", campo))
            continue

        if campo == "numero_autorizacao" and intencao == "nova_autorizacao":
            out.append(Achado("CAMPO_OBRIGATORIO_AUSENTE", CORRIGIR, True,
                              "Sem número de autorização, mas a recepção anotou que o paciente trouxe autorização nova.",
                              "Lançar o número da autorização nova antes de enviar.", campo))
            continue

        nome = NOME_CAMPO.get(campo, campo)
        acao = ACAO_CAMPO_VAZIO.get(campo, f"Preencher {nome} antes de enviar.")
        out.append(Achado("CAMPO_OBRIGATORIO_AUSENTE", BLOQUEIA, True,
                          f"Sem {nome}. {c.nome} exige.", acao, campo))
    return out


def regra_procedimento(g: GuiaNormalizada, c: Convenio, r: Regras, ctx) -> list[Achado]:
    cod = g.procedimento_codigo
    if not cod:
        return [Achado("PROCEDIMENTO_AUSENTE", BLOQUEIA, True, "Guia sem código de procedimento.",
                       "Lançar o procedimento.", "procedimento_codigo")]
    if cod not in r.procedimentos:
        return [Achado("PROCEDIMENTO_DESCONHECIDO", BLOQUEIA, True,
                       f"Código {cod} não existe na tabela de procedimentos dos convênios.",
                       "Conferir o código. Se for procedimento fora da tabela, é particular.", "procedimento_codigo")]
    out = []
    desc_ref = r.procedimentos[cod]["descricao"]
    if g.procedimento_descricao and g.procedimento_descricao.strip().lower() != desc_ref.lower():
        out.append(Achado("DESCRICAO_DIVERGE", ATENCAO, False,
                          f"Descrição '{g.procedimento_descricao}' não bate com o código {cod} ({desc_ref}).",
                          "Conferir se o código é o do procedimento feito.", "procedimento_descricao"))
    if cod not in c.procedimentos_cobertos:
        eh_consulta = cod == "20103301"
        if eh_consulta and "particular" in c.observacao.lower():
            acao = f"Faturar como particular. Regra do {c.nome}: '{c.observacao}'"
        else:
            acao = f"Não enviar ao {c.nome}. Confirmar com o paciente: particular ou outro convênio."
        out.append(Achado("PROCEDIMENTO_NAO_COBERTO", BLOQUEIA, True,
                          f"{c.nome} não cobre {desc_ref} ({cod}).", acao, "procedimento_codigo"))
    return out


def regra_autorizacao(g: GuiaNormalizada, c: Convenio, r, ctx: Contexto) -> list[Achado]:
    """Validade contra a data do atendimento, com o último dia valendo (regras_convenio.json).

    O CSV só traz a data final da autorização, não a de concessão. Por isso NÃO existe regra
    comparando a validade com o máximo de dias do convênio: seria inventar a data de concessão.
    """
    out = []
    if not (g.autorizacao_validade and g.data_atendimento):
        return out
    intencao = ctx.obs.get("intencao")
    det = ctx.obs.get("detalhes", {})
    if g.autorizacao_validade < g.data_atendimento:
        base = (f"Autorização {g.numero_autorizacao or '(sem número)'} venceu em {_fmt(g.autorizacao_validade)} "
                f"e o atendimento foi em {_fmt(g.data_atendimento)}.")
        if intencao == "nova_autorizacao":
            val = det.get("validade_informada")
            extra = f" (validade {val})" if val else ""
            out.append(Achado("AUTORIZACAO_VENCIDA", CORRIGIR, True,
                              base + f" A recepção anotou que o paciente trouxe autorização nova{extra}, ainda não lançada.",
                              "Lançar o número e a validade da autorização nova e enviar.", "autorizacao_validade"))
        else:
            out.append(Achado("AUTORIZACAO_VENCIDA", BLOQUEIA, True, base + " Vai glosar.",
                              "Pedir nova autorização ao convênio antes de enviar.", "autorizacao_validade"))
    return out


def regra_sessoes(g: GuiaNormalizada, c: Convenio, r, ctx) -> list[Achado]:
    out = []
    if g.sessao_numero is None:
        if g.procedimento_codigo in ("50000470", "50000560", "50000012"):
            out.append(Achado("SESSAO_AUSENTE", CORRIGIR, True, "Sessão sem número dentro da autorização.",
                              "Informar qual sessão é (1ª, 2ª...).", "sessao_numero_na_autorizacao"))
        return out
    lim = c.limite_sessoes_por_autorizacao
    if g.sessao_numero > lim:
        acao = f"Precisa de nova autorização. {c.nome} cobre {lim} sessões por autorização."
        if c.observacao and "reavalia" in c.observacao.lower():
            acao += f" ({c.observacao})"
        out.append(Achado("SESSAO_EXCEDE_LIMITE", BLOQUEIA, True,
                          f"Sessão nº {g.sessao_numero} numa autorização que cobre {lim}.", acao,
                          "sessao_numero_na_autorizacao"))
    if g.autorizacao_sessoes_limite is not None and g.autorizacao_sessoes_limite != lim:
        out.append(Achado("LIMITE_SESSOES_DIVERGE", ATENCAO, False,
                          f"Guia diz que a autorização cobre {g.autorizacao_sessoes_limite} sessões; regra do {c.nome} é {lim}.",
                          "Conferir com a autorização em mãos.", "autorizacao_sessoes_limite"))
    return out


def regra_registro_profissional(g: GuiaNormalizada, c, r, ctx) -> list[Achado]:
    reg = g.profissional_registro
    if not reg:
        return []  # ausência já é tratada em campos obrigatórios
    out = []
    esperado = REGISTRO_POR_PROCEDIMENTO.get(g.procedimento_codigo)
    tipo = "CREFITO" if reg.upper().startswith("CREFITO") else "CRM" if reg.upper().startswith("CRM") else ""
    if not tipo or not re.match(r"^(CREFITO-\d+\s+\d+(-[A-Z])?|CRM-[A-Z]{2}\s+\d+)$", reg.upper()):
        out.append(Achado("REGISTRO_FORMATO", CORRIGIR, True,
                          f"Registro '{reg}' fora do padrão (CREFITO-3 123456-F ou CRM-SP 12345).",
                          "Corrigir o registro do profissional.", "profissional_registro"))
    if esperado and tipo and tipo != esperado:
        quem = "fisioterapeuta (CREFITO)" if esperado == "CREFITO" else "médico (CRM)"
        out.append(Achado("REGISTRO_INCOMPATIVEL", BLOQUEIA, True,
                          f"{g.procedimento_descricao or g.procedimento_codigo} exige {quem}, mas o profissional lançado é "
                          f"{g.profissional} ({reg}).",
                          "Ou o profissional está errado, ou o procedimento. Conferir com quem atendeu.",
                          "profissional_registro"))
    return out


def regra_valor(g: GuiaNormalizada, c, r: Regras, ctx) -> list[Achado]:
    if g.valor is None:
        return [Achado("VALOR_AUSENTE", CORRIGIR, True, "Guia sem valor.", "Lançar o valor do procedimento.", "valor")]
    ref = r.procedimentos.get(g.procedimento_codigo, {}).get("valor_referencia")
    if ref is not None and abs(g.valor - ref) > 0.005:
        return [Achado("VALOR_DIVERGE", CORRIGIR, True,
                       f"Valor {g.valor:.2f} difere da referência {ref:.2f} do procedimento.",
                       f"Corrigir para {ref:.2f} ou justificar.", "valor")]
    return []


def regra_datas_e_prazo(g: GuiaNormalizada, c: Convenio, r, ctx: Contexto) -> list[Achado]:
    out = []
    if g.data_lancamento and g.data_atendimento and g.data_lancamento < g.data_atendimento:
        out.append(Achado("LANCAMENTO_ANTES_DO_ATENDIMENTO", ATENCAO, False,
                          f"Lançada em {_fmt(g.data_lancamento)}, antes do atendimento ({_fmt(g.data_atendimento)}).",
                          "Conferir as datas.", "data_lancamento"))
    if g.data_atendimento:
        vence = g.data_atendimento + timedelta(days=c.prazo_envio_dias)
        dias = (vence - ctx.data_referencia).days
        if dias < 0:
            out.append(Achado("PRAZO_ENVIO_VENCIDO", BLOQUEIA, True,
                              f"Prazo de envio ao {c.nome} ({c.prazo_envio_dias} dias) venceu em {_fmt(vence)}.",
                              "Se ainda não foi enviada, o convênio vai recusar. Conferir se já foi.", "data_atendimento",
                              {"vence_em": str(vence), "dias": dias}))
        elif dias <= 7:
            out.append(Achado("PRAZO_ENVIO_PROXIMO", ATENCAO, False,
                              f"Prazo de envio vence em {dias} dia(s), em {_fmt(vence)}.",
                              "Enviar esta semana.", "data_atendimento", {"vence_em": str(vence), "dias": dias}))
    return out


def _chave_ordem(guia: dict | GuiaNormalizada) -> tuple:
    """Quem foi lançada antes. A duplicata é sempre a que chegou depois."""
    if isinstance(guia, GuiaNormalizada):
        return (guia.data_lancamento or date.max, guia.id_guia)
    return (guia.get("data_lancamento") or date.max, guia.get("id_guia") or "")


def regra_duplicidade(g: GuiaNormalizada, c, r, ctx: Contexto) -> list[Achado]:
    """A mesma guia lançada duas vezes: mesma carteirinha, data, procedimento, autorização e sessão.

    Não é reconstruir histórico de autorização (as 80 guias são um recorte): é comparar o que
    duas guias declaram. Só a lançada por último é marcada, então reenviar o lote não muda nada.
    Mesmo código de paciente com carteirinha diferente NÃO é duplicata.
    """
    for outra in ctx.guias_mesmo_atendimento:
        if outra.get("id_guia") == g.id_guia:
            continue
        if _chave_ordem(outra) >= _chave_ordem(g):
            continue
        mesmo = ((outra.get("procedimento_codigo") or "") == g.procedimento_codigo
                 and (outra.get("numero_autorizacao") or "") == g.numero_autorizacao
                 and outra.get("sessao_numero") == g.sessao_numero)
        if mesmo:
            return [Achado("GUIA_DUPLICADA", BLOQUEIA, True,
                           f"Mesma carteirinha, data, procedimento, autorização e sessão da guia {outra['id_guia']}.",
                           f"Cancelar esta guia. A {outra['id_guia']} já cobre esse atendimento; "
                           "enviar as duas é cobrança em dobro e glosa certa.",
                           "id_guia", {"duplicada_de": outra["id_guia"]})]
    return []


def regra_observacao(g: GuiaNormalizada, c, r: Regras, ctx: Contexto) -> list[Achado]:
    """O que a recepção escreveu e nenhuma outra regra pega."""
    intencao = ctx.obs.get("intencao")
    det = ctx.obs.get("detalhes", {})
    obs = g.observacao_recepcao
    if intencao == "faturar_particular":
        return [Achado("OBS_FATURAR_PARTICULAR", BLOQUEIA, True,
                       f"Recepção anotou: '{obs}'.",
                       f"Não enviar ao {c.nome}. Lançar como particular.", "observacao_recepcao")]
    if intencao == "codigo_errado":
        feito = det.get("procedimento_realizado") or "outro procedimento"
        existe = any(feito.lower() in p["descricao"].lower() for p in r.procedimentos.values())
        acao = "Trocar o código pelo procedimento realizado antes de enviar."
        if not existe:
            acao += f" '{feito}' não está na tabela dos convênios: provavelmente é particular."
        return [Achado("OBS_CODIGO_ERRADO", BLOQUEIA, True,
                       f"Recepção anotou: '{obs}'. Código lançado: {g.procedimento_codigo} ({g.procedimento_descricao}).",
                       acao, "procedimento_codigo")]
    if intencao == "remarcacao":
        if g.autorizacao_validade and g.data_atendimento and g.autorizacao_validade >= g.data_atendimento:
            return [Achado("OBS_REMARCACAO", ATENCAO, False,
                           f"Sessão remarcada. Autorização vale até {_fmt(g.autorizacao_validade)}, cobre a nova data.",
                           "Nada a fazer.", "observacao_recepcao")]
        return []  # vencida já foi apontada pela regra de autorização
    if intencao == "reembolso":
        return [Achado("OBS_REEMBOLSO", ATENCAO, False,
                       f"Recepção anotou: '{obs}'. Reembolso é coisa de quem pagou particular.",
                       f"Confirmar se essa guia vai mesmo pro {c.nome} ou se o paciente pagou direto.", "observacao_recepcao")]
    if intencao == "nova_autorizacao" and g.numero_autorizacao and g.autorizacao_validade and g.data_atendimento \
            and g.autorizacao_validade >= g.data_atendimento:
        return [Achado("OBS_NOVA_AUTORIZACAO", ATENCAO, False,
                       f"Recepção anotou autorização nova, mas a lançada ({g.numero_autorizacao}) ainda vale.",
                       "Conferir se o número lançado é o da autorização nova.", "numero_autorizacao")]
    return []


# Ordem em que rodam. As duas primeiras podem interromper (sem convênio não dá pra seguir).
REGRAS_BASE = [regra_convenio_conhecido, regra_campos_ilegiveis, regra_formato]
REGRAS_CONVENIO = [
    regra_campos_obrigatorios, regra_procedimento, regra_autorizacao, regra_sessoes,
    regra_registro_profissional, regra_valor, regra_datas_e_prazo, regra_duplicidade, regra_observacao,
]
