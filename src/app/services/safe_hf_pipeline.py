from __future__ import annotations

from typing import Any

from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_huggingface import HuggingFacePipeline


class SafeHuggingFacePipeline(HuggingFacePipeline):
    """LangChain HF pipeline wrapper that drops unsupported kwargs.

    Some text2text models fail when `return_full_text` is forwarded into
    `model.generate(...)`. This wrapper strips the kwarg defensively.
    """

    def _generate(
        self,
        prompts: list[str],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ):
        sanitized_kwargs = dict(kwargs)
        sanitized_kwargs.pop("return_full_text", None)

        pipeline_kwargs = sanitized_kwargs.get("pipeline_kwargs")
        if isinstance(pipeline_kwargs, dict):
            cleaned_pipeline_kwargs = dict(pipeline_kwargs)
            cleaned_pipeline_kwargs.pop("return_full_text", None)
            sanitized_kwargs["pipeline_kwargs"] = cleaned_pipeline_kwargs

        return super()._generate(
            prompts,
            stop=stop,
            run_manager=run_manager,
            **sanitized_kwargs,
        )
