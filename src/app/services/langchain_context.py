"""
langchain_context.py
--------------------
Dedicated LangChain LCEL (LangChain Expression Language) RAG chain module.

Context Flow (addressing guide comment on elaborating LangChain usage):
  1. FAISS Retriever  →  fetches top-k relevant transcript chunks from session index
  2. Context Assembler →  formats retrieved documents with timestamps into a prompt context
  3. PromptTemplate   →  structures the question + context into a model-ready prompt
  4. HuggingFace LLM  →  generates the answer from the structured prompt
  5. StrOutputParser   →  cleans and returns the final string answer

Each step is named via .with_config({"run_name": "..."}) so MLflow and LangSmith
can trace individual chain components.
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RAG Prompt Template
# ---------------------------------------------------------------------------

_RAG_PROMPT_TEMPLATE = """\
You are a helpful teaching assistant. Answer the student's question using ONLY
the lecture transcript context provided below. Be concise and accurate.
If the context does not contain enough information, say: "This topic is not
covered in the lecture transcript."

Lecture Transcript Context:
{context}

Student Question:
{question}

Answer (factual, 2-4 sentences):"""


def _assemble_context(docs: list[Document]) -> str:
    """
    Step 2 of the RAG chain: format retrieved documents into a clean context string.
    Each chunk includes its source filename and timestamp range for citation grounding.
    """
    if not docs:
        return "No relevant transcript segments found."

    parts: list[str] = []
    for i, doc in enumerate(docs, start=1):
        meta = doc.metadata or {}
        source = meta.get("source", "transcript")
        start_hms = meta.get("start_hms", "")
        end_hms = meta.get("end_hms", "")
        timestamp = f" [{start_hms} → {end_hms}]" if start_hms else ""
        parts.append(f"[{i}] {source}{timestamp}:\n{doc.page_content.strip()}")

    return "\n\n".join(parts)


def build_rag_chain(
    vectorstore: Any,
    llm: Any,
    top_k: int = 4,
) -> Any:
    """
    Build and return a named LangChain LCEL RAG chain.

    Pipeline steps:
        retriever     → FAISS vector similarity search (top_k chunks)
        context_build → Assembles retrieved docs into a formatted context string
        prompt        → Injects question + context into the RAG prompt template
        llm           → HuggingFace pipeline (text2text-generation)
        parser        → StrOutputParser strips extra whitespace

    Args:
        vectorstore: A LangChain-compatible FAISS vectorstore with .as_retriever()
        llm: A HuggingFacePipeline or compatible LangChain LLM
        top_k: Number of transcript chunks to retrieve per query

    Returns:
        A LangChain LCEL Runnable chain that accepts {"question": str} and
        returns a string answer.
    """
    if vectorstore is None or llm is None:
        logger.warning(
            "build_rag_chain: vectorstore or llm is None — chain will return empty answers"
        )
        return None

    # Step 1: Retriever — FAISS top-k semantic search
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": top_k},
    ).with_config({"run_name": "v2ai_faiss_retriever"})

    # Step 2: Context assembler (RunnableLambda wrapping our formatter)
    context_assembler = RunnableLambda(_assemble_context).with_config(
        {"run_name": "v2ai_context_assembler"}
    )

    # Step 3: Prompt template
    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template=_RAG_PROMPT_TEMPLATE,
    ).with_config({"run_name": "v2ai_rag_prompt"})

    # Step 4: LLM
    named_llm = llm.with_config({"run_name": "v2ai_llm_generation"})

    # Step 5: Output parser
    parser = StrOutputParser().with_config({"run_name": "v2ai_output_parser"})

    # Assemble LCEL chain:
    #   Input: {"question": str}
    #   Retriever fetches docs for "question"
    #   context_assembler formats those docs
    #   prompt combines context + question
    #   llm generates text
    #   parser returns clean string
    chain = (
        {
            "context": retriever | context_assembler,
            "question": RunnablePassthrough(),
        }
        | prompt
        | named_llm
        | parser
    ).with_config({"run_name": "v2ai_rag_chain"})

    logger.info(
        "RAG chain built: retriever(top_k=%d) → context_assembler → prompt → llm → parser",
        top_k,
    )
    return chain


def build_rag_chain_with_sources(
    vectorstore: Any,
    llm: Any,
    top_k: int = 4,
) -> Any:
    """
    Build a RAG chain that also returns the source documents alongside the answer.
    Used when the caller needs citation metadata (timestamps, source filenames).

    Returns a Runnable that, given {"question": str}, returns:
        {"answer": str, "source_documents": list[Document]}
    """
    if vectorstore is None or llm is None:
        return None

    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": top_k},
    ).with_config({"run_name": "v2ai_faiss_retriever_with_sources"})

    context_assembler = RunnableLambda(_assemble_context).with_config(
        {"run_name": "v2ai_context_assembler_with_sources"}
    )

    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template=_RAG_PROMPT_TEMPLATE,
    ).with_config({"run_name": "v2ai_rag_prompt_with_sources"})

    named_llm = llm.with_config({"run_name": "v2ai_llm_generation_with_sources"})
    parser = StrOutputParser().with_config({"run_name": "v2ai_output_parser_with_sources"})

    def _run_with_sources(inputs: dict) -> dict:
        question = inputs["question"]
        docs = retriever.invoke(question)
        context_str = _assemble_context(docs)
        prompt_value = prompt.invoke({"context": context_str, "question": question})
        raw_answer = named_llm.invoke(prompt_value)
        answer = parser.invoke(raw_answer)
        return {"answer": answer, "source_documents": docs}

    return RunnableLambda(_run_with_sources).with_config(
        {"run_name": "v2ai_rag_chain_with_sources"}
    )
