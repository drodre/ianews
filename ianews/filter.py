from __future__ import annotations

import re
from functools import lru_cache

# (regex pattern, etiqueta corta para mostrar / guardar)
DEFAULT_RULES: tuple[tuple[str, str], ...] = (
    (r"\bai\b", "AI"),
    (r"\bartificial intelligence\b", "artificial intelligence"),
    (r"\bmachine learning\b", "machine learning"),
    (r"\bdeep learning\b", "deep learning"),
    (r"\bneural (?:network|net)\b", "neural network"),
    (r"\bllm\b", "LLM"),
    (r"\blarge language model\b", "large language model"),
    (r"\bgenerative ai\b", "generative AI"),
    (r"\bgenai\b", "GenAI"),
    (r"\bchatgpt\b", "ChatGPT"),
    (r"\bopenai\b", "OpenAI"),
    (r"\bclaude\b", "Claude"),
    (r"\bgemini\b", "Gemini"),
    (r"\btransformer\b", "transformer"),
    (r"\bnlp\b", "NLP"),
    (r"\bcomputer vision\b", "computer vision"),
    (r"\bfoundation model\b", "foundation model"),
    (r"\bmultimodal\b", "multimodal"),
    (r"\bagentic\b", "agentic"),
    (r"\bagi\b", "AGI"),
    (r"inteligencia artificial", "inteligencia artificial"),
    (r"aprendizaje automático", "aprendizaje automático"),
    (r"aprendizaje profundo", "aprendizaje profundo"),
    (r"modelo de lenguaje", "modelo de lenguaje"),
    (r"redes? neuronales?", "red neuronal"),
)


@lru_cache
def _compiled_rules(
    rules: tuple[tuple[str, str], ...],
) -> tuple[tuple[re.Pattern[str], str], ...]:
    return tuple((re.compile(p, re.IGNORECASE), label) for p, label in rules)


def _rules_from_keywords(keywords: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    out: list[tuple[str, str]] = []
    for k in keywords:
        k = k.strip()
        if not k:
            continue
        out.append((re.escape(k), k))
    return tuple(out)


def match_keywords(
    text: str,
    keywords: tuple[str, ...] | None = None,
) -> list[str]:
    """
    keywords=None: reglas IA por defecto.
    keywords=tuple no vacío: solo esas frases (literal, case-insensitive).
    """
    if not text or not text.strip():
        return []
    if keywords is None:
        rules = DEFAULT_RULES
    else:
        rules = _rules_from_keywords(keywords)
    hay = text
    matched: list[str] = []
    for pat, label in _compiled_rules(rules):
        if pat.search(hay):
            matched.append(label)
    return matched


def should_include(
    text: str,
    keywords: tuple[str, ...] | None,
) -> bool:
    """None = filtro IA por defecto; () = incluir todo; resto = filtro personalizado."""
    if keywords is not None and len(keywords) == 0:
        return True
    return len(match_keywords(text, keywords)) > 0
