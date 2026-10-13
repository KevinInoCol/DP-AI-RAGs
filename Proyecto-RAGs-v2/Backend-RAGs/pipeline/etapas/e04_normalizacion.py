"""
Pipeline de ingesta RAG · 04 · NORMALIZAR TEXTO
Ruta: Backend-RAGs/pipeline/etapas/e04_normalizacion.py

Paso 2 del pipeline: limpia la suciedad tipográfica que traen los PDFs y que
degrada los embeddings, SIN romper la estructura Markdown de pymupdf4llm
(headers #, tablas |, listas -).

Qué hace:
  - Unicode NFKC        -> arregla ligaduras (fi/fl), comillas/espacios raros.
  - Quita zero-width + soft-hyphen.
  - Espacios Unicode raros (nbsp, thin space...) -> espacio normal.
  - Quita caracteres de control (menos \\n y \\t).
  - Des-hifenizacion de fin de linea ("informa-\\ncion" -> "informacion"),
    conservadora: solo une si lo que sigue es minuscula (evita romper compuestos).
  - Colapsa espacios/tabs repetidos y limita lineas en blanco, PRESERVANDO
    los saltos de parrafo (que el chunker estructural necesita).
"""

from __future__ import annotations

import re
import unicodedata

# Zero-width + soft hyphen -> eliminar (por code point, legible).
_REMOVE = dict.fromkeys(
    (
        0x200B,  # zero width space
        0x200C,  # zero width non-joiner
        0x200D,  # zero width joiner
        0x2060,  # word joiner
        0xFEFF,  # BOM / zero width no-break space
        0x00AD,  # soft hyphen
    ),
    None,
)

# Espacios Unicode "raros" -> espacio normal.
_SPACES = dict.fromkeys(
    (
        0x00A0,  # nbsp
        0x1680,
        *range(0x2000, 0x200B),  # en/em/thin/hair spaces, etc.
        0x202F,  # narrow nbsp
        0x205F,  # medium math space
        0x3000,  # ideographic space
    ),
    " ",
)

# Des-hifenizacion: letra + '-' + salto + minuscula -> se unen.
_DEHYPHEN = re.compile(r"([A-Za-zÀ-ÿ])-\s*\n\s*([a-zà-ÿ])")

# Explicación didáctica de normalize_text, paso a paso y en el MISMO orden en que
# se ejecuta. La muestra el frontend (GET /pipeline → "¿Cómo funciona?"). Los
# caracteres invisibles se escriben como marcadores visibles (⟨…⟩) a propósito.
EXPLAINED_STEPS: list[dict[str, str]] = [
    {
        "title": "Unifica caracteres «disfrazados» (Unicode NFKC)",
        "detail": (
            "Algunos PDFs usan ligaduras: un solo símbolo tipográfico para dos letras. "
            "Sin esto, buscar «financiero» no encuentra el texto, porque el PDF no dice f+i."
        ),
        "before": "\ufb01nanciero  (\ufb01 es 1 solo carácter: U+FB01)",
        "after": "financiero",
    },
    {
        "title": "Borra caracteres invisibles",
        "detail": (
            "Espacios de ancho cero y guiones suaves: no se ven, pero parten la palabra "
            "en dos para la máquina."
        ),
        "before": "póli⟨invisible⟩za",
        "after": "póliza",
    },
    {
        "title": "Convierte espacios raros en espacios normales",
        "detail": "Espacios que no permiten cortar la línea, espacios finos, etc.",
        "before": "S/⟨espacio especial⟩1,500",
        "after": "S/ 1,500",
    },
    {
        "title": "Quita caracteres de control",
        "detail": (
            "Restos del formato interno del PDF que el lector no ve. Solo se conservan "
            "el salto de línea y el tabulador."
        ),
        "before": "Cláusula⟨control⟩ 5",
        "after": "Cláusula 5",
    },
    {
        "title": "Une palabras cortadas al final de la línea",
        "detail": (
            "Des-hifenización conservadora: solo une si lo que sigue empieza en "
            "minúscula, para no romper nombres como «Lima-Callao». Limitación: un "
            "compuesto que cae justo al final de la línea («franco-peruano») se uniría."
        ),
        "before": "la garan-\ntía cubre",
        "after": "la garantía cubre",
    },
    {
        "title": "Ordena los espacios sin perder los párrafos",
        "detail": (
            "Varios espacios seguidos pasan a ser uno y 3+ líneas en blanco pasan a ser "
            "una. Se mantienen los párrafos y el Markdown (# títulos, | tablas, - listas) "
            "porque el chunking los necesita."
        ),
        "before": "Artículo   1\n\n\n\nEl  seguro cubre",
        "after": "Artículo 1\n\nEl seguro cubre",
    },
]

# Qué NO hace, a propósito (se muestra junto a los pasos).
NOT_DONE = (
    "No pasa a minúsculas, no quita tildes ni ñ («daños» ≠ «danos») y no corrige "
    "ortografía. Aplicarla dos veces da el mismo resultado."
)


def _strip_controls(text: str) -> str:
    """Quita caracteres de control/format (categoria Unicode 'C'), salvo \\n y \\t."""
    return "".join(
        c for c in text if c in "\n\t" or unicodedata.category(c)[0] != "C"
    )


def normalize_text(text: str, *, form: str = "NFKC", dehyphenate: bool = True) -> str:
    """Normaliza un bloque de texto/Markdown. Idempotente (correrlo 2 veces = igual)."""
    if not text:
        return ""

    t = unicodedata.normalize(form, text)
    t = t.translate(_REMOVE)
    t = t.translate(_SPACES)
    t = _strip_controls(t)

    if dehyphenate:
        t = _DEHYPHEN.sub(r"\1\2", t)

    t = re.sub(r"[ \t]+", " ", t)      # runs de espacios/tabs -> 1 espacio
    t = re.sub(r" *\n *", "\n", t)     # limpia espacios alrededor de saltos
    t = re.sub(r"\n{3,}", "\n\n", t)   # max. 1 linea en blanco (preserva parrafos)
    t = "\n".join(line.rstrip() for line in t.split("\n"))
    return t.strip()


def normalize_documents(docs: list[dict], **kwargs) -> list[dict]:
    """Aplica normalize_text al 'text' de cada pagina/doc, conservando metadata."""
    return [{**d, "text": normalize_text(d.get("text", ""), **kwargs)} for d in docs]
