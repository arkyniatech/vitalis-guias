"""Banco: Postgres (Supabase) em produção, SQLite local e nos testes. Mesmo código nos dois."""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone

from sqlalchemy import (Column, Date, DateTime, Float, Integer, MetaData, String, Table, Text,
                        create_engine, delete, event, insert, select, update)
from sqlalchemy.engine import Engine

from app import config

metadata = MetaData()

# Uma linha por guia. Guardamos o bruto (como chegou) e o normalizado (como a regra leu).
guias = Table(
    "guias", metadata,
    Column("id_guia", String(40), primary_key=True),
    Column("unidade", String(40)),
    Column("data_atendimento", Date),
    Column("paciente", String(40)),
    Column("convenio", String(60)),
    Column("carteirinha", String(40)),
    Column("cid", String(20)),
    Column("procedimento_codigo", String(20)),
    Column("procedimento_descricao", String(120)),
    Column("numero_autorizacao", String(40)),
    Column("autorizacao_validade", Date),
    Column("autorizacao_sessoes_limite", Integer),
    Column("sessao_numero", Integer),
    Column("profissional", String(120)),
    Column("profissional_registro", String(60)),
    Column("valor", Float),
    Column("observacao_recepcao", Text),
    Column("data_lancamento", Date),
    Column("dados_brutos", Text),            # JSON do que chegou
    Column("origem", String(20)),            # api | lote
    Column("status", String(20)),            # ok | bloqueada | corrigir | pendente | atencao
    Column("glosa_provavel", Integer),       # 1 se, do jeito que está, o convênio vai glosar
    Column("valor_em_risco", Float),
    Column("obs_intencao", String(40)),
    Column("obs_fonte", String(20)),         # llm | palavra_chave | vazio
    Column("achados", Text),                 # JSON com a lista completa
    Column("data_referencia", Date),         # "hoje" no momento da verificação
    Column("prazo_envio_vence_em", Date),    # último dia pra guia chegar no convênio
    Column("recebida_em", DateTime),
    Column("verificada_em", DateTime),
)

# Uma linha por achado, pra agregar por tipo sem abrir JSON.
achados = Table(
    "achados", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("id_guia", String(40), index=True),
    Column("codigo", String(60), index=True),
    Column("severidade", String(20)),
    Column("glosa_provavel", Integer),
    Column("campo", String(60)),
    Column("mensagem", Text),
    Column("acao", Text),
)

# Cache da leitura da observação: o mesmo texto não vai pra IA duas vezes.
observacoes = Table(
    "observacoes_classificadas", metadata,
    Column("texto", String(500), primary_key=True),
    Column("intencao", String(40)),
    Column("fonte", String(20)),
    Column("detalhes", Text),
    Column("classificada_em", DateTime),
)

_engine: Engine | None = None


def engine(url: str | None = None) -> Engine:
    global _engine
    if _engine is None or url:
        u = url or config.DATABASE_URL
        kw = {"pool_pre_ping": True} if u.startswith("postgres") else {"connect_args": {"check_same_thread": False}}
        _engine = create_engine(u, **kw)
        if u.startswith("postgres") and config.DB_SCHEMA:
            _usar_schema(_engine, config.DB_SCHEMA)
        metadata.create_all(_engine)
    return _engine


def _usar_schema(e: Engine, schema: str) -> None:
    """Cada conexão nova aponta o search_path pro schema (o pooler do Supabase ignora isso na URL)."""
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", schema):
        raise ValueError(f"DB_SCHEMA inválido: {schema!r}")

    @event.listens_for(e, "connect")
    def _search_path(dbapi_conn, _):
        with dbapi_conn.cursor() as cur:
            cur.execute(f"create schema if not exists {schema}")
            cur.execute(f"set search_path to {schema}")
        dbapi_conn.commit()


def usar_engine(e: Engine) -> None:
    """Usado nos testes pra apontar pra um SQLite temporário."""
    global _engine
    _engine = e
    metadata.create_all(e)


def agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def salvar_resultado(res: dict) -> None:
    """Grava (ou regrava) a guia e seus achados. Idempotente por id_guia."""
    e = engine()
    linha = dict(res["guia"])
    linha["dados_brutos"] = json.dumps(res["bruto"], ensure_ascii=False)
    linha["achados"] = json.dumps(res["achados"], ensure_ascii=False, default=str)
    linha["verificada_em"] = agora()
    with e.begin() as cx:
        existe = cx.execute(select(guias.c.id_guia, guias.c.recebida_em).where(guias.c.id_guia == linha["id_guia"])).first()
        if existe:
            cx.execute(update(guias).where(guias.c.id_guia == linha["id_guia"]).values(**linha))
        else:
            linha["recebida_em"] = agora()
            cx.execute(insert(guias).values(**linha))
        cx.execute(delete(achados).where(achados.c.id_guia == linha["id_guia"]))
        if res["achados"]:
            cx.execute(insert(achados), [
                {"id_guia": linha["id_guia"], "codigo": a["codigo"], "severidade": a["severidade"],
                 "glosa_provavel": 1 if a["glosa_provavel"] else 0, "campo": a.get("campo") or "",
                 "mensagem": a["mensagem"], "acao": a.get("acao") or ""}
                for a in res["achados"]
            ])


def cancelar_guia(id_guia: str) -> bool:
    """Tira a guia (e os achados dela) do painel. Devolve False se não existia."""
    with engine().begin() as cx:
        apagou = cx.execute(delete(guias).where(guias.c.id_guia == id_guia)).rowcount
        cx.execute(delete(achados).where(achados.c.id_guia == id_guia))
    return apagou > 0


def buscar_observacao(texto: str) -> dict | None:
    with engine().connect() as cx:
        r = cx.execute(select(observacoes).where(observacoes.c.texto == texto)).mappings().first()
        return dict(r) if r else None


def guardar_observacao(texto: str, intencao: str, fonte: str, detalhes: dict) -> None:
    with engine().begin() as cx:
        cx.execute(delete(observacoes).where(observacoes.c.texto == texto))
        cx.execute(insert(observacoes).values(texto=texto, intencao=intencao, fonte=fonte,
                                              detalhes=json.dumps(detalhes, ensure_ascii=False),
                                              classificada_em=agora()))


def guias_mesmo_atendimento(carteirinha: str, data_atendimento: date | None, excluir_id: str) -> list[dict]:
    """Outras guias da mesma carteirinha no mesmo dia. Base da regra de duplicata.
    Usa carteirinha e não o código do paciente: a carteirinha é o que o convênio confere."""
    if not carteirinha or not data_atendimento:
        return []
    with engine().connect() as cx:
        rs = cx.execute(select(guias).where(guias.c.carteirinha == carteirinha,
                                            guias.c.data_atendimento == data_atendimento,
                                            guias.c.id_guia != excluir_id)).mappings().all()
        return [dict(r) for r in rs]


def registros_conhecidos(profissional: str) -> set[str]:
    """Registros já lançados pra esse profissional em outras guias. Serve pra sugerir o que falta."""
    if not profissional:
        return set()
    with engine().connect() as cx:
        rs = cx.execute(select(guias.c.profissional_registro).where(guias.c.profissional == profissional)).all()
        return {r[0] for r in rs if r[0]}
