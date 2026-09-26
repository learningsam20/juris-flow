"""Shared helpers for DeepEval test cases that exercise the live JurisLab API."""
from __future__ import annotations

import os
import uuid

import httpx

API_BASE = os.environ.get("JAIL_API_BASE", "http://localhost:5273/api/v1")
OLLAMA_MODEL = os.environ.get("JAIL_OLLAMA_MODEL", "granite4.2:8b")
OLLAMA_API = os.environ.get("JAIL_OLLAMA_API", "http://localhost:11434")


def _raise_if_api_down() -> None:
    try:
        httpx.get(f"{API_BASE}/health", timeout=3)
    except httpx.HTTPError:
        raise RuntimeError(
            "JurisLab API not reachable. Start it first (make start). "
            "Eval tests run against a live backend."
        )


def register_and_login(email: str | None = None) -> dict:
    """Register a fresh org-admin user and return auth headers."""
    _raise_if_api_down()
    email = email or f"eval-{uuid.uuid4().hex[:10]}@jurislab.test"
    client = httpx.Client(base_url=API_BASE, timeout=60)
    r = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "S3curePass!x9",
            "organization_name": f"Eval Org {uuid.uuid4().hex[:6]}",
        },
    )
    r.raise_for_status()
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def complete_llm(prompt: str) -> str:
    """Call the local LLM (Ollama, OpenAI-compatible) and return the text."""
    r = httpx.post(
        f"{OLLAMA_API}/v1/chat/completions",
        json={
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def ask_over_knowledge(question: str) -> tuple[str, list[str]]:
    """Dispatch a question to the live API and return (answer, retrieval_context)."""
    headers = register_and_login()
    retrieved = httpx.post(
        f"{API_BASE}/knowledge/search",
        headers=headers,
        json={"query": question, "top_k": 3},
        timeout=30,
    )
    retrieved.raise_for_status()
    contexts = [h["text"] for h in retrieved.json()["results"]]
    if not contexts:
        return "No relevant documents found in the knowledge base.", []
    prompt = (
        "Answer the legal-education question using ONLY the documents below. "
        "If the answer is not grounded in them, say so.\n\nSOURCE DOCUMENTS:\n"
        + "\n---\n".join(contexts)
        + f"\n\nQUESTION: {question}\nANSWER:"
    )
    answer = complete_llm(prompt)
    return answer, contexts