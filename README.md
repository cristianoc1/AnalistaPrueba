# Consulta y extracción de facturas electrónicas

## Descripción

El proyecto organiza el procesamiento de diez facturas electrónicas indicadas en la prueba técnica. Para cada CUFE, la persona realiza la consulta en el portal de la DIAN y descarga la representación gráfica en PDF. El programa registra cada descarga, extrae los datos solicitados y genera un archivo CSV por factura.

## Alcance y limitación de la automatización

La prueba solicita que un RPA consulte los CUFE, descargue los PDF y resuelva automáticamente el CAPTCHA. Durante la validación del portal, Cloudflare Turnstile mostró el mensaje **«La verificación falló»** en Chrome controlado por Selenium. Por esa razón, esta implementación no automatiza el control del navegador ni intenta resolver o evadir el CAPTCHA.

La consulta y descarga deben realizarse manualmente en un navegador normal; el programa no abre Chrome ni controla el navegador. Para cada CUFE, muestra el código y la ruta de destino, y espera a que la persona consulte el documento, ingrese el NIT, resuelva el CAPTCHA y descargue la representación gráfica en `facturas`. Después, comprueba que haya un único PDF nuevo, espera a que su tamaño se estabilice y verifica su firma PDF antes de asignarle un nombre consecutivo. La extracción, la creación de los DataFrames, la exportación de los CSV y el cálculo de las métricas se ejecutan automáticamente. Si los PDF están protegidos, solicita una vez en la terminal el NIT compuesto solo por dígitos para poder leerlos; el dato no se guarda en el proyecto.

Por lo tanto, la consulta y descarga automáticas solicitadas en el primer punto no quedan cubiertas. La solución no presenta esta intervención manual como un RPA completo.

## Tecnologías

- **Python 3:** flujo principal y manejo de archivos.
- **Pandas:** creación de un DataFrame por factura y exportación a CSV.
- **PyMuPDF:** extracción de texto seleccionable de los PDF.
- **Regex (`re`):** identificación de campos y filas de producto.
- **`pathlib` y `time`:** manejo de rutas y medición de tiempos.

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

- `main.py` coordina las consultas manuales, el procesamiento de PDF y las métricas.
- `automatizacion.py` presenta cada CUFE, espera la descarga manual, verifica el archivo y le asigna un nombre consecutivo.
- `extraccion.py` extrae los datos generales y productos, crea los DataFrames y exporta los CSV.
- `config.py` contiene los CUFE, la dirección del portal, las rutas y los límites de espera.
- `facturas/` almacena las representaciones gráficas descargadas.
- `resultados/` almacena los CSV generados.

## Requisitos e instalación

Se requiere Python 3.10 o posterior.

Desde la carpeta del proyecto, se puede crear y preparar un entorno virtual con:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Ejecución

```powershell
python main.py
```

Para cada CUFE, el programa lo presenta en la consola y espera a que se complete la consulta manual:

1. Abrir el portal de consulta de documentos de la DIAN en un navegador normal: <https://catalogo-vpfe.dian.gov.co/User/SearchDocument>.
2. Copiar el CUFE mostrado en la consola y realizar la consulta.
3. Resolver el CAPTCHA en el navegador cuando el portal lo solicite.
4. Descargar únicamente la representación gráfica de esa factura en la ruta `facturas` que muestra la consola. Si el navegador la guarda en otra ubicación, muévela a `facturas`.
5. Esperar a que termine la descarga y presionar Enter en la consola.

El programa comprueba que haya un único PDF nuevo, lo nombra `factura_01.pdf`, `factura_02.pdf`, etc., y continúa con el siguiente CUFE. Después de presionar Enter, espera hasta 90 segundos a que aparezca el archivo; si no aparece, informa el error y continúa con el siguiente CUFE. No sobrescribe archivos consecutivos existentes; en ejecuciones posteriores reutiliza los PDF que ya estén en `facturas`. Al completar las consultas, solicita el NIT si hay PDF para procesar, extrae su contenido y guarda un CSV por factura en `resultados`.

Si una consulta falla, no se descarga un PDF o aparecen varios PDF nuevos a la vez, el error se informa y el proceso continúa con el siguiente CUFE. Los archivos que no se hayan podido asociar a una consulta deben revisarse antes de volver a ejecutar el proceso.

## Datos extraídos

Cada CSV contiene las siguientes columnas:

| Columna | Descripción |
| --- | --- |
| `numero_factura` | Número de la factura |
| `fecha_emision` | Fecha de emisión |
| `nit_emisor` | NIT del emisor o vendedor |
| `codigo` | Código del producto |
| `descripcion` | Descripción del producto |
| `cantidad` | Cantidad facturada |
| `precio_unitario` | Precio unitario |

Cada fila representa un producto e incluye los datos generales de su factura. Las descripciones que continúan en la siguiente línea se unen antes de procesar la fila. Los campos que no se identifican se dejan vacíos y se informan en consola; no se completan con valores supuestos. Los archivos CSV se guardan en UTF-8.

## Métricas

Al finalizar, el programa presenta:

- CUFE atendidos y PDF disponibles para procesar.
- PDF procesados y CSV generados.
- Cantidad de errores.
- Tiempo empleado en las consultas y descargas manuales.
- Tiempo de extracción y exportación.
- Tiempo total y promedio por CUFE atendido.

Los tiempos se miden durante la ejecución e incluyen la espera mientras se realizan las consultas manuales.

## Restricciones

- La resolución automática del CAPTCHA no está implementada; Cloudflare rechazó la verificación en el navegador controlado por Selenium.
- La consulta y descarga manuales son necesarias para obtener los PDF sin automatizar ni evadir el control del portal.
- Los PDF protegidos requieren el NIT correspondiente para permitir la extracción de texto.
- PyMuPDF requiere texto seleccionable. Los PDF que solo contienen imágenes se reportan como no procesables; no se incluye OCR.
- La extracción depende de la estructura del texto de cada factura. Se deben revisar los campos faltantes que informe el programa.
- Los PDF y CSV generados se excluyen del control de versiones mediante `.gitignore`.
