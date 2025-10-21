# 🧩 **Arquitectura del Proyecto: Conversor HTML → Excel**

## 🧱 **Separación de Responsabilidades**

El proyecto aplica una arquitectura limpia basada en **separación entre la lógica de negocio (procesamiento de datos)** y la **capa de presentación (interfaz visual y control de usuario)**.  
Cada módulo cumple una función específica y se comunica a través de **callbacks** bien definidos.

---

## 📁 **Estructura del Proyecto**

1toolConverter_local/
│
├── main.py # Lógica de negocio y punto de entrada
├── presentation/
│ ├── init.py
│ └── ui.py # Interfaz gráfica y control de usuario
│
├── requirements.txt # Dependencias
└── ARCHITECTURE.md # Documentación de arquitectura


---

## 🎯 **Responsabilidades**

### 🧠 `main.py` — Lógica de Negocio

**Descripción:**  
Es el módulo principal del proyecto. Contiene toda la **lógica de procesamiento**, desde la lectura de archivos HTML hasta la generación de un `DataFrame` con la estructura final exportable a Excel.

**Responsabilidades principales:**
- Parsear archivos HTML y extraer sus tablas con `pandas.read_html`.
- Limpiar, transformar y normalizar las columnas.
- Interpretar permisos de lectura/escritura.
- Determinar la longitud de los datos según el rango numérico.
- Agregar columnas por defecto según la estructura definida en `LIBRARY_COLUMNS`.
- Devolver un `DataFrame` listo para la capa de presentación.

**Funciones clave:**

| Función | Descripción |
|----------|-------------|
| `process_html()` | Procesa el archivo HTML completo, aplica las transformaciones y genera el DataFrame final. |
| `_process_dataframe()` | Procesa individualmente cada tabla HTML (limpieza, mapeo, normalización). |
| `_apply_column_mapping()` | Mapea columnas del HTML a nombres estándar definidos en `COLUMN_MAPPING`. |
| `_process_access_permissions()` | Interpreta permisos R/W según tipo de variable y sistema. |
| `_process_specific_columns()` | Ajusta valores específicos como offsets, unidades, categorías, sampling, etc. |
| `_determine_data_length()` | Determina la longitud (16bit, s16) según los valores mín/máx. |
| `_add_default_columns()` | Agrega columnas con valores predeterminados para metadatos, alarmas y formato JSON. |

**Constantes:**

| Constante | Descripción |
|------------|-------------|
| `LIBRARY_COLUMNS` | Define la estructura final del DataFrame exportado a Excel. |
| `COLUMN_MAPPING` | Especifica cómo se deben renombrar las columnas del HTML. |

**Punto de entrada:**
- `main()` inicializa la aplicación y la interfaz, creando una instancia de `HTMLConverterUI` y pasando el callback `process_html`.

---

### 🖥️ `presentation/ui.py` — Capa de Presentación

**Descripción:**  
Controla toda la interfaz de usuario utilizando **NiceGUI**, manejando la interacción con el usuario, visualización de datos, y exportación a Excel.

**Clase principal:**  
`HTMLConverterUI` — Controlador general de la interfaz.

**Responsabilidades principales:**
- Gestionar carga, procesamiento y visualización de archivos HTML.
- Permitir clasificación manual de parámetros por tipo.
- Administrar la visualización de tablas con datos procesados.
- Controlar la exportación de resultados a Excel.
- Manejar la selección de filas, agrupación y eliminación de datos.

**Métodos públicos:**

| Método | Descripción |
|--------|--------------|
| `create_ui()` | Construye la interfaz completa con secciones visuales. |
| `handle_upload()` | Gestiona la carga del archivo HTML (validación y preparación). |
| `process_file()` | Invoca el procesamiento de datos llamando al callback `process_html`. |
| `display_table()` | Muestra los datos procesados en una tabla interactiva. |
| `download_excel()` | Exporta los datos procesados o clasificados a un archivo Excel. |
| `assign_group_to_selection()` | Asigna una categoría a las filas seleccionadas en la tabla principal. |
| `delete_selected_group_rows()` | Elimina filas seleccionadas de la tabla de grupos. |
| `clear_group_table()` | Limpia completamente la tabla de variables clasificadas. |

**Métodos privados (interfaz interna):**

| Método | Descripción |
|--------|--------------|
| `_create_upload_section()` | Sección para subir el archivo HTML. |
| `_create_process_section()` | Controles para procesar el archivo y mostrar los resultados. |
| `_create_table_section()` | Crea la tabla principal de parámetros procesados. |
| `_create_group_table_section()` | Crea la tabla de variables clasificadas. |

---

## 🔄 **Flujo de Datos**

Usuario
↓
[UI Component] (presentation/ui.py)
↓
[Event Handler] (handle_upload, process_file)
↓
[Business Logic] (main.py → process_html)
↓
[Data Processing] (limpieza, clasificación, validación)
↓
[Return to UI] (display_table, download_excel)
↓
Usuario (interacción visual)


---

## 🧮 **Detalles de Procesamiento**

| Etapa | Acción |
|--------|--------|
| **Lectura HTML** | Extrae las tablas del archivo con `pandas.read_html`. |
| **Filtrado** | Omite tablas vacías o sin estructura válida. |
| **Normalización** | Limpia encabezados duplicados, elimina columnas sin nombre y corrige tipos de datos. |
| **Mapeo** | Renombra columnas según el diccionario `COLUMN_MAPPING`. |
| **Permisos** | Interpreta permisos de acceso “R” o “R/W” según `system_category`. |
| **Clasificación** | Define categorías y sampling predeterminados según tipo de variable (ANALOG, DIGITAL, ALARM, etc.). |
| **Finalización** | Combina todas las tablas procesadas, agrega columnas por defecto y genera el `DataFrame` final. |

---

## 🎨 **Patrón de Diseño**

### 🧩 **Arquitectura por Capas (Layered Architecture)**

1. **Capa de Presentación** (`presentation/`)
   - Implementa la interfaz visual.
   - Gestiona interacción con el usuario.
   - No contiene lógica de negocio.
   - Usa callbacks para comunicarse con `main.py`.

2. **Capa de Negocio** (`main.py`)
   - Contiene toda la lógica de procesamiento de datos.
   - No depende de la interfaz.
   - Devuelve resultados procesados listos para exportar o mostrar.

---

## 🚀 **Características Destacadas**

- 🔍 Procesamiento automático de múltiples tablas HTML.  
- 🧹 Limpieza y validación de datos.  
- ⚙️ Clasificación automática y manual de parámetros.  
- 🧠 Interpretación inteligente de permisos de acceso (Read/Write).  
- 👩‍💻 Interfaz moderna construida con **NiceGUI**.  
- 📊 Tablas interactivas con selección múltiple y agrupación visual por color.  
- 📦 Exportación directa a Excel.  
- ♻️ Eliminación automática de archivos temporales tras la descarga.
