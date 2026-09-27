"""Evaluation Agent: asks an LLM to score ONE supplier against the active criteria.

The agent only produces a raw JSON *judgement* (scores, justification, evidence).
It never calculates weighted totals, benchmarks, tie-breaks or ranks.

Providers
---------
openai     - OpenAI API, or any OpenAI-compatible endpoint (Groq, OpenRouter, Together,
             local Ollama) via LLM_BASE_URL. Uses JSON mode + temperature 0.
anthropic  - Anthropic Claude API. temperature 0.
mock       - Offline, deterministic keyword evaluator. No API key needed. Used for
             tests, reproducible demos and as a safe fallback. Clearly labelled in the UI.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from rfp.config import DEFAULT_MODELS
from rfp.prompts import SYSTEM_PROMPT, build_repair_prompt, build_user_prompt


class LLMError(Exception):
    """Raised when the LLM provider call itself fails (auth, network, quota)."""


@dataclass
class LLMSettings:
    provider: str = "mock"
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.0

    def resolved_model(self) -> str:
        return self.model or DEFAULT_MODELS.get(self.provider, "")


@dataclass
class EvaluationRequest:
    supplier_name: str
    document_text: str
    criteria: list[dict]
    history: list[dict] = field(default_factory=list)  # prior (assistant, error) turns


# ------------------------------------------------------------------ providers
def _call_openai(settings: LLMSettings, messages: list[dict]) -> str:
    from openai import OpenAI

    client = OpenAI(
        api_key=settings.api_key or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY"),
        base_url=settings.base_url or None,
        timeout=120,
        max_retries=6,  # backs off on 429 rate limits (Groq free tier has low tokens/minute)
    )
    kwargs = dict(model=settings.resolved_model(), temperature=settings.temperature,
                  messages=[{"role": "system", "content": SYSTEM_PROMPT}, *messages])
    try:
        resp = client.chat.completions.create(response_format={"type": "json_object"}, **kwargs)
    except Exception as exc:
        # Some OpenAI-compatible servers do not support response_format; retry without it.
        if "response_format" in str(exc) or "json_object" in str(exc):
            resp = client.chat.completions.create(**kwargs)
        else:
            raise
    return resp.choices[0].message.content or ""


def _call_anthropic(settings: LLMSettings, messages: list[dict]) -> str:
    import anthropic

    client = anthropic.Anthropic(
        api_key=settings.api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("LLM_API_KEY"),
        timeout=120,
        max_retries=6,
    )
    resp = client.messages.create(
        model=settings.resolved_model(), max_tokens=4000, temperature=settings.temperature,
        system=SYSTEM_PROMPT, messages=messages,
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


def _call_mock(req: EvaluationRequest) -> str:
    from rfp.agents.mock_llm import mock_evaluate

    return json.dumps(mock_evaluate(req.supplier_name, req.document_text, req.criteria))


# ------------------------------------------------------------------ public API
def build_messages(req: EvaluationRequest) -> list[dict]:
    messages = [{"role": "user",
                 "content": build_user_prompt(req.supplier_name, req.document_text, req.criteria)}]
    for turn in req.history:
        messages.append({"role": "assistant", "content": turn["output"] or "(empty)"})
        messages.append({"role": "user", "content": build_repair_prompt(turn["output"], turn["error"])})
    return messages


def run_evaluation(req: EvaluationRequest, settings: LLMSettings) -> str:
    """Return the model's raw text output. Parsing/validation is the Validation Tool's job."""
    try:
        if settings.provider == "mock":
            return _call_mock(req)
        messages = build_messages(req)
        if settings.provider == "openai":
            return _call_openai(settings, messages)
        if settings.provider == "anthropic":
            return _call_anthropic(settings, messages)
        raise LLMError(f"Unknown LLM provider '{settings.provider}'.")
    except LLMError:
        raise
    except Exception as exc:
        msg = re.sub(r"(sk|gsk|key)[-_A-Za-z0-9]{12,}", "***", str(exc))  # never leak keys
        raise LLMError(f"{settings.provider} call failed: {type(exc).__name__}: {msg}") from exc
