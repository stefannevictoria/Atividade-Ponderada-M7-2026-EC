import json
from pathlib import Path

import pandas as pd
from prophet import Prophet
from prophet.serialize import model_to_json

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_DADOS = RAIZ / "data" / "dolar.csv"
PASTA_ARTEFATOS = RAIZ / "artifacts"
N_TESTE = 20


def criar_modelo():
    return Prophet(
        daily_seasonality=False,
        weekly_seasonality=False,
        yearly_seasonality=False,
    )


def main():
    PASTA_ARTEFATOS.mkdir(parents=True, exist_ok=True)

    # 1. Preparar os dados.
    dados = pd.read_csv(ARQUIVO_DADOS)

    if not {"data", "fechamento"}.issubset(dados.columns):
        raise ValueError("O CSV precisa ter data e fechamento.")

    dados = dados.rename(columns={"data": "ds", "fechamento": "y"})
    dados = dados[["ds", "y"]].copy()
    dados["ds"] = pd.to_datetime(
        dados["ds"], format="%Y-%m-%d", errors="coerce"
    )
    dados["y"] = pd.to_numeric(dados["y"], errors="coerce")
    dados["y"] = dados["y"].replace(
        [float("inf"), float("-inf")], float("nan")
    )

    quantidade_original = len(dados)

    dados = (
        dados.dropna()
        .sort_values("ds")
        .drop_duplicates("ds", keep="last")
        .reset_index(drop=True)
    )

    if len(dados) < N_TESTE + 20:
        raise ValueError("Histórico insuficiente para treino e teste.")

    if (dados["y"] <= 0).any():
        raise ValueError("Existem cotações menores ou iguais a zero.")

    print(f"Registros válidos: {len(dados)}")
    print(f"Removidos: {quantidade_original - len(dados)}")
    print(f"Última data disponível: {dados['ds'].max().date()}")

    # 2. Avaliação walk-forward nas últimas 20 observações.
    # Cada modelo usa somente os dados anteriores à data prevista.
    corte = len(dados) - N_TESTE
    registros = []

    for i in range(corte, len(dados)):
        treino = dados.iloc[:i].copy()
        observacao = dados.iloc[i]

        modelo = criar_modelo()
        modelo.fit(treino)

        entrada = pd.DataFrame({"ds": [observacao["ds"]]})
        previsto = float(modelo.predict(entrada)["yhat"].iloc[0])
        real = float(observacao["y"])

        # Baseline: último fechamento conhecido.
        naive = float(treino["y"].iloc[-1])

        registros.append({
            "data": observacao["ds"].date().isoformat(),
            "real": real,
            "previsto_prophet": previsto,
            "previsto_naive": naive,
            "erro_absoluto_prophet": abs(real - previsto),
            "erro_absoluto_naive": abs(real - naive),
        })

        print(
            f"Teste {i - corte + 1}/{N_TESTE}: "
            f"{observacao['ds'].date()} | "
            f"real={real:.4f} | previsto={previsto:.4f}"
        )

    resultados = pd.DataFrame(registros)
    mae_prophet = float(resultados["erro_absoluto_prophet"].mean())
    mae_naive = float(resultados["erro_absoluto_naive"].mean())

    resultados.to_csv(
        PASTA_ARTEFATOS / "previsoes_teste.csv",
        index=False,
    )

    print(f"MAE Prophet: {mae_prophet:.6f} BRL por USD")
    print(f"MAE Naive: {mae_naive:.6f} BRL por USD")

    # 3. Modelo final: utiliza todo o histórico disponível.
    modelo_final = criar_modelo()
    modelo_final.fit(dados)

    (PASTA_ARTEFATOS / "modelo.json").write_text(
        model_to_json(modelo_final),
        encoding="utf-8",
    )

    # 4. Demonstração: prever a próxima data de segunda a sexta.
    # BDay não considera feriados nem o calendário específico da fonte.
    ultima_data = dados["ds"].max()
    data_prevista = ultima_data + pd.offsets.BDay(1)

    previsao = modelo_final.predict(
        pd.DataFrame({"ds": [data_prevista]})
    )

    demonstracao = {
        "ultima_data_historico": ultima_data.date().isoformat(),
        "data_prevista": data_prevista.date().isoformat(),
        "cotacao_prevista": float(previsao["yhat"].iloc[0]),
        "unidade": "BRL por USD",
        "criterio_data": (
            "Próxima data de segunda a sexta, sem ajuste de feriados."
        ),
    }

    (PASTA_ARTEFATOS / "previsao_futura.json").write_text(
        json.dumps(demonstracao, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    metricas = {
        "modelo": "Prophet",
        "avaliacao": (
            "Walk-forward com janela expansiva: retreino antes "
            "de prever cada próxima observação do teste."
        ),
        "registros_validos": len(dados),
        "registros_treino_inicial": corte,
        "registros_teste": N_TESTE,
        "inicio_teste": registros[0]["data"],
        "fim_teste": registros[-1]["data"],
        "mae_prophet": mae_prophet,
        "mae_naive": mae_naive,
        "unidade": "BRL por USD",
        "fim_historico": ultima_data.date().isoformat(),
        "modelo_final": "Treinado com todo o histórico válido.",
    }

    (PASTA_ARTEFATOS / "metricas.json").write_text(
        json.dumps(metricas, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nPrevisão futura:")
    print(json.dumps(demonstracao, indent=2, ensure_ascii=False))
    print("Modelo e resultados salvos em artifacts.")


if __name__ == "__main__":
    main()