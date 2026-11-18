"""Extrae campos y productos de las representaciones gráficas en PDF."""

import re
from pathlib import Path

import pandas as pd
import pymupdf as fitz


COLUMNAS_CSV = [
    "numero_factura",
    "fecha_emision",
    "nit_emisor",
    "codigo",
    "descripcion",
    "cantidad",
    "precio_unitario",
]

_NUMERO = r"(?:\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
_PATRON_NUMERO_COMPLETO = re.compile(rf"^{_NUMERO}$")
# Estas siglas de unidad aparecen como líneas aparte, no como parte de la descripción.
_UNIDADES_MEDIDA = {"C62", "NAR", "NIU"}


def leer_texto_pdf(ruta_pdf: Path, contrasena: str | None = None) -> str:
    """Desbloquea el PDF si es necesario y lee su texto seleccionable."""
    with fitz.open(ruta_pdf) as documento:
        if documento.needs_pass:
            if not contrasena or documento.authenticate(contrasena) == 0:
                raise ValueError(
                    "El PDF está protegido y no se pudo abrir con el NIT ingresado."
                )

        texto = "\n".join(pagina.get_text() for pagina in documento)

    if not texto.strip():
        raise ValueError(
            "El PDF no contiene texto seleccionable; se requiere OCR para leerlo."
        )
    return texto


def _buscar_valor(texto: str, patrones: list[str]) -> str | None:
    for patron in patrones:
        coincidencia = re.search(patron, texto, flags=re.IGNORECASE | re.MULTILINE)
        if coincidencia:
            return coincidencia.group(1).strip()
    return None


def _seccion(texto: str, inicio: str, fin: str) -> str:
    """Devuelve el texto entre dos encabezados, si ambos están presentes."""
    posicion_inicio = re.search(inicio, texto, flags=re.IGNORECASE)
    if not posicion_inicio:
        return ""

    contenido = texto[posicion_inicio.end() :]
    posicion_fin = re.search(fin, contenido, flags=re.IGNORECASE)
    return contenido[: posicion_fin.start()] if posicion_fin else contenido


def extraer_datos_generales(texto: str) -> dict[str, str | None]:
    """Identifica número, fecha y NIT del emisor sin completar datos faltantes."""
    # Limitar la búsqueda del NIT a la sección del emisor evita tomar el del receptor
    seccion_documento = _seccion(
        texto,
        r"Datos del Documento",
        r"Datos del Emisor|Datos del Vendedor|Detalles del Producto",
    )
    seccion_emisor = _seccion(
        texto,
        r"Datos del Emisor(?:/Vendedor)?|Datos del Vendedor",
        r"Datos del Receptor|Datos del Cliente|Detalles del Producto",
    )

    numero_factura = _buscar_valor(
        seccion_documento or texto,
        [
            r"(?:N[uú]mero|Nro\.?|No\.?|N[º°])\s*(?:de\s*)?factura\s*[:#]?\s*"
            r"([A-Z0-9-]+)",
            r"Factura Electr[oó]nica de Venta\s*(?:No\.?|N[º°])?\s*[:#]?\s*"
            r"([A-Z0-9-]+)",
        ],
    )
    fecha_emision = _buscar_valor(
        texto,
        [
            r"(?:Fecha\s*(?:de\s*)?(?:emisi[oó]n|generaci[oó]n)|Emisi[oó]n)"
            r"\s*[:#]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})"
        ],
    )
    nit_emisor = _buscar_valor(
        seccion_emisor,
        [r"\bN\.?I\.?T\.?\s*[:#]?\s*([0-9][0-9.\- ]{5,})"],
    )

    return {
        "numero_factura": numero_factura,
        "fecha_emision": fecha_emision,
        "nit_emisor": nit_emisor,
    }


