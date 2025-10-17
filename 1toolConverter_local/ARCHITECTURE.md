# 🏗️ Arquitectura del Proyecto

## Separación de Responsabilidades

Este proyecto sigue una arquitectura limpia con separación clara entre lógica de negocio y presentación.

## 📁 Estructura del Proyecto

```
1toolConverter_local/
│
├── main.py                      # Lógica de negocio y punto de entrada
├── presentation/                # Capa de presentación (UI/UX)
│   ├── __init__.py
│   └── ui.py                    # Componentes visuales y controladores
│
├── requirements.txt             # Dependencias
└── ARCHITECTURE.md             # Este archivo
```

## 🎯 Responsabilidades

### `main.py` - Lógica de Negocio

**Responsabilidades:**
- Procesamiento de archivos HTML
- Transformación de datos
- Validación de datos
- Mapeo de columnas
- Generación de DataFrames

**Funciones principales:**
- `process_html()`: Función principal de procesamiento
- `_process_dataframe()`: Procesa un DataFrame individual
- `_apply_column_mapping()`: Mapea nombres de columnas
- `_process_access_permissions()`: Procesa permisos R/W
- `_process_specific_columns()`: Procesa columnas especiales
- `_determine_data_length()`: Calcula longitud de datos
- `_add_default_columns()`: Agrega valores por defecto

**Constantes:**
- `LIBRARY_COLUMNS`: Definición de estructura de salida
- `COLUMN_MAPPING`: Mapeo de nombres de columnas

### `presentation/ui.py` - Capa de Presentación

**Responsabilidades:**
- Creación de componentes visuales
- Manejo de eventos de usuario
- Actualización de la interfaz
- Gestión del estado de la UI
- Feedback visual al usuario

**Clase principal:**
- `HTMLConverterUI`: Controlador de la interfaz de usuario

**Métodos públicos:**
- `create_ui()`: Crea la interfaz completa
- `handle_upload()`: Maneja la carga de archivos
- `process_file()`: Inicia el procesamiento
- `display_table()`: Muestra los datos en tabla
- `download_excel()`: Genera y descarga Excel

**Métodos privados:**
- `_create_upload_section()`: Sección de carga
- `_create_process_section()`: Sección de procesamiento
- `_create_results_section()`: Sección de resultados
- `_create_table_section()`: Sección de tabla

## 🔄 Flujo de Datos

```
Usuario
  ↓
[UI Component] (presentation/ui.py)
  ↓
[Event Handler] (handle_upload, process_file)
  ↓
[Business Logic] (main.py - process_html)
  ↓
[Data Processing] (transformaciones, validaciones)
  ↓
[Return to UI] (actualización de componentes)
  ↓
Usuario (feedback visual)
```

## 🎨 Patrón de Diseño

### Separación de Capas (Layered Architecture)

1. **Capa de Presentación** (`presentation/`)
   - Maneja todo lo relacionado con la UI
   - No contiene lógica de negocio
   - Utiliza callbacks para invocar lógica de negocio

2. **Capa de Negocio** (`main.py`)
   - Procesa datos
   - No conoce detalles de la UI
   - Retorna datos procesados
