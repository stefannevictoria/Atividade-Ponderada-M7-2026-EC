"""API de inferência: carrega o Prophet exportado, sem treinar novamente."""

import os
import re
from datetime import date
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, request
from prophet.serialize import model_from_json


def create_app():
    app = Flask(__name__)
    default_path = Path(__file__).resolve().parents[1] / "artifacts" / "modelo.json"
    model_path = Path(os.environ.get("MODEL_PATH", str(default_path)))

    if not model_path.is_file():
        raise FileNotFoundError(
            f"Modelo não encontrado: {model_path}. Execute o treinamento primeiro."
        )

    # O arquivo deve ter sido salvo com model_to_json(modelo).
    model = model_from_json(model_path.read_text(encoding="utf-8"))
    last_date = pd.Timestamp(model.history["ds"].max()).date()
    app.logger.info("Modelo carregado. Última data do treino: %s", last_date)

    @app.get("/health")
    def health():
        return jsonify(status="ok", modelo="Prophet", ultima_data_treino=last_date.isoformat())

    @app.post("/predict")
    def predict():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(erro="Envie um JSON com o campo data."), 400

        value = payload.get("data")
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return jsonify(erro="Use data no formato YYYY-MM-DD."), 400
        try:
            target = date.fromisoformat(value)
            timestamp = pd.Timestamp(target)
            # Confere se a data cabe no formato utilizado pelo Prophet.
            _ = timestamp.value
        except (ValueError, OverflowError, pd.errors.OutOfBoundsDatetime):
            return jsonify(erro="Data inválida ou fora do intervalo suportado."), 400

        if target <= last_date:
            return jsonify(
                erro="A data deve ser posterior à última data do treinamento.",
                ultima_data_treino=last_date.isoformat(),
            ), 400

        try:
            forecast = model.predict(pd.DataFrame({"ds": [timestamp]}))
            estimate = float(forecast.iloc[0]["yhat"])
        except Exception:
            app.logger.exception("Falha ao executar a previsão")
            return jsonify(erro="Não foi possível gerar a previsão para essa data."), 500

        return jsonify(data=value, previsao=round(estimate, 6), unidade="BRL por USD", modelo="Prophet")

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8000, debug=False)
