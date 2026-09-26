"""RAG quality evals: grounded, relevant answers over the JurisLab knowledge base.

Requires a running backend (make start) and a local Ollama model.
"""
from __future__ import annotations

import pytest
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase

from helpers import ask_over_knowledge, complete_llm

QUESTIONS = [
    "What are the main grounds for terminating a commercial agreement early?",
    "When is a party considered to be in material breach?",
    "What dispute-resolution options exist after a contract dispute arises?",
]

THRESHOLDS = {"answer_relevancy": 0.5, "faithfulness": 0.5}


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda q: q[:24].replace(" ", "_"))
def test_grounded_knowledge_answers(question: str) -> None:
    answer, contexts = ask_over_knowledge(question)
    assert contexts, "no retrieval context returned"

    case = LLMTestCase(
        input=question,
        actual_output=answer,
        retrieval_context=contexts,
    )
    relevancy = AnswerRelevancyMetric(threshold=THRESHOLDS["answer_relevancy"])
    faithfulness = FaithfulnessMetric(threshold=THRESHOLDS["faithfulness"])

    relevancy.measure(case)
    faithfulness.measure(case)

    assert relevancy.is_successful(), (
        f"answer_relevancy={relevancy.score} < {THRESHOLDS['answer_relevancy']}"
    )
    assert faithfulness.is_successful(), (
        f"faithfulness={faithfulness.score} < {THRESHOLDS['faithfulness']}"
    )


def test_contains_disclaimer_and_citation_pattern() -> None:
    """Cheap lexical guard so runs don't need two model hops per check."""
    prompt = (
        "Answer a legal-education question briefly. If you cannot verify a claim "
        "from sources, say 'I cannot verify' and include at least one citation marker."
    )
    out = complete_llm(prompt)
    assert len(out.strip()) > 20
    assert ("cannot verify" in out.lower()) or ("citation" in out.lower() and "(" in out)