FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY mcp_vitalis ./mcp_vitalis
COPY skills ./skills
COPY dados/regras_convenio.json ./dados/regras_convenio.json
COPY dados/guias_agosto.csv ./dados/guias_agosto.csv

# SQLite de fallback fica aqui quando DATABASE_URL não está definido
RUN mkdir -p /srv/dados && chmod 777 /srv/dados

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/saude')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
