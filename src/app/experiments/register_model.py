from __future__ import annotations

from typing import Any

import mlflow
import mlflow.pyfunc
import pandas as pd

from app.config import load_settings
from app.services.rag_service import get_rag_service


class RAGPyFuncModel(mlflow.pyfunc.PythonModel):
    def load_context(self, context: mlflow.pyfunc.PythonModelContext) -> None:
        self.service = get_rag_service()

    def predict(self, context: mlflow.pyfunc.PythonModelContext, model_input: Any):
        if not isinstance(model_input, pd.DataFrame):
            raise ValueError("Model input must be a pandas DataFrame")
        if "question" not in model_input.columns:
            raise ValueError("Input DataFrame must contain a 'question' column")

        answers = [
            self.service.answer_question(str(question))["answer"]
            for question in model_input["question"].tolist()
        ]
        return pd.Series(answers)


def register_model() -> str:
    settings = load_settings()

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)

    with mlflow.start_run(run_name="register-rag-model") as run:
        mlflow.log_param("generation_model", settings.hf_generation_model)
        mlflow.log_param("embedding_model", settings.hf_embedding_model)
        mlflow.log_param("retrieval_top_k", settings.retrieval_k)

        if settings.vector_store_path.exists():
            mlflow.log_artifacts(
                local_dir=str(settings.vector_store_path),
                artifact_path="vectorstore",
            )

        mlflow.pyfunc.log_model(
            artifact_path="rag_pyfunc",
            python_model=RAGPyFuncModel(),
            code_path=["src"],
            registered_model_name=settings.registered_model_name,
            pip_requirements=[
                "mlflow",
                "pandas",
                "torch",
                "transformers",
                "langchain",
                "langchain-community",
                "langchain-huggingface",
                "sentence-transformers",
                "faiss-cpu",
            ],
        )

        return run.info.run_id


if __name__ == "__main__":
    run_id = register_model()
    print(f"Registered model from MLflow run: {run_id}")
