from pathlib import Path

import yfinance as yf

# Localiza a raiz do projeto independentemente da pasta de execução.
RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "data"
PASTA_DADOS.mkdir(parents=True, exist_ok=True)

# A data final é exclusiva: não inclui a cotação parcial de 05/10.
dados = yf.Ticker("BRL=X").history(
    start="2023-01-01",
    end="2026-10-05",
    interval="1d",
    auto_adjust=False,
)

if dados.empty:
    raise RuntimeError(
        "Nenhum dado foi recebido. Verifique a conexão e tente novamente."
    )

# Mantém apenas data e cotação de fechamento.
dados = (
    dados[["Close"]]
    .dropna()
    .sort_index()
    .rename(columns={"Close": "fechamento"})
)

dados.index.name = "data"
arquivo = PASTA_DADOS / "dolar.csv"
dados.to_csv(arquivo, date_format="%Y-%m-%d")

print(f"CSV salvo em: {arquivo}")
print(f"Quantidade de registros: {len(dados)}")
print(dados.head())
print(dados.tail())