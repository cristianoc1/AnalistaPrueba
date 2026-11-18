"""Punto de entrada para descargar, extraer y exportar las facturas."""

from time import perf_counter

from automatizacion import descargar_facturas
from config import CARPETA_FACTURAS, CARPETA_RESULTADOS, CUFES
from extraccion import exportar_csv, procesar_pdf


def main() -> None:
    """Ejecuta el flujo y muestra un resumen de tiempos y resultados."""
    nit = input("Ingresa el NIT del emisor o receptor (solo dígitos): ").strip()
    if not nit.isdigit():
        print("Error: el NIT debe contener únicamente dígitos.")
        return

    inicio_proceso = perf_counter()
    CARPETA_FACTURAS.mkdir(parents=True, exist_ok=True)
    CARPETA_RESULTADOS.mkdir(parents=True, exist_ok=True)

    inicio_descarga = perf_counter()
    try:
        pdfs_disponibles, errores, cufes_procesados = descargar_facturas(
            CUFES, CARPETA_FACTURAS, nit
        )
    except Exception as error:
        pdfs_disponibles = []
        errores = [f"No se pudo iniciar el proceso de consulta: {error}"]
        cufes_procesados = 0
        print(errores[0])
    tiempo_descarga = perf_counter() - inicio_descarga

    inicio_extraccion = perf_counter()
    pdfs_procesados = 0
    csv_generados = 0
    if pdfs_disponibles:
        for ruta_pdf in pdfs_disponibles:
            pdfs_procesados += 1
            try:
                dataframe, faltantes = procesar_pdf(ruta_pdf, nit)
                ruta_csv = CARPETA_RESULTADOS / f"{ruta_pdf.stem}.csv"
                exportar_csv(dataframe, ruta_csv)
                csv_generados += 1
                print(f"CSV generado: {ruta_csv.name}")
                if faltantes:
                    print(
                        f"Revisar {ruta_pdf.name}; campos no identificados: "
                        f"{', '.join(faltantes)}"
                    )
            except Exception as error:
                mensaje = f"No se pudo procesar {ruta_pdf.name}: {error}"
                print(mensaje)
                errores.append(mensaje)

    tiempo_extraccion = perf_counter() - inicio_extraccion
    tiempo_total = perf_counter() - inicio_proceso
    promedio_por_factura = (
        tiempo_total / cufes_procesados if cufes_procesados else 0
    )

    print("\n--- Resumen del proceso ---")
    print(f"CUFE procesados: {cufes_procesados} de {len(CUFES)}")
    print(f"PDF disponibles para procesar: {len(pdfs_disponibles)}")
    print(f"PDF procesados: {pdfs_procesados}")
    print(f"CSV generados: {csv_generados}")
    print(f"Errores: {len(errores)}")
    print(f"Tiempo de consulta y descarga: {tiempo_descarga:.2f} s")
    print(f"Tiempo de extracción y exportación: {tiempo_extraccion:.2f} s")
    print(f"Tiempo total: {tiempo_total:.2f} s")
    print(f"Tiempo promedio por CUFE: {promedio_por_factura:.2f} s")


if __name__ == "__main__":
    main()
