import json
from pathlib import Path

import pandas as pd
from prophet import Prophet
from prophet.serialize import model_to_json

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_DADOS = RAIZ / "data" / "dolar.csv"
PASTA_ARTEFATOS = RAIZ / "artifacts"


def criar_modelo():
    # Configuração simples para dados diários.
    # Sazonalidades desativadas nesta primeira abordagem.
    return Prophet(
        daily_seasonality=False,
        weekly_seasonality=False,
        yearly_seasonality=False,
    )


def main():
    PASTA_ARTEFATOS.mkdir(parents=True, exist_ok=True)

    # 1. Ler e preparar os dados.
    dados = pd.read_csv(ARQUIVO_DADOS)

    colunas = {"data", "fechamento"}
    if not colunas.issubset(dados.columns):
        raise ValueError("O CSV precisa ter as colunas data e fechamento.")

    dados = dados.rename(columns={"data": "ds", "fechamento": "y"})
    dados = dados[["ds", "y"]].copy()

    dados["ds"] = pd.to_datetime(
        dados["ds"], errors="coerce", utc=True
    ).dt.tz_convert(None)

    dados["y"] = pd.to_numeric(dados["y"], errors="coerce")
    dados["y"] = dados["y"].replace(
        [float("inf"), float("-inf")], float("nan")
    )

    quantidade_original = len(dados)

    dados = (
        dados.dropna(subset=["ds", "y"])
        .sort_values("ds")
        .drop_duplicates(subset=["ds"], keep="last")
        .reset_index(drop=True)
    )

    if len(dados) < 20:
        raise ValueError("São necessárias pelo menos 20 observações válidas.")

    if (dados["y"] <= 0).any():
        raise ValueError("Existem cotações menores ou iguais a zero.")

    # 2. Separar cronologicamente: 80% treino e 20% teste.
    corte = int(len(dados) * 0.8)
    treino = dados.iloc[:corte].copy()
    teste = dados.iloc[corte:].copy()

    print(f"Registros válidos: {len(dados)}")
    print(f"Registros removidos: {quantidade_original - len(dados)}")
    print(
        f"Treino: {len(treino)} registros "
        f"({treino['ds'].min().date()} até "
        f"{treino['ds'].max().date()})"
    )
    print(
        f"Teste: {len(teste)} registros "
        f"({teste['ds'].min().date()} até "
        f"{teste['ds'].max().date()})"
    )

    # 3. Treinar usando somente o conjunto de treino.
    modelo_avaliacao = criar_modelo()
    modelo_avaliacao.fit(treino)

    # 4. Prever as datas do teste sem usar seus preços.
    previsoes = modelo_avaliacao.predict(teste[["ds"]])

    resultados = teste.merge(
        previsoes[["ds", "yhat"]],
        on="ds",
        how="left",
        validate="one_to_one",
    )

    resultados["erro_absoluto"] = (
        resultados["y"] - resultados["yhat"]
    ).abs()

    mae = float(resultados["erro_absoluto"].mean())
    print(f"MAE no teste: {mae:.6f} BRL por USD")

    resultados.to_csv(
        PASTA_ARTEFATOS / "previsoes_teste.csv",
        index=False,
        date_format="%Y-%m-%d",
    )

    # 5. Treinar o modelo final com todo o histórico disponível.
    # A métrica acima continua sendo do modelo avaliado no teste.
    modelo_final = criar_modelo()
    modelo_final.fit(dados)

    caminho_modelo = PASTA_ARTEFATOS / "modelo.json"
    caminho_modelo.write_text(
        model_to_json(modelo_final),
        encoding="utf-8",
    )

    # 6. Registrar avaliação e informações do treinamento.
    metricas = {
        "modelo": "Prophet",
        "moeda": "USD/BRL",
        "unidade": "BRL por USD",
        "registros_validos": len(dados),
        "registros_treino": len(treino),
        "registros_teste": len(teste),
        "mae_teste": mae,
        "avaliacao": (
            "Previsão de todo o período de teste a partir "
            "do final do treino, sem atualização diária."
        ),
        "inicio_historico": dados["ds"].min().date().isoformat(),
        "fim_historico": dados["ds"].max().date().isoformat(),
        "modelo_final": "Retreinado com todo o histórico válido.",
        "sazonalidades": {
            "diaria": False,
            "semanal": False,
            "anual": False,
        },
    }

    (PASTA_ARTEFATOS / "metricas.json").write_text(
        json.dumps(metricas, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Modelo salvo em: {caminho_modelo}")
    print("Treinamento concluído.")


if __name__ == "__main__":
    main()