def extraer_productos(texto: str) -> list[dict[str, str]]:
    """Lee las filas numeradas y une las líneas de cada descripción."""
    lineas = texto.splitlines()
    inicio = next(
        (
            indice
            for indice, linea in enumerate(lineas)
            if re.search(r"Detalles\s+(?:de|del)\s+Productos?", linea, re.I)
        ),
        None,
    )
    if inicio is None:
        return []

    indice_nro = next(
        (
            indice
            for indice in range(inicio, len(lineas))
            if re.fullmatch(r"\s*Nro\.?\s*", lineas[indice], re.I)
        ),
        None,
    )
    if indice_nro is None:
        return []

    indice_inc = next(
        (
            indice
            for indice in range(indice_nro, len(lineas))
            if re.fullmatch(r"\s*INC\s*", lineas[indice], re.I)
        ),
        None,
    )
    if indice_inc is None:
        return []

    inicio_datos = indice_inc + 1
    while inicio_datos < len(lineas) and (
        not lineas[inicio_datos].strip() or lineas[inicio_datos].strip() == "%"
    ):
        inicio_datos += 1

    fin_datos = next(
        (
            indice
            for indice in range(inicio_datos, len(lineas))
            if re.fullmatch(
                r"\s*(?:Notas Finales|Datos Totales|Documento generado el|MONEDA)\s*",
                lineas[indice],
                re.I,
            )
        ),
        len(lineas),
    )
    lineas_datos = [
        linea.strip() for linea in lineas[inicio_datos:fin_datos] if linea.strip()
    ]

    productos = []
    posicion = 0
    numero_esperado = 1

    # En el texto de la DIAN, cada fila comienza con su número de ítem.
    while True:
        fila_encontrada = None
        for indice in range(posicion, len(lineas_datos)):
            if lineas_datos[indice] != str(numero_esperado):
                continue

            indice_codigo = indice + 1
            if indice_codigo >= len(lineas_datos):
                continue

            partes = lineas_datos[indice_codigo].split(maxsplit=1)
            codigo = ""
            descripcion = []
            if re.search(r"\d", partes[0]):
                codigo = partes[0]
                if len(partes) > 1:
                    descripcion.append(partes[1])
                inicio_busqueda = indice_codigo + 1
            else:
                descripcion.append(lineas_datos[indice_codigo])
                inicio_busqueda = indice_codigo + 1

            # Cantidad y precio unitario aparecen como las primeras dos cifras
            # consecutivas después del código y la descripción.
            indice_cantidad = next(
                (
                    indice_valor
                    for indice_valor in range(
                        inicio_busqueda, len(lineas_datos) - 1
                    )
                    if _PATRON_NUMERO_COMPLETO.fullmatch(
                        lineas_datos[indice_valor]
                    )
                    and _PATRON_NUMERO_COMPLETO.fullmatch(
                        lineas_datos[indice_valor + 1]
                    )
                ),
                None,
            )
            if indice_cantidad is None:
                continue

            descripcion.extend(lineas_datos[inicio_busqueda:indice_cantidad])
            if descripcion and descripcion[-1].upper() in _UNIDADES_MEDIDA:
                descripcion.pop()

            descripcion_texto = " ".join(descripcion).strip()
            if not descripcion_texto:
                continue

            fila_encontrada = (
                indice,
                indice_cantidad,
                {
                    "codigo": codigo,
                    "descripcion": descripcion_texto,
                    "cantidad": lineas_datos[indice_cantidad],
                    "precio_unitario": lineas_datos[indice_cantidad + 1],
                },
            )
            break

        if fila_encontrada is None:
            break

        _, indice_cantidad, producto = fila_encontrada
        productos.append(producto)
        posicion = indice_cantidad + 2
        numero_esperado += 1

    return productos


def crear_dataframe(
    datos_generales: dict[str, str | None],
    productos: list[dict[str, str]],
) -> pd.DataFrame:
    """Crea un DataFrame con una fila por producto y las columnas requeridas."""
    # Los datos generales se repiten en cada producto para mantener una fila por ítem
    filas = [
        {**datos_generales, **producto}
        for producto in productos
    ]
    return pd.DataFrame(filas, columns=COLUMNAS_CSV)


def procesar_pdf(
    ruta_pdf: Path, contrasena: str | None = None
) -> tuple[pd.DataFrame, list[str]]:
    """Extrae datos y devuelve los campos no identificados para su revisión."""
    texto = leer_texto_pdf(ruta_pdf, contrasena)
    datos_generales = extraer_datos_generales(texto)
    productos = extraer_productos(texto)
    dataframe = crear_dataframe(datos_generales, productos)

    # Los campos no encontrados se informan; no se completan con valores supuestos
    faltantes = [
        campo
        for campo, valor in datos_generales.items()
        if not valor
    ]
    if not productos:
        faltantes.append("filas de productos")
    else:
        for indice, producto in enumerate(productos, start=1):
            for campo in ("codigo", "descripcion", "cantidad", "precio_unitario"):
                if not producto.get(campo):
                    faltantes.append(f"producto {indice}: {campo}")

    return dataframe, faltantes


def exportar_csv(dataframe: pd.DataFrame, ruta_csv: Path) -> None:
    """Guarda el DataFrame en UTF-8."""
    ruta_csv.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(ruta_csv, index=False, encoding="utf-8")
