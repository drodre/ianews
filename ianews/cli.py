from __future__ import annotations

import os
import webbrowser
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.table import Table

from ianews.config_loader import SourceSpec, load_config
from ianews.db import list_articles, list_sources, session, upsert_source, insert_article
from ianews.external_runner import load_external_feed, synthetic_feed_url
from ianews.feeds import discover_feed_url, fetch_feed_latest, take_latest_entries
from ianews.filter import match_keywords, should_include
from ianews.digest import articles_to_brief, build_messages, run_digest

app = typer.Typer(no_args_is_help=True, help="Agregador de noticias sobre IA (RSS/Atom + SQLite).")
console = Console()


def _default_db_path() -> Path:
    env = os.environ.get("IANEWS_DB")
    if env:
        return Path(env).expanduser()
    return Path.cwd() / "data" / "ianews.db"


def _resolve_feed_url(spec: SourceSpec) -> str:
    if spec.feed_url:
        return spec.feed_url
    if spec.site_url:
        found = discover_feed_url(spec.site_url)
        if not found:
            raise typer.BadParameter(
                f"No se encontró feed RSS/Atom en {spec.site_url}. Añade feed_url manualmente en el YAML."
            )
        return found
    raise typer.BadParameter("Cada fuente necesita feed_url o site_url.")


def _keyword_tags(text: str, cfg_keywords: tuple[str, ...] | None) -> list[str]:
    if cfg_keywords is not None and len(cfg_keywords) == 0:
        return match_keywords(text, None)
    return match_keywords(text, cfg_keywords)


@app.command()
def fetch(
    config: Path = typer.Option(
        Path("config/sources.yaml"),
        "--config",
        "-c",
        exists=True,
        dir_okay=False,
        readable=True,
        help="YAML con fuentes (ver config/sources.example.yaml).",
    ),
    db: Path | None = typer.Option(None, "--db", help="Ruta a la base SQLite (por defecto data/ianews.db)."),
    max_per_feed: int = typer.Option(
        80,
        "--max-per-feed",
        min=1,
        max=500,
        help="Solo procesa las N entradas más recientes de cada feed (orden del XML).",
    ),
) -> None:
    """Descarga feeds, filtra por IA y guarda en SQLite."""
    cfg = load_config(config)
    if not cfg.sources and not cfg.external_scripts:
        console.print("[red]No hay fuentes ni external_scripts en el archivo de configuración.[/red]")
        raise typer.Exit(code=1)
    db_path = db or _default_db_path()
    added = 0
    errors: list[str] = []
    with session(db_path) as conn:
        for spec in cfg.sources:
            try:
                feed_url = _resolve_feed_url(spec)
                sid = upsert_source(conn, spec.name, feed_url)
                entries = fetch_feed_latest(feed_url, limit=max_per_feed)
            except Exception as e:
                errors.append(f"{spec.name}: {e}")
                continue
            for ent in entries:
                blob = f"{ent.title}\n{ent.summary or ''}"
                if not should_include(blob, cfg.keywords):
                    continue
                tags = _keyword_tags(blob, cfg.keywords)
                if insert_article(
                    conn,
                    sid,
                    ent.title,
                    ent.link,
                    ent.summary,
                    ent.published,
                    tags,
                ):
                    added += 1
        for ext in cfg.external_scripts:
            try:
                entries = load_external_feed(ext, timeout=120.0)
                entries = take_latest_entries(entries, max_per_feed)
                sid = upsert_source(conn, ext.name, synthetic_feed_url(ext.name))
            except Exception as e:
                errors.append(f"{ext.name} (externo): {e}")
                continue
            for ent in entries:
                blob = f"{ent.title}\n{ent.summary or ''}"
                if not should_include(blob, cfg.keywords):
                    continue
                tags = _keyword_tags(blob, cfg.keywords)
                if insert_article(
                    conn,
                    sid,
                    ent.title,
                    ent.link,
                    ent.summary,
                    ent.published,
                    tags,
                ):
                    added += 1
    console.print(f"[green]Artículos nuevos guardados:[/green] {added}")
    if errors:
        console.print("[yellow]Avisos por fuente:[/yellow]")
        for e in errors:
            console.print(f"  • {e}")


