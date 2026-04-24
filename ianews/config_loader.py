from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class SourceSpec:
    name: str
    feed_url: str | None = None
    site_url: str | None = None


@dataclass(frozen=True)
class ExternalScriptSpec:
    name: str
    argv: list[str]
    xml: str
    cwd: str | None = None


@dataclass(frozen=True)
class AppConfig:
    sources: list[SourceSpec]
    external_scripts: list[ExternalScriptSpec]
    # None = filtro IA integrado; () = guardar todos los ítems del feed; (a,b) = solo esas frases
    keywords: tuple[str, ...] | None


def load_config(path: Path) -> AppConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not raw or not isinstance(raw, dict):
        raise ValueError(f"Config vacío o inválido: {path}")
    items = raw.get("sources") or []
    sources: list[SourceSpec] = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or f"source-{i}")
        feed = it.get("feed_url")
        site = it.get("site_url")
        feed_s = str(feed).strip() if feed else None
        site_s = str(site).strip() if site else None
        if not feed_s and not site_s:
            continue
        sources.append(SourceSpec(name=name, feed_url=feed_s, site_url=site_s))
    ext_items = raw.get("external_scripts") or []
    external_scripts: list[ExternalScriptSpec] = []
    for i, it in enumerate(ext_items):
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or f"external-{i}")
        argv = it.get("argv")
        xml = it.get("xml")
        if not isinstance(argv, list) or not argv:
            continue
        argv_s = [str(x) for x in argv]
        xml_s = str(xml).strip() if xml else ""
        if not xml_s:
            continue
        cwd_raw = it.get("cwd")
        cwd_s = str(cwd_raw).strip() if cwd_raw else None
        external_scripts.append(
            ExternalScriptSpec(name=name, argv=argv_s, xml=xml_s, cwd=cwd_s or None),
        )
    if "keywords" not in raw:
        keywords: tuple[str, ...] | None = None
    else:
        kw = raw["keywords"]
        if kw is None:
            keywords = None
        elif isinstance(kw, list):
            keywords = tuple(str(x).strip() for x in kw if str(x).strip())
        else:
            keywords = (str(kw).strip(),) if str(kw).strip() else ()
    return AppConfig(sources=sources, external_scripts=external_scripts, keywords=keywords)
