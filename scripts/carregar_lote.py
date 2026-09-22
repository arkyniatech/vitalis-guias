"""Manda um CSV de guias pra API. Uso:

    python scripts/carregar_lote.py dados/guias_agosto.csv https://SEU-DOMINIO SUA_API_KEY [data_referencia]

data_referencia: 'lancamento' (padrão, conferência como no dia do lançamento), 'hoje' ou AAAA-MM-DD.
"""
import sys

import httpx

if len(sys.argv) < 4:
    print(__doc__)
    sys.exit(1)

arquivo, base, chave = sys.argv[1:4]
ref = sys.argv[4] if len(sys.argv) > 4 else "lancamento"
params = {} if ref == "hoje" else {"data_referencia": ref}

with open(arquivo, "rb") as f:
    r = httpx.post(f"{base.rstrip('/')}/guias/lote", params=params, headers={"X-API-Key": chave},
                   files={"arquivo": (arquivo, f, "text/csv")}, timeout=120)
print(r.status_code)
print(r.text[:2000])
