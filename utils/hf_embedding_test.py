"""Smoke test for online Hugging Face embeddings through LangChain."""

import os

from langchain_huggingface import HuggingFaceEndpointEmbeddings


MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
SAMPLES = [
    "بانک مرکزی برای کنترل تورم نرخ بهره را افزایش داد.",
    "شرکت درآمد فصلی بالاتری از انتظار بازار گزارش کرد.",
    "با افزایش نرخ بهره، قیمت اوراق قرضه معمولاً کاهش می‌یابد.",
    "تنوع‌بخشی می‌تواند ریسک سبد سرمایه‌گذاری را کاهش دهد.",
    "مدیریت اندازه موقعیت از زیان‌های بزرگ جلوگیری می‌کند.",
]


def main() -> None:
    token = os.getenv("HF_TOKEN")
    if not token:
        raise SystemExit("HF_TOKEN is not set. Set it before running this script.")

    embeddings = HuggingFaceEndpointEmbeddings(
        model=MODEL,
        huggingfacehub_api_token=token,
    )

    try:
        vectors = embeddings.embed_documents(SAMPLES)
    except Exception as error:
        raise SystemExit(f"Hugging Face embedding request failed: {error}") from error

    print(f"Model: {MODEL}")
    print(f"Embedded {len(vectors)} samples; vector size: {len(vectors[0])}")
    for sample, vector in zip(SAMPLES, vectors):
        preview = ", ".join(f"{value:.6f}" for value in vector[:5])
        print(f"- {sample}\n  first 5 values: [{preview}, ...]")


if __name__ == "__main__":
    main()
