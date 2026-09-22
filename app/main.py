"""API + dashboard. Três jeitos de uma guia entrar:
  POST /guias        JSON de uma guia (ou lista). É o que o n8n/sistema de gestão chama.
  POST /guias/lote   CSV exportado do sistema (o que a Carla tem hoje).
  GET  /             dashboard de terça.  GET /relatorio  mesmos números em JSON pro n8n.
  GET  /convenios    regras dos convênios pra gente ler.  GET /integracao  como chamar a API.
"""
from __future__ import annotations

import csv
import io
import logging
import re
import secrets
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from app import config, db, relatorio
from app.validador import motor
from app.validador.regras_convenio import REGISTRO_POR_PROCEDIMENTO, carregar

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("vitalis.api")

@asynccontextmanager
async def _ciclo_de_vida(_: FastAPI):
    db.engine()
    carregar()
    if not config.API_KEY:
        log.warning("API_KEY vazia: POST /guias aberto. Só use assim em desenvolvimento.")
    if not config.DASH_USER:
        log.warning("DASH_USER vazio: dashboard sem senha. Só use assim em desenvolvimento.")
    yield


app = FastAPI(title="Vitalis · conferência de guias", version="1.0", lifespan=_ciclo_de_vida)
templates = Jinja2Templates(directory=str(config.RAIZ / "app" / "templates"))
templates.env.filters["brl"] = relatorio.brl
templates.env.globals["rotulo"] = relatorio.rotulo
basic = HTTPBasic(auto_error=False)


def _mensagem_html(texto: str) -> Markup:
    """Mensagem de Telegram/WhatsApp (*negrito*) em HTML, pra mostrar no painel como vai chegar."""
    return Markup(re.sub(r"\*([^*\n]+)\*", r"<b>\1</b>", str(escape(texto or ""))))


templates.env.filters["mensagem"] = _mensagem_html


# --------------------------------------------------------------------------- segurança

def exige_api_key(request: Request) -> None:
    if not config.API_KEY:
        return
    chave = request.headers.get("x-api-key") or request.query_params.get("api_key")
    if not chave or not secrets.compare_digest(chave, config.API_KEY):
        raise HTTPException(401, "X-API-Key inválida ou ausente")


def exige_login(request: Request, cred: HTTPBasicCredentials | None = Depends(basic)) -> None:
    if not config.DASH_USER:
        return
    # aceita a API key também, pro n8n bater no /relatorio sem senha de gente
    chave = request.headers.get("x-api-key")
    if config.API_KEY and chave and secrets.compare_digest(chave, config.API_KEY):
        return
    ok = cred is not None and secrets.compare_digest(cred.username, config.DASH_USER) \
        and secrets.compare_digest(cred.password, config.DASH_PASS)
    if not ok:
        raise HTTPException(401, "login necessário", headers={"WWW-Authenticate": "Basic"})


def _data_ref(valor: str | None) -> date | str | None:
    """?data_referencia= vazio ou 'lancamento' (padrão: dia em que a guia foi lançada) | 'hoje' | AAAA-MM-DD"""
    if not valor or valor == "lancamento":
        return None
    if valor == "hoje":
        return valor
    try:
        return date.fromisoformat(valor)
    except ValueError:
        raise HTTPException(422, "data_referencia deve ser 'lancamento', 'hoje' ou AAAA-MM-DD")


def _resumo(res: dict) -> dict:
    return {"id_guia": res["guia"]["id_guia"], "status": res["status"], "glosa_provavel": res["glosa_provavel"],
            "valor_em_risco": res["valor_em_risco"], "unidade": res["guia"]["unidade"],
            "convenio": res["guia"]["convenio"], "data_referencia": str(res["guia"]["data_referencia"]),
            "obs": res["obs"], "mensagem": relatorio.mensagem_guia(res),
            "achados": [{k: a[k] for k in ("codigo", "severidade", "glosa_provavel", "campo", "mensagem", "acao")}
                        for a in res["achados"]]}


# --------------------------------------------------------------------------- entrada de guias

@app.post("/guias", dependencies=[Depends(exige_api_key)])
async def receber_guia(request: Request, data_referencia: str | None = Query(None)):
    """Uma guia (objeto) ou várias (lista). Devolve o resultado da conferência na hora."""
    try:
        corpo = await request.json()
    except Exception:
        raise HTTPException(422, "corpo precisa ser JSON")
    ref = _data_ref(data_referencia)
    if isinstance(corpo, dict):
        if not corpo.get("id_guia"):
            raise HTTPException(422, "id_guia é obrigatório")
        try:
            res = motor.registrar(corpo, ref, origem="api")
        except Exception as exc:
            log.exception("falha ao verificar guia %s", corpo.get("id_guia"))
            raise HTTPException(500, f"não consegui verificar a guia: {exc}")
        return _resumo(res)
    if isinstance(corpo, list):
        r = motor.registrar_lote(corpo, ref, origem="api")
        return {"verificadas": r["verificadas"], "com_erro_de_leitura": r["com_erro_de_leitura"],
                "erros": r["erros"], "resultados": [_resumo(x) for x in r["resultados"]]}
    raise HTTPException(422, "envie um objeto ou uma lista de guias")


