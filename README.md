# ianews

Herramienta en línea de comandos que lee feeds **RSS/Atom** de blogs y sitios que configures, opcionalmente ejecuta **scripts externos** que generan un XML de tipo RSS (por ejemplo `external/noticias_ai_rss.py` para noticias.ai), filtra entradas relacionadas con **IA** (reglas por defecto en inglés y español, o palabras propias en YAML) y lo guarda todo en la **misma base SQLite**. Incluye un servidor local mínimo para ver los enlaces en el navegador.

## Requisitos

- Python 3.11+

## Instalación

En la raíz del repositorio (donde está `pyproject.toml`):

```bash
python3 -m venv .venv
```

Activa el entorno (en **fish** usa `activate.fish`, no `activate` de bash):

```bash
# bash / zsh
source .venv/bin/activate

# fish
source .venv/bin/activate.fish
```

Instala el paquete en modo editable (esto crea el comando `ianews` dentro de `.venv/bin/`):

```bash
pip install -e .
cp config/sources.example.yaml config/sources.yaml
# Edita config/sources.yaml con tus feeds o site_url
```

Si ves `Unknown command: ianews`, casi siempre es porque **no** has hecho `pip install -e .` o **no** tienes activado el venv (el ejecutable está en `.venv/bin/ianews`).

Sin activar el venv puedes usar:

```bash
.venv/bin/pip install -e .
.venv/bin/ianews fetch -c config/sources.yaml
```

O, equivalente, sin depender del script de consola:

```bash
.venv/bin/python -m ianews fetch -c config/sources.yaml
```

## Uso

```bash
ianews fetch -c config/sources.yaml
ianews list -n 20
ianews serve --port 8765 --open
```

### Boletín con un LLM (`digest`)

Tras `fetch`, puedes pedir un resumen agrupado de las últimas entradas guardadas en SQLite:

```bash
export OPENAI_API_KEY=sk-...
ianews digest -n 35 -o boletin.md
```

- **OpenAI** (o cualquier API compatible con `/v1/chat/completions`): por defecto `https://api.openai.com/v1` y modelo `gpt-4o-mini`. Variables opcionales: `OPENAI_BASE_URL`, `IANEWS_DIGEST_MODEL`.
- **Ollama** en local: `ianews digest --provider ollama -m llama3.2` (servidor en `http://127.0.0.1:11434`, configurable con `--ollama-url` o `OLLAMA_HOST`).
- **`--context-only`**: muestra el texto que se enviaría al modelo sin llamar a la API (útil para depurar o para pegarlo en otro chat).

- Por cada fuente solo se procesan las **N entradas más recientes** (`--max-per-feed`, por defecto 80), ordenadas por fecha si el feed la trae.
- Base de datos por defecto: `data/ianews.db`. Otra ruta: variable `IANEWS_DB` o `ianews fetch --db /ruta/a.db`.
- Cada fuente necesita `feed_url` o `site_url` (se intenta descubrir el enlace `<link rel="alternate" …>`).
- Sin clave `keywords` en el YAML: filtro IA integrado. `keywords: []` guarda todas las entradas del feed. Lista no vacía: solo entradas que contengan alguna de esas frases.
- **`external_scripts`** (opcional): cada entrada tiene `name`, `argv` (lista, p. ej. `[python3, external/mi_script.py]`) y `xml` (ruta al fichero RSS generado). En cada `fetch` se ejecuta el comando y después se importan las entradas como una fuente más. Las dependencias del script van aparte (p. ej. en el mismo venv: `pip install requests beautifulsoup4`).

## Limitaciones

Los feeds HTTP deben ser RSS/Atom. Sitios sin feed pueden integrarse mediante un script externo que produzca XML compatible; el scraping concreto no va en el núcleo de ianews.
