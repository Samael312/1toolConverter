# 🧩 **Arquitectura del Proyecto: 1tools - Convert Data Table Format**

## 🧾 **Metadatos del Proyecto**

| Campo | Descripción |
|-------|--------------|
| **Autor** | Kiconex - Samuel Ali |
| **Versión** | 2.0 |
| **Nombre** | 1tools - Convert Data Table Format |
| **Tipo** | Aplicación |
| **Descripción** | Conversión del formato de tablas de variables desde HTML a Excel utilizando `pandas`. |

---

## 📁 **Estructura del Proyecto**

1toolConverter_local/
│
├── convert_html_to_excel.py # Script principal de conversión (lógica completa)
├── ARCHITECTURE.md # Documentación de arquitectura (este archivo)
└── input.html # Archivo HTML de entrada (ejemplo)


---

## ⚙️ **Descripción General**

El script **convierte tablas HTML en una hoja Excel unificada**, procesando y normalizando la información de variables industriales.  
Utiliza `pandas`, `numpy` y `openpyxl` para realizar la lectura, limpieza, transformación y exportación final de datos.

El flujo principal:
1. Lee el archivo HTML.
2. Extrae todas las tablas válidas.
3. Limpia, mapea y normaliza los datos.
4. Aplica reglas automáticas según el tipo de variable y permisos de acceso.
5. Combina todas las tablas en una única hoja Excel estructurada.

---

## 🧱 **Constantes Clave**

### 📋 `LIBRARY_COLUMNS`
Define el orden y los nombres finales de las columnas exportadas en el Excel:

["id", "register", "name", "description", "system_category", "category", "view",
"sampling", "read", "write", "minvalue", "maxvalue", "unit", "offset",
"addition", "mask", "value", "length", "general_icon", "alarm", "metadata",
"l10n", "tags", "type", "parameter_write_byte_position", "mqtt", "json",
"current_value", "current_error_status", "notes"]


### 🔄 `COLUMN_MAPPING`
Mapea nombres de columnas del HTML a nombres estándar:

| Original | Mapeado a |
|-----------|------------|
| BMS Address | register |
| Variable name | name |
| Description | description |
| Min | minvalue |
| Max | maxvalue |
| Category | category |
| UOM | unit |
| Bms_Ofs | offset |
| Bms_Type | system_category |

---

## 🧠 **Lógica Principal**

### 🔹 `convert_html_to_excel(input_path, output_path="parametros.xlsx")`

**Descripción:**  
Procesa un archivo HTML, extrae todas las tablas y genera un Excel con la información unificada.

**Flujo detallado:**

1. **Lectura del archivo HTML**
   - Usa `pandas.read_html` con el parser `BeautifulSoup` para extraer todas las tablas.
   - Si no encuentra tablas válidas, el programa se detiene con un mensaje descriptivo.

2. **Selección de tablas útiles**
   - Omite la primera tabla (índice 0), asumiendo que es un resumen.
   - Procesa las tablas restantes.

3. **Limpieza inicial de datos**
   - Elimina columnas “Unnamed”.
   - Ajusta encabezados.
   - Detecta la columna de permisos (`Read/Write` o `Direction`).

4. **Normalización de acceso**
   - Crea columnas `read` y `write` inicializadas en `0`.
   - Interpreta permisos:
     - Contiene “R” → `read = 4`
     - Contiene “W” → `write = 4`

5. **Reglas automáticas por tipo de variable (`system_category`)**

   | Tipo | Condición | Read | Write | Sampling |
   |------|------------|------|--------|-----------|
   | ANALOG / INTEGER (R/W) | Ambos > 0 | 3 | 16 | 60 |
   | ANALOG / INTEGER (R) | Solo lectura | 4 | 0 | 60 |
   | DIGITAL (R/W) | Ambos > 0 | 1 | 5 | 60 |
   | DIGITAL (R) | Solo lectura | 4 | 0 | 60 |
   | ALARM | Siempre lectura | 4 | 0 | 30 |

6. **Reclasificación de categorías**
   Se redefine `system_category` según reglas jerárquicas:

   | Condición | Nueva Categoría |
   |------------|----------------|
   | ALARM detectada | ALARM |
   | ANALOG R/W | SET_POINT |
   | INTEGER R/W | CONFIG_PARAMETER |
   | ANALOG / INTEGER R-only | DEFAULT |
   | DIGITAL R/W | COMMAND |
   | Ninguna aplica | STATUS |

7. **Ajustes adicionales**
   - Limpieza y normalización de unidades (`unit`).
   - Conversión de `offset`, `minvalue`, `maxvalue` a valores numéricos.
   - Determinación de longitud (`length`) → `16bit` o `s16` si hay valores negativos.

8. **Agregado de columnas por defecto**
   Se completan valores faltantes con información estándar (`alarm`, `metadata`, `tags`, `l10n`, etc.).

9. **Exportación a Excel**
   - Combina todas las tablas procesadas en una hoja llamada `"Parametros_Unificados"`.
   - Exporta con `pandas.ExcelWriter` y `openpyxl`.

---

## 🔄 **Flujo General del Sistema**
Usuario
   ↓
Archivo HTML
   ↓
[convert_html_to_excel()]
   ↓
  ├─ Extracción de tablas (pandas)
  ├─ Limpieza y mapeo de columnas
  ├─ Reglas de permisos y categorías
  ├─ Normalización de unidades y valores
   ↓
Archivo Excel Unificado

---

## 🧮 **Dependencias**

Librería -	Uso
pandas:	Lectura y escritura de tablas HTML/Excel
numpy:	Procesamiento numérico y máscaras lógicas
openpyxl:	Motor de exportación a Excel
sys, pathlib, typing:	Utilidades estándar del sistema

---

## 🧩 **Patrón y Principios**

**Single Responsibility:**
Cada bloque del código tiene una función única (lectura, limpieza, normalización, exportación).

**Pipeline de Procesamiento:**
Los datos pasan secuencialmente por etapas definidas sin mezclar responsabilidades.

**Data Normalization:**
Se garantiza un formato unificado independientemente del contenido HTML original.

---

## ✅ **Resultado Final**

El script genera un archivo Excel con estructura homogénea, listo para:

Cargar en sistemas SCADA o BMS.

Revisar y ajustar manualmente.

Usar como base para automatización de configuración industrial.

Salida final:
parametros.xlsx
└── Hoja: "Parametros_Unificados"

---

## 🚀 **Función Principal: `main()`**

**Propósito:**  
Permite ejecutar el script desde la terminal, solicitando el archivo de entrada o usando uno por defecto.

**Flujo:**
1. Si se pasa un argumento → se usa como ruta de entrada.  
2. Si no → solicita al usuario la ruta (por defecto `input.html`).  
3. Llama a `convert_html_to_excel(path)`.

**Ejecución desde terminal:**
```bash
python convert_html_to_excel.py archivo.html


