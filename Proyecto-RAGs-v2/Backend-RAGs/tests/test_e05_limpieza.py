"""
Tests de pipeline/stages/d_boilerplate.py con casos de distintos rubros.
Ejecutar desde Backend-RAGs:  python -m pytest tests -q
"""

from pipeline.stages.d_boilerplate import remove_boilerplate


def _pages(n, body, header=None, footer=None):
    """n páginas con cuerpo body(i), y header/footer opcionales (callables o str)."""
    out = []
    for i in range(n):
        parts = []
        if header:
            parts.append(header(i) if callable(header) else header)
        parts.append(body(i))
        if footer:
            parts.append(footer(i) if callable(footer) else footer)
        out.append("\n".join(parts))
    return out


def _body(i):
    return f"Texto propio de la página {i} con varias líneas.\nSegunda línea {i}.\nTercera línea {i}.\nCuarta línea {i}."


# --------------------------------------------------------------------------- #
# Lo que SÍ debe borrar
# --------------------------------------------------------------------------- #
def test_legal_quita_encabezado_corporativo_y_numeracion():
    pages = _pages(
        5, _body,
        header="Estudio Rodrigo & Asociados · Documento confidencial",
        footer=lambda i: f"Página {i + 1} de 5",
    )
    res = remove_boilerplate(pages)
    for p in res["pages"]:
        assert "confidencial" not in p.lower()
        assert "Página" not in p
        assert "Texto propio" in p
    assert res["removed_lines"] == 10


def test_encabezado_nativo_y_ocr_se_reconocen_como_iguales():
    # Página nativa en Markdown vs página OCR sin tildes ni negritas.
    headers = ["**BANCO XYZ · Área Legal**", "Banco XYZ - Area Legal", "**BANCO XYZ · Área Legal**", "BANCO XYZ Area Legal"]
    pages = _pages(4, _body, header=lambda i: headers[i])
    res = remove_boilerplate(pages)
    assert all("BANCO" not in p.upper() for p in res["pages"])


def test_numeros_de_pagina_sueltos_que_suben():
    pages = _pages(6, _body, footer=lambda i: f"- {i + 3} -")
    res = remove_boilerplate(pages)
    assert all(not p.endswith("-") for p in res["pages"])
    assert res["removed_lines"] == 6


def test_aviso_legal_largo_repetido():
    aviso = "La información contenida en este documento es confidencial y para uso exclusivo del destinatario."
    pages = _pages(4, _body, footer=aviso)
    res = remove_boilerplate(pages)
    assert all(aviso not in p for p in res["pages"])


# --------------------------------------------------------------------------- #
# Lo que NO debe borrar
# --------------------------------------------------------------------------- #
def test_legal_conserva_titulos_de_articulo_markdown():
    pages = _pages(6, _body, header=lambda i: f"## Artículo {i + 5}")
    res = remove_boilerplate(pages)
    for i, p in enumerate(res["pages"]):
        assert f"## Artículo {i + 5}" in p
    assert res["removed_lines"] == 0


def test_legal_conserva_clausulas_en_texto_plano():
    pages = _pages(6, _body, header=lambda i: f"Cláusula {i + 1}: Obligaciones del arrendatario")
    res = remove_boilerplate(pages)
    assert all("Cláusula" in p for p in res["pages"])


def test_finanzas_conserva_montos_sueltos_al_pie():
    montos = ["1,250.00", "980.50", "1,250.00", "15,300.00", "980.50"]
    pages = _pages(5, _body, footer=lambda i: montos[i])
    res = remove_boilerplate(pages)
    for i, p in enumerate(res["pages"]):
        assert montos[i] in p


def test_retail_conserva_filas_de_tabla_repetidas():
    tabla = "| SKU | Producto | Precio |"
    pages = _pages(4, lambda i: f"| {i} | Polo | 39.90 |\n{_body(i)}", header=tabla)
    res = remove_boilerplate(pages)
    assert all(tabla in p for p in res["pages"])


def test_marketing_conserva_encabezado_presente_en_pocas_paginas():
    # "Campaña Verano" solo en 2 de 8 páginas: no es plantilla.
    pages = _pages(8, _body, header=lambda i: "Campaña Verano 2026" if i < 2 else f"Sección {i}")
    res = remove_boilerplate(pages)
    assert "Campaña Verano 2026" in res["pages"][0]


def test_documentos_de_menos_de_3_paginas_no_se_tocan():
    pages = _pages(2, lambda i: "Capítulo 1. Misma frase inicial.", footer="Página 1")
    res = remove_boilerplate(pages)
    assert res["pages"] == [p.strip() for p in pages]
    assert res["removed_lines"] == 0


def test_paginas_cortas_no_borran_el_cuerpo():
    # Páginas de 4 líneas: el borde es 1 línea arriba y 1 abajo, no toda la página.
    pages = [f"Encabezado ACME\nLínea repetida en el cuerpo\nContenido {i}\nPie ACME" for i in range(4)]
    res = remove_boilerplate(pages)
    assert all("Línea repetida en el cuerpo" in p for p in res["pages"])
    assert all("ACME" not in p for p in res["pages"])


def test_es_idempotente():
    pages = _pages(5, _body, header="ACME S.A.", footer=lambda i: f"Página {i + 1}")
    once = remove_boilerplate(pages)["pages"]
    twice = remove_boilerplate(once)["pages"]
    assert once == twice
