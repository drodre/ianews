# ianews

Herramienta en línea de comandos que lee feeds **RSS/Atom** de blogs y sitios que configures, opcionalmente ejecuta **scripts externos** que generan un XML de tipo RSS (por ejemplo `external/noticias_ai_rss.py` para noticias.ai), filtra entradas relacionadas con **IA** (reglas por defecto en inglés y español, o palabras propias en YAML) y lo guarda todo en la **misma base SQLite**. Incluye un servidor local mínimo para ver los enlaces en el navegador.

## Requisitos

- Python 3.11+

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp config/sources.example.yaml config/sources.yaml
# Edita config/sources.yaml con tus feeds o site_url
```

## Uso

```bash
ianews fetch -c config/sources.yaml
ianews list -n 20
ianews serve --port 8765 --open
```

- Por cada fuente solo se procesan las **N entradas más recientes** (`--max-per-feed`, por defecto 80), ordenadas por fecha si el feed la trae.
- Base de datos por defecto: `data/ianews.db`. Otra ruta: variable `IANEWS_DB` o `ianews fetch --db /ruta/a.db`.
- Cada fuente necesita `feed_url` o `site_url` (se intenta descubrir el enlace `<link rel="alternate" …>`).
- Sin clave `keywords` en el YAML: filtro IA integrado. `keywords: []` guarda todas las entradas del feed. Lista no vacía: solo entradas que contengan alguna de esas frases.
- **`external_scripts`** (opcional): cada entrada tiene `name`, `argv` (lista, p. ej. `[python3, external/mi_script.py]`) y `xml` (ruta al fichero RSS generado). En cada `fetch` se ejecuta el comando y después se importan las entradas como una fuente más. Las dependencias del script van aparte (p. ej. en el mismo venv: `pip install requests beautifulsoup4`).

## Limitaciones

Los feeds HTTP deben ser RSS/Atom. Sitios sin feed pueden integrarse mediante un script externo que produzca XML compatible; el scraping concreto no va en el núcleo de ianews.
