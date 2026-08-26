"""Test the finance retrieval endpoint with five Persian-topic questions."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ENDPOINT = os.getenv("RETRIEVAL_ENDPOINT", "http://127.0.0.1:8000/search")
QUESTIONS = [
    "شاخص RSI چگونه برای شناسایی اشباع خرید استفاده می‌شود؟",
    "تفاوت تحلیل فاندامنتال و تحلیل تکنیکال چیست؟",
    "هاوینگ بیت‌کوین چه اثری بر عرضه دارد؟",
    "چگونه حد ضرر و اندازه موقعیت را تعیین کنیم؟",
    "نسبت P/E در ارزیابی سهام چه کاربردی دارد؟",
]


def search(query: str) -> dict:
    payload = json.dumps({"query": query, "k": 5}).encode("utf-8")
    request = Request(
        ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    print(f"Testing retrieval endpoint: {ENDPOINT}\n")
    for number, question in enumerate(QUESTIONS, start=1):
        print(f"{number}. {question}")
        try:
            response = search(question)
            results = response.get("results", [])
            if not results:
                print("   No knowledge-base results returned.\n")
                continue

            top_result = results[0]
            content = " ".join(top_result.get("content", "").split())
            print(f"   Most relevant source: {top_result.get('source')}")
            print(f"   Score: {top_result.get('score')}")
            print(f"   Match: {content[:250]}...\n")
        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            print(f"   Endpoint returned HTTP {error.code}: {details}\n")
        except URLError as error:
            print(f"   Could not reach the endpoint: {error.reason}\n")


if __name__ == "__main__":
    main()
