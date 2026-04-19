from __future__ import annotations

import time
from functools import lru_cache
from typing import Any

try:
    import torch
except ImportError:  # pragma: no cover - fallback for environments without torch
    torch = None

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFacePipeline
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline

from app.config import Settings, load_settings


class RAGService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.settings.hf_embedding_model,
            model_kwargs={"device": "cuda" if self._use_cuda() else "cpu"},
        )
        self.vector_store = self._load_or_build_vector_store(force_rebuild=False)
        self.retriever = self.vector_store.as_retriever(
            search_kwargs={"k": self.settings.retrieval_k}
        )
        self.llm = self._build_generation_llm()
        self.chain = self._build_chain()

    def _use_cuda(self) -> bool:
        return bool(
            self.settings.use_gpu and torch is not None and torch.cuda.is_available()
        )

    def _collect_documents(self) -> list[Document]:
        documents: list[Document] = []
        allowed_suffixes = {".txt", ".md"}

        knowledge_path = self.settings.knowledge_base_path
        if not knowledge_path.exists():
            raise FileNotFoundError(
                f"Knowledge base folder does not exist: {knowledge_path}"
            )

        for file_path in knowledge_path.rglob("*"):
            if not file_path.is_file() or file_path.suffix.lower() not in allowed_suffixes:
                continue
            content = file_path.read_text(encoding="utf-8")
            if not content.strip():
                continue
            documents.append(
                Document(
                    page_content=content,
                    metadata={
                        "source": str(file_path.as_posix()),
                    },
                )
            )

        if not documents:
            raise RuntimeError(
                f"No .txt/.md documents found in knowledge base: {knowledge_path}"
            )
        return documents

    def _split_documents(self, documents: list[Document]) -> list[Document]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=700,
            chunk_overlap=120,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        return splitter.split_documents(documents)

    def _load_or_build_vector_store(self, force_rebuild: bool) -> FAISS:
        vector_path = self.settings.vector_store_path
        index_file = vector_path / "index.faiss"

        if index_file.exists() and not force_rebuild:
            return FAISS.load_local(
                folder_path=str(vector_path),
                embeddings=self.embeddings,
                allow_dangerous_deserialization=True,
            )

        docs = self._collect_documents()
        chunks = self._split_documents(docs)

        vector_store = FAISS.from_documents(chunks, self.embeddings)
        vector_path.mkdir(parents=True, exist_ok=True)
        vector_store.save_local(str(vector_path))
        return vector_store

    def _build_generation_llm(self) -> HuggingFacePipeline:
        model_name = self.settings.hf_generation_model
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

        generator = pipeline(
            task="text2text-generation",
            model=model,
            tokenizer=tokenizer,
            device=0 if self._use_cuda() else -1,
            max_new_tokens=self.settings.generation_max_tokens,
            temperature=self.settings.generation_temperature,
            do_sample=True,
        )
        return HuggingFacePipeline(pipeline=generator)

    def _build_chain(self):
        prompt = PromptTemplate.from_template(
            """
You are an AI assistant for an MLOps project team.
Use ONLY the retrieved context to answer.
If the answer is not in context, say: "I cannot find this in the current project knowledge base.".

Context:
{context}

Question:
{question}

Answer:
""".strip()
        )

        def _format_docs(docs: list[Document]) -> str:
            return "\n\n".join(doc.page_content for doc in docs)

        chain = (
            {
                "context": self.retriever | RunnableLambda(_format_docs),
                "question": RunnablePassthrough(),
            }
            | prompt
            | self.llm
            | StrOutputParser()
        )
        return chain

    def answer_question(self, question: str) -> dict[str, Any]:
        start = time.perf_counter()

        docs = self.retriever.invoke(question)
        answer = str(self.chain.invoke(question)).strip()
        latency_ms = (time.perf_counter() - start) * 1000.0

        sources = sorted({doc.metadata.get("source", "unknown") for doc in docs})

        return {
            "question": question,
            "answer": answer,
            "sources": sources,
            "latency_ms": round(latency_ms, 2),
            "question_length": len(question),
            "answer_length": len(answer),
            "model_name": self.settings.hf_generation_model,
        }

    def rebuild_index(self) -> None:
        self.vector_store = self._load_or_build_vector_store(force_rebuild=True)
        self.retriever = self.vector_store.as_retriever(
            search_kwargs={"k": self.settings.retrieval_k}
        )
        self.chain = self._build_chain()


@lru_cache(maxsize=1)
def get_rag_service() -> RAGService:
    return RAGService(settings=load_settings())
