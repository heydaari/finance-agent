import threading
import logging
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .logging_config import stage
from .settings import EMBEDDING_MODEL, MARKDOWN_DIR, VECTOR_DB_DIR


_index_lock = threading.Lock()
logger = logging.getLogger("cv_retrieval.indexer")


def _embeddings(request_id: str | None = None) -> HuggingFaceEndpointEmbeddings:
    import os

    token = os.getenv("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN is not set; it is required for online Hugging Face embeddings.")
    stage(logger, request_id, "embedding_client_initializing", model=EMBEDDING_MODEL)
    return HuggingFaceEndpointEmbeddings(
        model=EMBEDDING_MODEL,
        huggingfacehub_api_token=token,
    )


def _markdown_documents() -> list[Document]:
    documents = []
    for path in sorted(MARKDOWN_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if text:
            documents.append(Document(page_content=text, metadata={"source": path.name}))
    return documents


def build_index(request_id: str | None = None) -> FAISS:
    """Build an index from the local Markdown knowledge base."""
    markdown_files = list(MARKDOWN_DIR.glob("*.md")) if MARKDOWN_DIR.exists() else []
    stage(logger, request_id, "markdown_files_found", file_count=len(markdown_files))

    documents = _markdown_documents()
    if not documents:
        raise RuntimeError(f"No Markdown documents found in {MARKDOWN_DIR}")
    stage(logger, request_id, "markdown_loaded", document_count=len(documents))

    splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200)
    chunks = splitter.split_documents(documents)
    stage(logger, request_id, "documents_split", chunk_count=len(chunks))
    stage(logger, request_id, "embedding_documents_started", chunk_count=len(chunks))
    vector_db = FAISS.from_documents(chunks, _embeddings(request_id))
    stage(logger, request_id, "embedding_documents_finished")
    VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
    vector_db.save_local(str(VECTOR_DB_DIR))
    stage(logger, request_id, "vector_index_saved", path=str(VECTOR_DB_DIR))
    return vector_db


def get_or_create_index(request_id: str | None = None) -> FAISS:
    """Load the persisted index, or create it lazily on the first query."""
    index_file = VECTOR_DB_DIR / "index.faiss"
    metadata_file = VECTOR_DB_DIR / "index.pkl"
    with _index_lock:
        if index_file.exists() and metadata_file.exists():
            stage(logger, request_id, "vector_index_loading", path=str(VECTOR_DB_DIR))
            vector_db = FAISS.load_local(
                str(VECTOR_DB_DIR),
                _embeddings(request_id),
                allow_dangerous_deserialization=True,
            )
            stage(logger, request_id, "vector_index_loaded", path=str(VECTOR_DB_DIR))
            return vector_db
        stage(logger, request_id, "vector_index_missing_building")
        return build_index(request_id)