@app.command("list")
def list_cmd(
    limit: int = typer.Option(30, "--limit", "-n", min=1, max=500),
    source: str | None = typer.Option(None, "--source", "-s", help="Filtrar por nombre de fuente o URL del feed."),
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Muestra las últimas noticias en la terminal."""
    db_path = db or _default_db_path()
    if not db_path.is_file():
        console.print(f"[red]No existe la base de datos {db_path}. Ejecuta `ianews fetch` primero.[/red]")
        raise typer.Exit(code=1)
    with session(db_path) as conn:
        rows = list_articles(conn, limit=limit, source=source)
    if not rows:
        console.print("No hay artículos (o el filtro no coincide).")
        raise typer.Exit(code=0)
    table = Table(show_header=True, header_style="bold")
    table.add_column("Fecha", max_width=12)
    table.add_column("Fuente", max_width=14)
    table.add_column("Título", max_width=48)
    table.add_column("Etiquetas", max_width=24)
    for r in rows:
        when = (r.published_at or r.fetched_at)[:10]
        tags = (r.matched_keywords or "").replace(",", ", ")[:24]
        table.add_row(when, r.source_name, r.title, tags)
    console.print(table)
    console.print("\n[dim]Enlaces: usa `ianews serve` o la columna link en export.[/dim]")


@app.command()
def sources(
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Lista fuentes registradas en la base de datos."""
    db_path = db or _default_db_path()
    if not db_path.is_file():
        console.print(f"[red]No existe {db_path}.[/red]")
        raise typer.Exit(code=1)
    with session(db_path) as conn:
        src = list_sources(conn)
    for r in src:
        console.print(f"• [bold]{r['name']}[/bold]\n  {r['feed_url']}")


@app.command()
def digest(
    limit: int = typer.Option(35, "--limit", "-n", min=1, max=200, help="Número de entradas recientes a enviar al modelo."),
    source: str | None = typer.Option(None, "--source", "-s", help="Solo artículos de esta fuente (nombre o feed_url)."),
    provider: str = typer.Option(
        "openai",
        "--provider",
        "-p",
        help="openai (API compatible Chat Completions) u ollama (servidor local).",
    ),
    model: str | None = typer.Option(None, "--model", "-m", help="Modelo (p. ej. gpt-4o-mini, llama3.2)."),
    lang: str = typer.Option("es", "--lang", "-l", help="es o en (instrucciones y tono del boletín)."),
    api_key: str | None = typer.Option(None, "--api-key", help="Sobrescribe OPENAI_API_KEY (no recomendado en shell compartido)."),
    base_url: str | None = typer.Option(None, "--base-url", help="Base URL API OpenAI-compatible (por defecto OPENAI_BASE_URL o api.openai.com)."),
    ollama_url: str | None = typer.Option(None, "--ollama-url", help="URL base de Ollama (por defecto http://127.0.0.1:11434)."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Guardar el texto en un fichero (UTF-8)."),
    context_only: bool = typer.Option(False, "--context-only", help="Solo imprime el texto enviado al modelo (sin llamar al LLM)."),
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Genera un boletín/resumen con un LLM a partir de las entradas en SQLite."""
    db_path = db or _default_db_path()
    if not db_path.is_file():
        console.print(f"[red]No existe la base de datos {db_path}. Ejecuta `ianews fetch` primero.[/red]")
        raise typer.Exit(code=1)
    if context_only:
        with session(db_path) as conn:
            rows = list_articles(conn, limit=limit, source=source)
        if not rows:
            console.print("[yellow]No hay artículos.[/yellow]")
            raise typer.Exit(code=1)
        system, user = build_messages(articles_to_brief(rows), lang=lang)
        console.print("[bold]--- system ---[/bold]\n")
        console.print(system)
        console.print("\n[bold]--- user ---[/bold]\n")
        console.print(user)
        raise typer.Exit(code=0)
    try:
        text = run_digest(
            db_path,
            limit=limit,
            source=source,
            provider=provider,
            model=model,
            lang=lang,
            api_key=api_key,
            base_url=base_url,
            ollama_url=ollama_url,
            timeout=180.0,
        )
    except (ValueError, FileNotFoundError) as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)
    except httpx.HTTPStatusError as e:
        body = (e.response.text or "")[:500]
        console.print(f"[red]Error HTTP {e.response.status_code}:[/red] {body}")
        raise typer.Exit(code=1)
    except httpx.RequestError as e:
        console.print(f"[red]Error de red:[/red] {e}")
        raise typer.Exit(code=1)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)
    if output:
        output.write_text(text + "\n", encoding="utf-8")
        console.print(f"[green]Guardado en[/green] {output}")
    console.print(text)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(10101, "--port", "-p"),
    db: Path | None = typer.Option(None, "--db"),
    open_browser: bool = typer.Option(False, "--open", "-o", help="Abrir el navegador al arrancar."),
) -> None:
    """Sirve una página HTML sencilla con las últimas noticias."""
    from ianews.web import run_server

    db_path = db or _default_db_path()
    if open_browser:
        webbrowser.open(f"http://{host}:{port}/")
    run_server(host, port, db_path)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
