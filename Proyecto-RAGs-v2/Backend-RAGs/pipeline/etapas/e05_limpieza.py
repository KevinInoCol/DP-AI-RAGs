"""
Pipeline de ingesta RAG · D · QUITAR BOILERPLATE (encabezados y pies)
Ruta: Backend-RAGs/pipeline/stages/d_boilerplate.py

Elimina encabezados, pies de página, numeración y avisos que se repiten en el
borde de muchas páginas y contaminan los chunks y el retrieval.

Tiene que servir para CUALQUIER cliente (retail, legal, finanzas, marketing…),
así que el principio es: ANTE LA DUDA, NO BORRAR. Perder un título o una
cláusula es peor que dejar un pie de página.

Técnica:
  1. Solo mira el BORDE de cada página (hasta 3 líneas arriba y 3 abajo, y como
     mucho ¼ de la página para que en páginas cortas el borde no sea todo).
  2. Compara con una CLAVE tolerante: sin Markdown (#, **, _), sin tildes, sin
     mayúsculas ni signos → "**BANCO XYZ**" == "Banco XYZ" y "Pagina" == "Página"
     (típico entre páginas nativas y páginas OCR).
  3. Dos formas de ser boilerplate:
       a) REPETICIÓN EXACTA de la clave en ≥ `min_ratio` de las páginas
          (encabezado corporativo, aviso de confidencialidad, título corriente).
       b) NUMERACIÓN: líneas que solo cambian en los números Y parecen número de
          página ("Página 3 de 40", "- 3 -", "3/40", "Page 3", "Folio 3"). Un
          número suelto solo cuenta si sube con la página (3, 4, 5…): así no se
          borran montos sueltos de un estado financiero.
          Una línea que cambia en los números pero tiene texto propio
          ("Artículo 5", "Cláusula 6", "Capítulo 7") NO se toca.
  4. Protecciones: nunca se borran filas de tabla (|…|), y los títulos Markdown
     solo se borran si se repiten EXACTOS (nunca por numeración).
  5. Requiere ≥ `min_pages` páginas (default 3): con menos no hay evidencia
     suficiente de qué es plantilla.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from typing import Any

DEFAULT_EDGE_LINES = 3      # líneas de borde a revisar arriba y abajo
DEFAULT_MIN_RATIO = 0.5     # fracción de páginas en las que debe repetirse
DEFAULT_MIN_PAGES = 3       # mínimo de páginas para intentar detectar algo

# Palabras que anuncian un número de página (es/en/pt, abreviadas o no).
_PAGE_WORDS = {"pagina", "pag", "pg", "p", "page", "pages", "hoja", "folio", "fojas", "de", "of", "del"}

_MD_DECOR = re.compile(r"^\s*(#{1,6}\s+|>\s*)|[*_`~]+")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")
_DIGITS = re.compile(r"\d+")


# --------------------------------------------------------------------------- #
# Claves de comparación
# --------------------------------------------------------------------------- #
def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _line_key(line: str) -> str:
    """Clave tolerante: sin Markdown, sin tildes, minúsculas, solo alfanumérico."""
    s = _MD_DECOR.sub(" ", line)
    s = _strip_accents(s).casefold()
    return _NON_ALNUM.sub(" ", s).strip()


def _is_table_row(line: str) -> bool:
    return line.lstrip().startswith("|")


def _is_heading(line: str) -> bool:
    return bool(re.match(r"^\s*#{1,6}\s", line))


def _looks_like_page_number(key: str) -> bool:
    """True si la línea es numeración: solo números + palabras de paginación.
    "pagina 3 de 40", "3", "3 40", "page 3 of 40", "folio 3" → True.
    "articulo 5", "clausula 6 obligaciones" → False (tienen texto propio)."""
    tokens = key.split()
    if not tokens or not any(t.isdigit() for t in tokens):
        return False
    return all(t.isdigit() or t in _PAGE_WORDS for t in tokens)


def _edge_indices(lines: list[str], edge_lines: int) -> set[int]:
    """Índices de las primeras/últimas líneas NO vacías. El borde nunca pasa de
    ¼ de la página (mínimo 1), para que en páginas cortas no cubra todo."""
    nonempty = [i for i, ln in enumerate(lines) if ln.strip()]
    k = max(1, min(edge_lines, len(nonempty) // 4))
    return set(nonempty[:k] + nonempty[-k:])


# --------------------------------------------------------------------------- #
# Detección y limpieza
# --------------------------------------------------------------------------- #
def detect_boilerplate(
    pages: list[str],
    *,
    edge_lines: int = DEFAULT_EDGE_LINES,
    min_ratio: float = DEFAULT_MIN_RATIO,
    min_pages: int = DEFAULT_MIN_PAGES,
) -> set[str]:
    """Claves de las líneas de borde que se repiten EXACTAS en suficientes páginas.
    (La numeración de página no necesita repetirse: se reconoce por su forma.)"""
    n = len(pages)
    if n < min_pages:
        return set()
    counter: Counter[str] = Counter()
    for text in pages:
        lines = text.split("\n")
        seen = {
            _line_key(lines[i])
            for i in _edge_indices(lines, edge_lines)
            if not _is_table_row(lines[i])
        }
        seen.discard("")
        counter.update(seen)
    threshold = max(min_pages, math.ceil(min_ratio * n))
    return {key for key, c in counter.items() if c >= threshold}


def _has_page_word(key: str) -> bool:
    return any(t in _PAGE_WORDS for t in key.split())


def _tracks_page_index(occurrences: list[tuple[int, int]]) -> bool:
    """True si el número sube con la página (número − índice constante en ≥ 80%).
    Distingue "3, 4, 5…" (paginación) de montos sueltos "1250, 980, 1250"."""
    offsets = Counter(num - idx for idx, num in occurrences)
    return offsets.most_common(1)[0][1] >= 0.8 * len(occurrences)


def detect_page_numbering(
    pages: list[str],
    *,
    edge_lines: int = DEFAULT_EDGE_LINES,
    min_ratio: float = DEFAULT_MIN_RATIO,
    min_pages: int = DEFAULT_MIN_PAGES,
) -> set[str]:
    """Patrones de numeración (números → '#') presentes en suficientes páginas.
    Con palabra de paginación ("página # de #") basta la repetición del patrón;
    si es un número suelto ("#", "- # -") además debe subir con la página."""
    n = len(pages)
    if n < min_pages:
        return set()
    seen_in: dict[str, list[tuple[int, int]]] = {}
    for idx, text in enumerate(pages):
        lines = text.split("\n")
        found: dict[str, int] = {}
        for i in _edge_indices(lines, edge_lines):
            key = _line_key(lines[i])
            if not _is_heading(lines[i]) and _looks_like_page_number(key):
                found.setdefault(_DIGITS.sub("#", key), int(_DIGITS.search(key).group()))
        for pat, num in found.items():
            seen_in.setdefault(pat, []).append((idx, num))
    threshold = max(min_pages, math.ceil(min_ratio * n))
    return {
        pat
        for pat, occ in seen_in.items()
        if len(occ) >= threshold and (_has_page_word(pat) or _tracks_page_index(occ))
    }


def remove_boilerplate(
    pages: list[str],
    *,
    edge_lines: int = DEFAULT_EDGE_LINES,
    min_ratio: float = DEFAULT_MIN_RATIO,
    min_pages: int = DEFAULT_MIN_PAGES,
) -> dict[str, Any]:
    """Quita el boilerplate detectado SOLO de los bordes de cada página.

    Devuelve {"pages": [...limpias...], "boilerplate": [...claves...], "removed_lines": int}.
    """
    repeated = detect_boilerplate(pages, edge_lines=edge_lines, min_ratio=min_ratio, min_pages=min_pages)
    numbering = detect_page_numbering(
        pages, edge_lines=edge_lines, min_ratio=min_ratio, min_pages=min_pages
    )

    cleaned: list[str] = []
    removed = 0
    for text in pages:
        lines = text.split("\n")
        edges = _edge_indices(lines, edge_lines)
        kept = []
        for i, ln in enumerate(lines):
            if i in edges and not _is_table_row(ln):
                key = _line_key(ln)
                is_numbering = (
                    not _is_heading(ln)
                    and _looks_like_page_number(key)
                    and _DIGITS.sub("#", key) in numbering
                )
                if key and (key in repeated or is_numbering):
                    removed += 1
                    continue
            kept.append(ln)
        cleaned.append("\n".join(kept).strip())
    return {
        "pages": cleaned,
        "boilerplate": sorted(repeated | numbering),
        "removed_lines": removed,
    }


# --------------------------------------------------------------------------- #
# Explicación didáctica (la muestra el frontend en "¿Cómo funciona?")
# --------------------------------------------------------------------------- #
EXPLAINED_STEPS: list[dict[str, str]] = [
    {
        "title": "Solo mira el borde de cada página",
        "detail": (
            "Revisa hasta 3 líneas arriba y 3 abajo (como mucho ¼ de la página, para "
            "que en páginas cortas el borde no sea toda la página). El cuerpo no se toca."
        ),
    },
    {
        "title": "Compara con tolerancia",
        "detail": (
            "Ignora Markdown, mayúsculas, tildes y signos. Así reconoce el mismo "
            "encabezado aunque una página sea nativa y otra venga de OCR."
        ),
        "before": "**BANCO XYZ · Confidencial**  vs  Banco Xyz - confidencial",
        "after": "misma línea",
    },
    {
        "title": "Borra lo que se repite exacto en ≥ 50% de las páginas",
        "detail": (
            "Encabezados corporativos, avisos de confidencialidad, títulos corrientes. "
            "Hacen falta al menos 3 páginas: con menos no hay evidencia de qué es plantilla."
        ),
        "before": "Banco XYZ · Documento confidencial\n…contenido…",
        "after": "…contenido…",
    },
    {
        "title": "Borra la numeración de página",
        "detail": (
            "Líneas que solo cambian en el número y tienen forma de paginación: "
            "«Página 3 de 40», «- 3 -», «3/40», «Page 3», «Folio 3». Un número suelto "
            "solo cuenta si sube página a página, para no borrar montos."
        ),
        "before": "…contenido…\nPágina 7 de 40",
        "after": "…contenido…",
    },
    {
        "title": "Protege títulos, cláusulas y tablas",
        "detail": (
            "Una línea que cambia en el número pero tiene texto propio NO se borra "
            "(«Artículo 5», «Cláusula 6», «Capítulo 7»). Las filas de tabla nunca se "
            "borran, y los títulos Markdown solo si se repiten exactos."
        ),
        "before": "## Artículo 5 · Artículo 6 · Artículo 7 (arriba de cada página)",
        "after": "se conservan",
    },
]

NOT_DONE = (
    "No borra nada del cuerpo de la página ni texto que aparezca en menos de la mitad "
    "de las páginas, y no actúa en documentos de menos de 3 páginas. Las marcas de agua "
    "en el centro de la página no se detectan aquí."
)
