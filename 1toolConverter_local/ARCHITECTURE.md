🧠 Documentación Técnica — convert_html_to_excel.py
📘 Descripción General
Este script convierte tablas contenidas en archivos HTML a un formato Excel (.xlsx), realizando limpieza, normalización y clasificación automática de parámetros técnicos. Está diseñado para procesar múltiples tablas, omitir resúmenes y exportar los datos combinados en una sola hoja Excel.
🧩 Función Principal: convert_html_to_excel()
Convierte un archivo HTML en un archivo Excel con los datos procesados y normalizados.

Flujo principal:
1. Verifica la existencia del archivo de entrada.
2. Extrae las tablas HTML con pandas.read_html().
3. Omite tablas de resumen y combina las demás.
4. Limpia y mapea las columnas según `COLUMN_MAPPING`.
5. Interpreta permisos de lectura/escritura ('R', 'W').
6. Normaliza unidades, offsets y categorías.
7. Clasifica parámetros (ALARM, SET_POINT, COMMAND, etc.).
8. Exporta el resultado consolidado a Excel.
⚙️ Constantes Globales
LIBRARY_COLUMNS → Define el orden y nombre estándar de las columnas del archivo final.
COLUMN_MAPPING → Mapea los nombres originales del HTML a los nombres normalizados del sistema.
🔍 Limpieza y Mapeo de Datos
El script elimina filas innecesarias, cabeceras duplicadas y columnas sin nombre. También transforma valores vacíos, '---' o 'nan' en NaN (valores nulos).
🧮 Clasificación de Parámetros
El procesamiento identifica el tipo de cada variable y su categoría de sistema con base en las siguientes reglas:
- **ALARM** → Variables detectadas por nombre o categoría.
- **SET_POINT** → Variables analógicas con permisos R/W.
- **CONFIG_PARAMETER** → Variables enteras con permisos R/W.
- **COMMAND** → Variables digitales con permisos R/W.
- **STATUS/DEFAULT** → Variables de solo lectura.
📊 Estructura Final del Excel
La hoja de salida 'Parametros_Unificados' contiene todas las variables procesadas con las columnas definidas en LIBRARY_COLUMNS.
Cada fila representa un parámetro completamente normalizado y clasificado.
📦 Dependencias
- pandas
- numpy
- openpyxl
- beautifulsoup4 (bs4)
- lxml
🚀 Ejecución
Desde consola:
  python convert_html_to_excel.py archivo.html

Si no se pasa un archivo como argumento, el script pedirá la ruta manualmente.
⚠️ Manejo de Errores
El script valida la existencia de archivos y controla excepciones comunes durante el procesamiento HTML y la escritura de Excel.
Si ocurre un error, imprime un mensaje descriptivo y termina la ejecución con sys.exit().
📚 Estructura de Archivos
convert_html_to_excel.py
│
├── LIBRARY_COLUMNS (lista de columnas finales)
├── COLUMN_MAPPING (mapa de nombres)
├── convert_html_to_excel() (función principal)
└── main() (entrada del programa)
