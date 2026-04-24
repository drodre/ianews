from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

from ianews.db import ArticleRow, connect, list_articles

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OLLAMA_MODEL = "llama3.2"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


def articles_to_brief(rows: list[ArticleRow]) -> str:
    lines: list[str] = []
    for i, r in enumerate(rows, start=1):
        when = (r.published_at or r.fetched_at or "")[:10]
        lines.append(f"{i}. [{r.source_name}] ({when}) {r.title}")
        lines.append(f"   URL: {r.link}")
        if r.summary and r.summary.strip() and r.summary.strip() != r.title.strip():
            snip = r.summary.strip().replace("\n", " ")
            if len(snip) > 320:
                snip = snip[:317] + "…"
            lines.append(f"   Resumen feed: {snip}")
        lines.append("")
    return "\n".join(lines).strip()


def build_messages(
    brief: str,
    *,
    lang: str,
) -> tuple[str, str]:
    if lang.lower().startswith("es"):
        system = (
            "Eres un editor de tecnología especializado en inteligencia artificial. "
            "Recibes una lista de noticias recientes (título, fuente, enlace y a veces un resumen corto del feed). "
            "Produce un boletín claro y útil para un lector técnico."
        )
        user = (
            "A partir de las siguientes entradas, redacta:\n"
            "1) Un párrafo de **resumen ejecutivo** (5–8 frases) con los temas y tendencias que conectan varias noticias.\n"
            "2) Una lista de **puntos destacados** (viñetas): una línea por noticia relevante, con el titular y en una frase qué aporta.\n"
            "3) Al final, una sección **Enlaces** con cada URL en una línea (formato: `- [fuente] título — URL`).\n\n"
            "Si varias noticias tratan lo mismo, agrúpalas en un solo punto.\n"
            "Responde en español.\n\n"
            "--- Noticias ---\n\n"
            f"{brief}"
        )
    else:
        system = (
            "You are a technology editor focused on artificial intelligence. "
            "You receive a list of recent news items (title, source, link, sometimes a short feed summary). "
            "Produce a clear briefing for a technical reader."
        )
        user = (
            "From the items below, write:\n"
            "1) An **executive summary** paragraph (5–8 sentences) on cross-cutting themes.\n"
            "2) **Bullet highlights**: one line per relevant story (headline + one sentence on why it matters).\n"
            "3) A final **Links** section with each URL on its own line (`- [source] title — URL`).\n\n"
            "Group duplicates. Respond in English.\n\n"
            "--- Items ---\n\n"
            f"{brief}"
        )
    return system, user


def call_openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system: str,
    user: str,
    timeout: float = 120.0,
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    try:
        return str(data["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Respuesta inesperada de la API: {data!r}") from e


def call_ollama(
    *,
    base_url: str,
    model: str,
    system: str,
    user: str,
    timeout: float = 180.0,
) -> str:
    url = base_url.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    msg = data.get("message") or {}
    content = msg.get("content")
    if not content:
        raise RuntimeError(f"Respuesta inesperada de Ollama: {json.dumps(data)[:800]}")
    return str(content).strip()


def run_digest(
    db_path: Path,
    *,
    limit: int,
    source: str | None,
    provider: str,
    model: str | None,
    lang: str,
    api_key: str | None,
    base_url: str | None,
    ollama_url: str | None,
    timeout: float,
) -> str:
    if not db_path.is_file():
        raise FileNotFoundError(f"No existe la base de datos: {db_path}")
    conn = connect(db_path)
    try:
        rows = list_articles(conn, limit=limit, source=source)
    finally:
        conn.close()
    if not rows:
        raise ValueError("No hay artículos en la base de datos para este filtro.")
    brief = articles_to_brief(rows)
    system, user = build_messages(brief, lang=lang)
    prov = provider.strip().lower()
    if prov in ("openai", "openai-compatible"):
        key = api_key or os.environ.get("OPENAI_API_KEY", "").strip()
        if not key:
            raise ValueError(
                "Falta la clave API. Define OPENAI_API_KEY o usa --api-key. "
                "Para APIs compatibles, ajusta también --base-url si no es OpenAI."
            )
        m = model or os.environ.get("IANEWS_DIGEST_MODEL", "").strip() or DEFAULT_OPENAI_MODEL
        bu = (base_url or os.environ.get("OPENAI_BASE_URL", "").strip() or "https://api.openai.com/v1").rstrip("/")
        return call_openai_compatible(
            base_url=bu,
            api_key=key,
            model=m,
            system=system,
            user=user,
            timeout=timeout,
        )
    if prov == "ollama":
        m = model or os.environ.get("IANEWS_OLLAMA_MODEL", "").strip() or DEFAULT_OLLAMA_MODEL
        ou = (ollama_url or os.environ.get("OLLAMA_HOST", "").strip() or DEFAULT_OLLAMA_URL).rstrip("/")
        return call_ollama(base_url=ou, model=m, system=system, user=user, timeout=timeout)
    raise ValueError(f"Proveedor desconocido: {provider}. Usa openai u ollama.")
