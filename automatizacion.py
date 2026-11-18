"""Automatiza la consulta pública por CUFE y NIT en el portal de la DIAN."""

import time
from pathlib import Path

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeout, sync_playwright

from config import TIEMPO_MAXIMO_DESCARGA, URL_CONSULTA


def _buscar_boton_pdf(pagina: Page) -> Locator | None:
    """Detecta el enlace o botón de descarga de representación gráfica (PDF)."""
    controles = pagina.locator("a, button")
    for indice in range(controles.count()):
        control = controles.nth(indice)
        if not control.is_visible():
            continue

        texto = " ".join(
            [
                control.inner_text().strip(),
                control.get_attribute("aria-label") or "",
                control.get_attribute("title") or "",
                control.get_attribute("href") or "",
            ]
        ).lower()

        if "xml" not in texto and any(
            clave in texto
            for clave in ("pdf", "representación", "representacion", "gráfica", "grafica")
        ):
            return control
    return None


def _esperar_respuesta_consulta(pagina: Page, tiempo_limite: int) -> Locator:
    """Espera a que Cloudflare o la persona valide el CAPTCHA y aparezca el PDF."""
    limite = time.monotonic() + tiempo_limite
    while time.monotonic() < limite:
        boton = _buscar_boton_pdf(pagina)
        if boton is not None:
            return boton
        pagina.wait_for_timeout(500)

    raise PlaywrightTimeout(
        "Tiempo agotado esperando la verificación del CAPTCHA o la respuesta de la DIAN."
    )


def descargar_facturas(
    cufes: list[str], carpeta_destino: Path, nit: str
) -> tuple[list[Path], list[str], int]:
    """Consulta cada CUFE con su NIT, espera la validación y descarga el PDF."""
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    pdfs_disponibles: list[Path] = []
    errores: list[str] = []
    cufes_procesados = 0

    perfil_navegador = carpeta_destino.parent / ".perfil_chrome_dian"
    perfil_navegador.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        contexto = playwright.chromium.launch_persistent_context(
            user_data_dir=str(perfil_navegador),
            channel="chrome",
            headless=False,
            accept_downloads=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            pagina = contexto.pages[0] if contexto.pages else contexto.new_page()

            for numero, cufe in enumerate(cufes, start=1):
                cufes_procesados += 1
                nombre_destino = carpeta_destino / f"factura_{numero:02}.pdf"

                if nombre_destino.exists():
                    print(f"Se usará el PDF existente: {nombre_destino.name}")
                    pdfs_disponibles.append(nombre_destino)
                    continue

                print(f"\nFactura {numero:02} de {len(cufes)} | CUFE: {cufe[:16]}...")

                try:
                    pagina.goto(URL_CONSULTA, wait_until="domcontentloaded")

                    pagina.locator("#DocumentKey").fill(cufe)
                    campo_nit = pagina.locator("#SearchDocumentNit")
                    campo_nit.wait_for(state="visible", timeout=15_000)
                    campo_nit.fill(nit)

                    pagina.wait_for_timeout(2000)

                    boton_buscar = pagina.locator("button.search-document")
                    if boton_buscar.is_enabled():
                        boton_buscar.click()

                    print("Si Cloudflare solicita verificación, haz clic en la casilla en Chrome...")
                    boton_pdf = _esperar_respuesta_consulta(pagina, TIEMPO_MAXIMO_DESCARGA)

                    with pagina.expect_download(timeout=30_000) as descarga_info:
                        boton_pdf.click()

                    descarga_info.value.save_as(str(nombre_destino))

                    with nombre_destino.open("rb") as pdf:
                        if pdf.read(5) != b"%PDF-":
                            nombre_destino.unlink(missing_ok=True)
                            raise ValueError(
                                f"{nombre_destino.name} no parece ser un archivo PDF válido."
                            )

                    pdfs_disponibles.append(nombre_destino)
                    print(f"PDF descargado automáticamente: {nombre_destino.name}")

                except (OSError, PlaywrightTimeout, ValueError) as error:
                    mensaje = f"Factura {numero:02} ({cufe[:8]}...): {error}"
                    print(f"Error de consulta o descarga: {mensaje}")
                    errores.append(mensaje)
        finally:
            contexto.close()

    return pdfs_disponibles, errores, cufes_procesados
