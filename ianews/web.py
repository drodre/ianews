from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ianews.db import connect, list_articles


def _page(body: str, title: str = "ianews") -> bytes:
    doc = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      font-family: system-ui, sans-serif;
      line-height: 1.45;
      color: #e8e8ec;
      background: #121218;
    }}
    body {{ max-width: 52rem; margin: 2rem auto; padding: 0 1rem; }}
    h1 {{ font-size: 1.35rem; font-weight: 650; }}
    ul {{ list-style: none; padding: 0; margin: 0; }}
    li {{
      border-bottom: 1px solid #2a2a34;
      padding: 0.85rem 0;
    }}
    a {{ color: #8ab4ff; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .meta {{ font-size: 0.82rem; color: #9aa0b4; margin-top: 0.25rem; }}
    .tags {{ color: #7bdc9a; }}
    form {{ margin: 1rem 0; display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }}
    input[type="number"] {{ width: 4rem; background: #1c1c26; border: 1px solid #3a3a48; color: inherit; padding: 0.25rem 0.4rem; border-radius: 4px; }}
    button {{ background: #3d5afe; color: #fff; border: none; padding: 0.35rem 0.75rem; border-radius: 4px; cursor: pointer; }}
    button:hover {{ filter: brightness(1.08); }}
  </style>
</head>
<body>
{body}
</body>
</html>"""
    return doc.encode("utf-8")


def _make_handler(db_path: Path):
    class _NewsHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *log_args: object) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path not in ("/", ""):
                self.send_error(404, "Not Found")
                return
            qs = parse_qs(parsed.query)
            try:
                limit = int(qs.get("n", ["80"])[0])
            except ValueError:
                limit = 80
            limit = max(1, min(limit, 300))
            conn = connect(db_path)
            try:
                rows = list_articles(conn, limit=limit)
            finally:
                conn.close()
            items: list[str] = []
            for r in rows:
                when = html.escape((r.published_at or r.fetched_at)[:10])
                src = html.escape(r.source_name)
                title = html.escape(r.title)
                link = html.escape(r.link, quote=True)
                tags = html.escape((r.matched_keywords or "").replace(",", ", "))
                items.append(
                    f"<li><a href=\"{link}\" target=\"_blank\" rel=\"noopener\">{title}</a>"
                    f"<div class=\"meta\">{when} · {src}"
                    + (f' · <span class="tags">{tags}</span>' if tags else "")
                    + "</div></li>"
                )
            inner = (
                "<h1>ianews · últimas entradas</h1>"
                '<form method="get" action="/">'
                "<label>Cantidad <input type=\"number\" name=\"n\" value=\""
                f"{limit}"
                "\" min=\"1\" max=\"300\"/></label>"
                '<button type="submit">Actualizar</button>'
                "</form>"
                "<ul>" + "".join(items) + "</ul>"
            )
            data = _page(inner)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return _NewsHandler


def run_server(host: str, port: int, db_path: Path) -> None:
    if not db_path.is_file():
        raise FileNotFoundError(f"No existe la base de datos: {db_path}")
    handler = _make_handler(db_path)
    httpd = HTTPServer((host, port), handler)
    print(f"ianews sirviendo en http://{host}:{port}/ (Ctrl+C para salir)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrando.")
