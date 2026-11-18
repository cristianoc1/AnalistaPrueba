# Consulta y extracción automatizada de facturas electrónicas (DIAN)

## Descripción

Este proyecto implementa un flujo de automatización (RPA híbrido / *Human-in-the-Loop*) y extracción de datos para procesar diez facturas electrónicas en el portal público de la DIAN. El sistema automatiza la navegación web, el diligenciamiento de formularios (CUFE y NIT), la captura directa de las representaciones gráficas en PDF, el desbloqueo de documentos protegidos y la estructuración de sus ítems en archivos CSV individuales.

## Arquitectura y decisión técnica (*Human-in-the-Loop*)

Durante las pruebas iniciales con navegadores automatizados estándar (Selenium), el portal de la DIAN bloqueaba las consultas mediante **Cloudflare Turnstile**, mostrando el error *«La verificación falló»* al detectar entornos sin historial ni cookies reales (`navigator.webdriver = true`).

Para resolver este bloqueo sin recurrir a servicios externos de evasión de CAPTCHA y manteniendo la estabilidad del flujo, se diseñó una arquitectura con **Playwright** apoyada en tres pilares:

1. **Perfil persistente y navegador nativo:** Se ejecuta Google Chrome instalado en el sistema (`channel="chrome"`) utilizando un contexto persistente (`.perfil_chrome_dian`) y suprimiendo las banderas de automatización (`--disable-blink-features=AutomationControlled`). Esto permite conservar la reputación de sesión y cookies entre consultas, reduciendo las interrupciones de Cloudflare.
2. **Intervención mínima asistida:** El script diligencia automáticamente el **CUFE** y el **NIT** en cada iteración. Si Cloudflare valida en segundo plano, el sistema ejecuta la búsqueda y descarga el PDF sin intervención; si exige confirmación visual puntual, el flujo aguarda el clic del usuario en la casilla de verificación y retoma el control automáticamente en cuanto detecta el enlace del documento.
3. **Captura directa de descargas y extracción estructurada:** Mediante la interceptación de eventos de descarga (`expect_download`), cada PDF se valida mediante su firma binaria (`%PDF-`), se renombra de forma consecutiva (`factura_01.pdf`, `factura_02.pdf`, etc.) y se procesa con **PyMuPDF** y expresiones regulares para generar los reportes CSV.

## Tecnologías

- **Python 3.10+:** Orquestación del flujo, manejo de rutas (`pathlib`) y medición de métricas (`time`).
- **Playwright:** Automatización del navegador, gestión de contexto persistente e interceptación directa de descargas.
- **PyMuPDF (`fitz`):** Autenticación de PDFs protegidos por contraseña y extracción de texto seleccionable.
- **Expresiones Regulares (`re`):** Parsing de encabezados de factura y reconstrucción de filas de productos multilínea.
- **Pandas:** Estructuración tabular de los datos extraídos y exportación a CSV en codificación UTF-8.

## Estructura del proyecto

```text
.
├── main.py
├── automatizacion.py
├── extraccion.py
├── config.py
├── facturas/
├── resultados/
├── requirements.txt
├── README.md
└── .gitignore
```

- `main.py`: Punto de entrada. Solicita el NIT una única vez, coordina la etapa de descarga con la de extracción y calcula las métricas de rendimiento.
- `automatizacion.py`: Controla Google Chrome mediante Playwright, rellena el CUFE y el NIT, espera la validación de Cloudflare y captura los PDF descargados.
- `extraccion.py`: Desbloquea los PDF protegidos usando el NIT, extrae los datos generales y los ítems facturados, y exporta un archivo CSV por documento.
- `config.py`: Centraliza la lista de CUFE, la URL del portal de la DIAN, las rutas de trabajo y los tiempos de espera.
- `facturas/`: Directorio local donde se almacenan los PDF descargados.
- `resultados/`: Directorio local donde se generan los archivos CSV procesados.

## Requisitos e instalación

Se requiere **Python 3.10 o superior** y **Google Chrome** instalado en el equipo.

1. Clonar el repositorio y crear el entorno virtual:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Instalar las dependencias del proyecto:
   ```powershell
   python -m pip install -r requirements.txt
   ```

## Ejecución

Para iniciar el proceso completo, ejecutar:

```powershell
python main.py
```

### Flujo paso a paso
1. **Ingreso único de credenciales:** La consola solicita el **NIT** (solo dígitos) del emisor o receptor. Este valor se reutiliza automáticamente tanto para las consultas web como para desbloquear los PDF protegidos.
2. **Consulta y descarga automatizada:** Se abre una ventana de Google Chrome con perfil persistente. Para cada CUFE, el script navega al portal, completa los campos y espera a que la verificación de seguridad se complete (requiriendo únicamente un clic humano si Cloudflare lo solicita en pantalla).
3. **Validación y almacenamiento:** Al aparecer la opción de descarga, Playwright intercepta el archivo, verifica su integridad (`%PDF-`) y lo guarda en `facturas/` con nombre consecutivo. Si un PDF ya existe de una ejecución previa, se reutiliza sin volver a descargarlo.
4. **Extracción y exportación:** Finalizadas las descargas, el motor de extracción procesa cada documento y genera su respectivo archivo `factura_XX.csv` en la carpeta `resultados/`.

## Datos extraídos

Cada archivo CSV generado contiene la siguiente estructura:

| Columna | Descripción |
| --- | --- |
| `numero_factura` | Número o prefijo y consecutivo de la factura |
| `fecha_emision` | Fecha de emisión del documento |
| `nit_emisor` | NIT del emisor o vendedor |
| `codigo` | Código interno o estándar del producto |
| `descripcion` | Descripción completa del ítem (uniendo líneas continuas) |
| `cantidad` | Cantidad facturada |
| `precio_unitario` | Valor unitario del producto |

Cada fila corresponde a un producto e incluye los datos de cabecera de su factura. Si algún campo no puede identificarse con certeza, se deja vacío y se reporta una advertencia en consola para evitar datos supuestos.

## Métricas

Al finalizar la ejecución, la consola presenta un resumen operativo con:

- Total de CUFE procesados y PDFs disponibles.
- Cantidad de PDFs procesados y archivos CSV generados.
- Registro detallado de errores o campos faltantes.
- Tiempo invertido en consulta/descarga, tiempo de extracción/exportación, tiempo total y promedio por factura.

## Consideraciones y restricciones

- **Seguridad y privacidad:** El NIT ingresado en consola se mantiene únicamente en memoria durante la ejecución y no se almacena en archivos de configuración. Los PDFs, los CSVs y el directorio `.perfil_chrome_dian/` están excluidos del control de versiones mediante `.gitignore`.
- **Lectura de PDF:** El módulo de extracción utiliza PyMuPDF sobre texto seleccionable; documentos escaneados como imagen requerirían la integración adicional de un motor OCR.