@app.post("/guias/lote", dependencies=[Depends(exige_api_key)])
async def receber_lote(arquivo: UploadFile = File(...), data_referencia: str | None = Query(None)):
    """CSV com o mesmo cabeçalho do export do sistema. Linha ruim não derruba o lote."""
    conteudo = await arquivo.read()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            texto = conteudo.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise HTTPException(422, "não consegui ler o arquivo como texto")
    amostra = texto[:2000]
    delim = ";" if amostra.count(";") > amostra.count(",") else ","
    linhas = list(csv.DictReader(io.StringIO(texto), delimiter=delim))
    if not linhas or "id_guia" not in linhas[0]:
        raise HTTPException(422, "CSV precisa ter cabeçalho com id_guia (veja dados/guias_agosto.csv)")
    r = motor.registrar_lote(linhas, _data_ref(data_referencia), origem="lote")
    return {"verificadas": r["verificadas"], "com_erro_de_leitura": r["com_erro_de_leitura"], "erros": r["erros"],
            "resumo": relatorio.gerar()["por_status"]}


# --------------------------------------------------------------------------- leitura

@app.get("/relatorio", dependencies=[Depends(exige_login)])
def relatorio_json(desde: date | None = None, ate: date | None = None):
    return JSONResponse(jsonable_encoder(relatorio.gerar(desde, ate)), headers={"Cache-Control": "no-store"})


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(exige_login)])
def dashboard(request: Request, desde: date | None = None, ate: date | None = None):
    rel = relatorio.gerar(desde, ate)
    return templates.TemplateResponse(request, "dashboard.html", {"rel": rel, "desde": desde, "ate": ate, "aba": "painel"})


@app.get("/guias/{id_guia}", response_class=HTMLResponse, dependencies=[Depends(exige_login)])
def detalhe(request: Request, id_guia: str):
    from sqlalchemy import select
    import json
    with db.engine().connect() as cx:
        g = cx.execute(select(db.guias).where(db.guias.c.id_guia == id_guia)).mappings().first()
    if not g:
        raise HTTPException(404, "guia não encontrada")
    g = dict(g)
    g["achados"] = json.loads(g["achados"] or "[]")
    g["dados_brutos"] = json.loads(g["dados_brutos"] or "{}")
    return templates.TemplateResponse(request, "guia.html", {"g": g})


@app.delete("/guias/{id_guia}", dependencies=[Depends(exige_api_key)])
def cancelar_guia(id_guia: str):
    """Guia lançada por engano (ou de teste): sai do painel e do relatório."""
    if not db.cancelar_guia(id_guia):
        raise HTTPException(404, "guia não encontrada")
    return {"cancelada": True, "id_guia": id_guia}


@app.get("/convenios", response_class=HTMLResponse, dependencies=[Depends(exige_login)])
def convenios(request: Request):
    """As mesmas regras do GET /regras, em tela: o que cada convênio exige e cobre."""
    r = carregar()
    return templates.TemplateResponse(request, "regras.html", {
        "r": r, "convenios": list(r.convenios.values()), "registro": REGISTRO_POR_PROCEDIMENTO, "aba": "regras"})


@app.get("/integracao", response_class=HTMLResponse, dependencies=[Depends(exige_login)])
def integracao(request: Request):
    """Como o sistema de gestão / n8n conversa com o app, com as mensagens que o relatório gera hoje."""
    base = str(request.base_url).rstrip("/")
    if request.headers.get("x-forwarded-proto") == "https":
        base = base.replace("http://", "https://", 1)
    return templates.TemplateResponse(request, "integracao.html", {
        "rel": relatorio.gerar(), "base": base, "aba": "integracao"})


@app.get("/regras")
def regras_carregadas():
    r = carregar()
    return {"versao": r.versao, "convenios": {n: c.__dict__ for n, c in r.convenios.items()},
            "procedimentos": r.procedimentos}


@app.get("/saude")
def saude():
    try:
        with db.engine().connect() as cx:
            cx.exec_driver_sql("select 1")
        banco = "ok"
    except Exception as exc:
        banco = f"erro: {exc}"
    return {"app": "ok", "banco": banco, "ia": "openai" if config.OPENAI_API_KEY else "palavra_chave"}
