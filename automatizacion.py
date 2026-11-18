"""Guía las consultas manuales y registra los PDF descargados desde la DIAN."""

import time
from pathlib import Path

from config import TIEMPO_MAXIMO_DESCARGA, URL_CONSULTA


def _esperar_pdf_nuevo(
    carpeta: Path,
    archivos_previos: set[Path],
    descargas_previas: set[Path],
    tiempo_limite: int,
) -> Path:
    """Espera un único PDF nuevo y confirma que terminó de descargarse."""
    limite = time.monotonic() + tiempo_limite
    ultimo_archivo = None
    tamano_anterior = -1
    lecturas_estables = 0

    while time.monotonic() < limite:
        archivos_nuevos = [
            archivo
            for archivo in carpeta.glob("*.pdf")
            if archivo.resolve() not in archivos_previos
        ]
        descargas_nuevas = [
            archivo
            for archivo in carpeta.glob("*.crdownload")
            if archivo.resolve() not in descargas_previas
        ]

        if len(archivos_nuevos) > 1:
            raise ValueError(
                "Se encontraron varios PDF nuevos; no es posible asociarlos "
                "con seguridad a este CUFE."
            )

        if len(archivos_nuevos) == 1 and not descargas_nuevas:
            archivo = archivos_nuevos[0]
            tamano_actual = archivo.stat().st_size
            if archivo == ultimo_archivo and tamano_actual == tamano_anterior:
                lecturas_estables += 1
            else:
                ultimo_archivo = archivo
                tamano_anterior = tamano_actual
                lecturas_estables = 0

            if tamano_actual > 0 and lecturas_estables >= 2:
                with archivo.open("rb") as pdf:
                    if pdf.read(5) != b"%PDF-":
                        raise ValueError(
                            f"{archivo.name} no parece ser un archivo PDF válido."
                        )
                return archivo

        time.sleep(0.5)

    raise TimeoutError(
        "No apareció un PDF nuevo en la carpeta indicada dentro del tiempo esperado."
    )


def descargar_facturas(
    cufes: list[str], carpeta_destino: Path
) -> tuple[list[Path], list[str], int]:
    """Solicita consultas manuales y devuelve los PDF disponibles para procesar."""
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    pdfs_disponibles = []
    errores = []
    cufes_procesados = 0

    for numero, cufe in enumerate(cufes, start=1):
        cufes_procesados += 1
        nombre_destino = carpeta_destino / f"factura_{numero:02}.pdf"
        if nombre_destino.exists():
            print(f"Se usará el PDF existente: {nombre_destino.name}")
            pdfs_disponibles.append(nombre_destino)
            continue

        print(f"\nFactura {numero:02} de {len(cufes)}")
        print(f"CUFE: {cufe}")
        print(f"Consulta el documento en: {URL_CONSULTA}")
        print(
            "En el navegador normal, ingresa también el NIT y resuelve el CAPTCHA. "
            "Descarga solo la representación gráfica en esta carpeta:"
        )
        print(carpeta_destino.resolve())
        print("Cuando termine la descarga, vuelve aquí y presiona Enter.")

        archivos_previos = {
            archivo.resolve() for archivo in carpeta_destino.glob("*.pdf")
        }
        descargas_previas = {
            archivo.resolve() for archivo in carpeta_destino.glob("*.crdownload")
        }

        try:
            input()
            pdf_descargado = _esperar_pdf_nuevo(
                carpeta_destino,
                archivos_previos,
                descargas_previas,
                TIEMPO_MAXIMO_DESCARGA,
            )
            pdf_descargado.rename(nombre_destino)
            pdfs_disponibles.append(nombre_destino)
            print(f"PDF registrado: {nombre_destino.name}")
        except EOFError:
            mensaje = "Se canceló la entrada; no se procesaron más CUFE."
            print(mensaje)
            errores.append(mensaje)
            break
        except (OSError, TimeoutError, ValueError) as error:
            mensaje = f"Factura {numero:02} ({cufe[:8]}...): {error}"
            print(f"Error de consulta o descarga: {mensaje}")
            errores.append(mensaje)

    return pdfs_disponibles, errores, cufes_procesados
