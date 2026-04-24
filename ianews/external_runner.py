from __future__ import annotations

import os
import subprocess
from pathlib import Path

from ianews.config_loader import ExternalScriptSpec
from ianews.feeds import FeedEntry, load_entries_from_path


def synthetic_feed_url(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-._" else "-" for c in name.strip().lower())
    safe = "-".join(p for p in safe.split("-") if p)
    return f"external://{safe or 'script'}"


def run_external_script(
    spec: ExternalScriptSpec,
    *,
    timeout: float = 120.0,
) -> None:
    work = Path(spec.cwd) if spec.cwd else Path.cwd()
    work = work.resolve()
    env = os.environ.copy()
    proc = subprocess.run(
        spec.argv,
        cwd=str(work),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"código {proc.returncode}"
        raise RuntimeError(err)


def load_external_feed(
    spec: ExternalScriptSpec,
    *,
    run_first: bool = True,
    timeout: float = 120.0,
) -> list[FeedEntry]:
    if run_first:
        run_external_script(spec, timeout=timeout)
    work = Path(spec.cwd) if spec.cwd else Path.cwd()
    xml_path = Path(spec.xml)
    if not xml_path.is_absolute():
        xml_path = (work.resolve() / xml_path).resolve()
    if not xml_path.is_file():
        raise FileNotFoundError(f"No existe el XML del script externo: {xml_path}")
    return load_entries_from_path(xml_path)
