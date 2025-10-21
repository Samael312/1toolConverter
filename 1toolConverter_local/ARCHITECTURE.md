# 🧩 **Arquitectura del Proyecto: Conversor HTML → Excel**

## 🧱 **Separación de Responsabilidades**

El proyecto sigue una arquitectura limpia con **división clara entre la lógica de negocio (procesamiento de datos)** y la **capa de presentación (interfaz visual y control de usuario)**.  
Cada capa es independiente y se comunica a través de **callbacks** bien definidos.

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

markdown
Copiar código

---

## 🎯 **Responsabilidades**

### 🧠 `main.py` — Lógica de Negocio

**Responsabilidades principales:**
- Procesar archivos HTML y extraer tablas.
- Limpiar, transformar y mapear datos a un formato estándar.
- Clasificar automáticamente parámetros según reglas.
- Generar un `DataFrame` con la estructura esperada para exportación.
- Exponer una interfaz (`process_html`) para que la UI invoque el procesamiento.

**Funciones clave:**

| Función | Descripción |
|----------|--------------|
| `process_html()` | Procesa el archivo HTML completo y combina las tablas. |
| `_process_dataframe()` | Procesa individualmente cada tabla HTML. |
| `_apply_column_mapping()` | Mapea nombres de columnas a la estructura esperada. |
| `_process_access_permissions()` | Interpreta permisos de lectura/escritura (R/W). |
| `_process_specific_columns()` | Limpia y ajusta valores específicos (offsets, unidades, categorías). |
| `_determine_data_length()` | Determina la longitud de datos según el rango numérico. |
| `_apply_deep_classification()` | Clasifica los parámetros en grupos lógicos (ALARM, CONFIG, etc.). |
| `_add_default_columns()` | Añade columnas y valores por defecto si no existen. |

**Constantes:**

| Constante | Descripción |
|------------|-------------|
| `LIBRARY_COLUMNS` | Define la estructura final del DataFrame exportado. |
| `COLUMN_MAPPING` | Define cómo mapear columnas HTML a nombres estándar. |

**Punto de entrada:**
- `main()` inicializa la aplicación, crea el controlador de UI (`HTMLConverterUI`) y ejecuta la interfaz con NiceGUI.

---

### 🖥️ `presentation/ui.py` — Capa de Presentación

**Responsabilidades principales:**
- Crear y administrar los componentes visuales.
- Manejar eventos de usuario (subida de archivo, procesamiento, clasificación, descarga).
- Mostrar los resultados en tablas interactivas.
- Permitir clasificación manual de parámetros por grupos.
- Controlar la descarga de archivos Excel procesados.

**Clase principal:**
- `HTMLConverterUI` — Controlador de interfaz de usuario.

**Métodos públicos:**

| Método | Descripción |
|--------|--------------|
| `create_ui()` | Crea la interfaz completa con todas las secciones. |
| `handle_upload()` | Gestiona la carga del archivo HTML. |
| `process_file()` | Llama a la función de negocio (`process_html`) para procesar los datos. |
| `display_table()` | Muestra los datos procesados en una tabla interactiva. |
| `assign_group_to_selection()` | Permite asignar manualmente una categoría a las filas seleccionadas. |
| `delete_selected_group_rows()` | Elimina filas seleccionadas de la tabla de grupos. |
| `clear_group_table()` | Limpia completamente la tabla de variables clasificadas. |
| `download_excel()` | Exporta los datos procesados o clasificados a Excel. |

**Métodos privados (UI interna):**

| Método | Descripción |
|--------|--------------|
| `_create_upload_section()` | Sección de carga de archivos HTML. |
| `_create_process_section()` | Sección de procesamiento y visualización. |
| `_create_table_section()` | Sección con la tabla de parámetros procesados. |
| `_create_group_table_section()` | Sección con la tabla de variables clasificadas. |

---

## 🔄 **Flujo de Datos**

Usuario
↓
[UI Component] (presentation/ui.py)
↓
[Event Handler] (handle_upload, process_file)
↓
[Business Logic] (main.py - process_html)
↓
[Data Processing] (limpieza, clasificación, validación)
↓
[Return to UI] (display_table, download_excel)
↓
Usuario (interacción visual)

markdown
Copiar código

---

## 🧮 **Detalles de Procesamiento**

| Etapa | Acción |
|--------|--------|
| **Lectura HTML** | Extrae tablas mediante `pandas.read_html`. |
| **Filtrado** | Omite tablas vacías o sin estructura válida. |
| **Normalización** | Limpia nombres de columnas y elimina las no relevantes. |
| **Mapeo** | Renombra columnas según `COLUMN_MAPPING`. |
| **Permisos** | Interpreta las columnas "Read/Write" o "Direction". |
| **Clasificación** | Aplica reglas automáticas y personalizadas de categorías (`_apply_deep_classification`). |
| **Finalización** | Combina todas las tablas procesadas, añade columnas por defecto y genera `DataFrame` final. |

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
   - No conoce detalles de la interfaz.
   - Devuelve resultados listos para mostrar o exportar.

---

## 🚀 **Características Destacadas**

- 🔍 Procesamiento automático de múltiples tablas HTML.  
- 🧹 Limpieza y validación automática de datos.  
- 🧠 Clasificación automática de parámetros por tipo.  
- 👩‍💻 Interfaz moderna con **NiceGUI**.  
- 🗂️ Tablas interactivas con selección múltiple y colores dinámicos.  
- 📦 Exportación directa a Excel.  
- ♻️ Eliminación automática de archivos temporales.
