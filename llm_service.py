# -*- coding: utf-8 -*-
"""LLM client for the tool-calling agent."""
from __future__ import annotations

import logging

import config

logger = logging.getLogger(__name__)

_llm = None


def _build_groq_llm():
    from langchain_groq import ChatGroq

    if not config.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Get a free key at https://console.groq.com/keys, "
            "then set GROQ_API_KEY in Railway Variables."
        )
    logger.info("Initializing Groq model %s", config.GROQ_MODEL)
    return ChatGroq(model=config.GROQ_MODEL, temperature=0, api_key=config.GROQ_API_KEY)


def _build_gemini_llm():
    from langchain_google_genai import ChatGoogleGenerativeAI

    if not config.GOOGLE_API_KEY:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Set it in Railway Variables or use LLM_PROVIDER=groq."
        )
    logger.info("Initializing Gemini model %s", config.GEMINI_MODEL)
    return ChatGoogleGenerativeAI(
        model=config.GEMINI_MODEL, temperature=0, google_api_key=config.GOOGLE_API_KEY
    )


def get_llm():
    """Lazy singleton — built on first use so deploy boot is lighter."""
    global _llm
    if _llm is None:
        provider = (config.LLM_PROVIDER or "groq").lower()
        if provider == "groq":
            _llm = _build_groq_llm()
        elif provider == "gemini":
            _llm = _build_gemini_llm()
        else:
            raise RuntimeError(
                f"Unknown LLM_PROVIDER '{config.LLM_PROVIDER}'. Use 'groq' or 'gemini'."
            )
    return _llm


# Backwards-compatible attribute used by agent.py: llm_service.llm
class _LLMProxy:
    def __getattr__(self, name):
        return getattr(get_llm(), name)

    def bind_tools(self, *args, **kwargs):
        return get_llm().bind_tools(*args, **kwargs)

    def invoke(self, *args, **kwargs):
        return get_llm().invoke(*args, **kwargs)


llm = _LLMProxy()
