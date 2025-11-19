# main.py

# Architecture: Aplicación Conversor Universal (Keyter / iPro / Cefa / Dixell)

## 1. Overview

Este archivo constituye el **punto de entrada** de la aplicación Conversor Universal, encargada de:

* Inicializar la interfaz NiceGUI
* Gestionar el flujo de subida de archivos
* Seleccionar dinámicamente qué backend procesará los archivos
* Unificar criterios de procesamiento para **Keyter**, **iPro**, **Cefa** y **Dixell**
* Coordinar la comunicación entre UI y lógica de negocio

Este módulo NO procesa datos directamente; delega toda la lógica pesada a los backends correspondientes.

---

## 2. Arquitectura General

```
+------------------------+
|     NiceGUI UI         |
|  (presentation/ui.py)  |
+-----------+------------+
            |
            | process_html_callback
            v
+-----------+------------+
|   unified_process_file |
|  Selección de backend  |
+-----------+------------+
            |
   +--------+--------+-------------+-----------------+
   |                 |             |                 |
   v                 v             v                 v
Keyter Backend   iPro Backend   Cefa Backend   Dixell Backend
(process_html,   (convert_excel) (process_pdf) (process_multiple_pdfs)
 process_excel)       Excel          PDF              PDFs
```

---

## 3. Componentes Principales

### 3.1 `unified_process_file(mode, filename, file_bytes)`

Función centralizadora que decide qué backend usar.

**Responsabilidades:**

* Determinar qué tipo de entrada corresponde según `mode`
* Manejar diferencias entre:

  * Backends de un solo archivo (Keyter, iPro, Cefa)
  * Backend multi-archivo (Dixell)
* Llamar al backend apropiado
* Manejar errores y notificar a la UI

**Backends soportados:**

* **Keyter** → permite HTML o Excel
* **iPro** → solo Excel
* **Cefa** → solo PDF
* **Dixell** → varios PDF simultáneos

---

## 4. Flujo de Procesamiento por Backend

### 4.1 Keyter

```
Si ext ∈ {html, htm} → backend.Keyter.Keyter.process_html
Si ext ∈ {xls, xlsx, xlsm} → backend.Keyter.KeyterNew.process_excel
```

Produce un DataFrame ya alineado al esquema `LIBRARY_COLUMNS`.

### 4.2 iPro

```
backend.iPro.ipro.convert_excel_to_dataframe
```

Convierte Excel iPro en tabla normalizada.

### 4.3 Cefa

```
backend.Cefa.cefa.process_pdf
```

Parser especializado en PDFs con tablas estructuradas con niveles/categorías.

### 4.4 Dixell

```
backend.Dixell.dixell2.process_multiple_pdfs(lista_de_bytes)
```

Backend más complejo: procesa múltiples PDFs, unifica cabeceras y reglas.

---

## 5. Interfaz (NiceGUI)

La interfaz se crea mediante:

```
HTMLConverterUI(process_html_callback=process_with_backend)
```

`process_with_backend` actúa como adaptador entre la UI y el proceso unificado.

**HTMLConverterUI proporciona:**

* Selector de backend
* Cargador de uno o varios archivos según el backend
* Vista previa y exportación de resultados
* Mensajes de error mediante `ui.notify`

---

## 6. Modo de Ejecución

El módulo se comporta como aplicación interactiva NiceGUI.

```
main()          → Construye la UI
ui.run()        → Lanza servidor web local
```

La app soporta recarga automática (`reload=True`).

---

## 7. Control de Errores

* Uso intensivo de `logger.exception` para capturar trazas completas
* Notificaciones en UI si ocurre una excepción en backends
* Prevención de ejecución sin selección de backend

---

## 8. Diseño y Filosofía del Módulo

* **No lógica de transformación**: todo se delega
* **Router de backends**: mapear tipo de archivo a función procesadora
* **Diseño extensible**: se puede agregar un backend nuevo añadiendo un nuevo modo en `unified_process_file`
* **UI independiente**: el backend nunca conoce la UI; la UI solo conoce un callback

---

## 9. Posibles Mejoras Futuras

* Añadir cola asíncrona para procesar PDFs grandes
* Añadir validaciones en la UI (extensiones permitidas por backend)
* Mostrar preview de DataFrames antes de exportar
* Cachear resultados para evitar reprocesar el mismo archivo durante la sesión

---

## 10. Resumen

Este archivo actúa como **punto de orquestación** entre UI y múltiples backends, manteniendo el procesamiento modular, escalable y fácilmente extensible sin comprometer la interfaz visual.

-------------------------------------------------------------------------------------------------------------------------------

# Arquitectura de la Interfaz (HTMLConverterUI)

Este documento describe la arquitectura funcional y estructural de la interfaz construida con **NiceGUI**, cuyo objetivo es convertir y clasificar parámetros provenientes de archivos HTML, Excel o PDF, dependiendo del backend seleccionado.

---

## 📌 1. Estructura General

La interfaz está encapsulada en la clase `HTMLConverterUI`, que actúa como **controlador de UI** siguiendo una arquitectura modular basada en:

* **Gestión de estado interno**
* **Eventos de interacción del usuario**
* **Representación visual mediante componentes NiceGUI**
* **Procesamiento delegado a un callback externo (`process_html_callback`)**

---

## 📌 2. Componentes Principales

### 2.1 Inicialización del estado

* Archivos cargados (`uploaded_file_contents`, `uploaded_file_names`)
* Datos procesados (`processed_data`)
* Datos agrupados (`grouped_data`)
* Backend seleccionado
* Selecciones de filas en ambas tablas

El estado permite que la interfaz sea reactiva y consistente durante la sesión del usuario.

---

### 2.2 Estructura visual

La interfaz se divide en tarjetas visibles secuencialmente:

1. **Selector de backend**
2. **Subida de archivo(s)**
3. **Procesamiento y tabla principal**
4. **Tabla de variables clasificadas**

Estas se muestran u ocultan dinámicamente según el avance del usuario.

---

## 📌 3. Flujo del Usuario

### Paso 1 — Seleccionar Backend

Define:

* Tipos de archivo permitidos
* Permisos automáticos para categories según lógica del backend
* Número de archivos permitidos (e.g. múltiples PDFs para Dixell)

### Paso 2 — Subir archivo(s)

La interfaz:

* Lee bytes del archivo
* Valida según backend
* Activa/desactiva botones según sea necesario

### Paso 3 — Procesar archivo

Uso del callback externo:

* Para backends simples: procesa solo el último archivo
* Para Dixell: procesa lista de PDFs

### Paso 4 — Mostrar Tabla Principal

Incluye:

* Filtros por columna
* Filtro por grupos
* Campos editables directamente en la tabla
* Selectores tipo dropdown para `system_category` y `view`

### Paso 5 — Clasificar variables

Mediante:

* Selección múltiple
* Selector de grupo
* Botón "Asignar grupo"

### Paso 6 — Tabla de Clasificadas

Permite:

* Filtrar
* Buscar
* Eliminar filas
* Vaciar tabla entera
* Exportar

---

## 📌 4. Lógica de Clasificación

La clasificación modifica dinámicamente:

* system_category
* view
* permisos de lectura/escritura (`read`, `write`)
* sampling (mapa dependiente de categoría)

Además la categoría **STATUS** fuerza `view='basic'`.

La categoría **ALARM** limpia view.

La vista **primary** solo puede existir en una fila a la vez.

---

## 📌 5. Sincronización entre Tablas

Cada cambio en la tabla principal:

* Sincroniza el DataFrame interno
* Actualiza tabla de grupos si la fila pertenece a un grupo válido

Cada cambio en la tabla de grupos:

* Sincroniza la tabla principal

Es una sincronización **bidireccional**, manteniendo consistencia del sistema.

---

## 📌 6. Edición de Campos

Los campos editables se generan mediante slots dinámicos que incluyen:

* QInput (texto o número)
* Botón de confirmación

Cada cambio dispara `handle_field_change()`.

Campos editables:

* register
* read
* write
* sampling
* minvalue
* maxvalue
* unit
* description
* name

---

## 📌 7. Exportaciones

La interfaz permite:

### ✔ Exportar parámetros procesados

* Archivo Excel con parámetros completos

### ✔ Exportar parámetros clasificados

* Archivo Excel con solo filas agrupadas

### ✔ Exportar mapa de variables personalizado

* Usuario selecciona columnas específicas

Usa archivos temporales gestión automática de limpieza.

---

## 📌 8. Manejo de eventos NiceGUI

La interfaz depende de múltiples eventos:

* `on_upload`
* `on_change`
* `on_click`
* `on_pagination_change`
* Slots personalizados `estado-change`, `view-change`, `*-change`

Toda la UI se reconstruye o actualiza sin recargarse.

---

## 📌 9. Arquitectura por Módulos

```
HTMLConverterUI
│
├── Estado interno
│   ├── archivos cargados
│   ├── processed_data
│   ├── grouped_data
│   └── seleccionados
│
├── Interfaz gráfica
│   ├── selector de backend
│   ├── módulo de subida
│   ├── módulo de procesamiento
│   ├── tabla principal
│   └── tabla clasificada
│
├── Lógica de negocio
│   ├── clasificación automática
│   ├── asignación de permisos
│   ├── sincronización bidireccional
│   ├── filtros y búsquedas
│   └── paginación
│
└── Exportación
    ├── Excel completo
    ├── Excel de grupos
    └── Mapa personalizado
```

---

## 📌 10. Extensibilidad

La arquitectura está pensada para:

* **Agregar nuevos backends** fácilmente
* **Incorporar nuevas columnas**
* **Modificar lógica de clasificación** sin tocar la UI
* **Agregar nuevos formatos de exportación**

---
---------------------------------------------------------------------------------------
# Listado de Backends
---------------------------------------------------------------------------------------
## Backend Keyter y NewKeyter

# Arquitectura del Backend Keyter

Este documento describe la arquitectura interna de los dos módulos backend:

* **NewKeter.py** → Procesamiento complejo de archivos Excel multipestaña.
* **Keyter.py** → Procesamiento de archivos HTML en tablas.

Ambos producen un DataFrame unificado con formato estándar Keyter.

---

# 1. Objetivo del Backend

El propósito del backend Keyter es transformar archivos de entrada (Excel o HTML) provenientes de diferentes sistemas de climatización/automatización en un único DataFrame con estructura uniforme, que luego se exporta a un Excel "procesado".

El resultado final siempre contiene las columnas definidas en `LIBRARY_COLUMNS`.

---

# 2. Arquitectura General

```
┌────────────────────┐
│ Archivo origen      │  (.xlsx / .html)
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Parser de entrada   │  (Excel o HTML → DataFrames crudos)
└─────────┬──────────┘
          │ múltiples hojas/tablas
          ▼
┌────────────────────────────┐
│ Motor de procesamiento      │  (_process_dataframe)
│ - Limpieza                  │
│ - Asignación de columnas    │
│ - Normalización categorías  │
│ - Permisos R/W              │
│ - length (1bit / 16bit...)  │
│ - sampling                  │
│ - l10n                      │
└─────────┬──────────────────┘
          │ DataFrames procesados
          ▼
┌───────────────────────┐
│ Unificación            │  (concat)
└─────────┬─────────────┘
          │
          ▼
┌──────────────────────────────────────┐
│ Reindexado final (LIBRARY_COLUMNS)   │
└─────────┬────────────────────────────┘
          │
          ▼
┌───────────────────────┐
│ Exportación a Excel    │
└────────────────────────┘
```

---

# 3. Arquitectura de **NewKeter.py** (Procesador Excel)

## 3.1 Flujo de ejecución principal

```
process_excel() → procesa todas las hojas desde memoria
process_excel_file() → procesa un archivo .xlsx desde disco
```

### Pasos:

1. **Cargar archivo Excel** con `openpyxl` permitiendo macros (VBA).
2. **Recorrer todas las hojas** o las tres principales (ANALOG, INTEGER, BOOL).
3. **Detectar bloques por color**: filas verdes marcan inicio de categoría.
4. **Construir DataFrame por hoja** con trazabilidad del nombre de hoja.
5. **Concatenar todos los DataFrames**.
6. **Procesar DataFrame general** mediante `_process_dataframe()`.
7. **Agregar columnas por defecto** y reindexar.
8. **Exportar a Excel.
   **

## 3.2 Estructura interna

### Módulos de procesamiento:

* `_apply_column_mapping1()` → renombre inteligente sensible a mayúsculas.
* `_process_specific_columns()` → limpieza de `offset`, `name`, `unit`, min/max...
* `_process_access_permissions()` → calcula permisos R/W.
* `_determine_data_length()` → asigna 1bit / 16bit / s16.
* `_apply_deep_classification()` → corrige categorías internas.
* `_apply_sampling_rules()` → frecuencia recomendada según tipo.
* `_apply_view_rules()` → vista recomendada (basic/simple).
* `_apply_localization()` → genera JSON l10n multilenguaje.
* `_apply_system_configuratiom()` → duplicados, reglas SYSTEM.
* `_apply_range_rules()` → corrige valores fuera de [-32767, 32767].
* `_add_default_columns()` → columns faltantes.

## 3.3 Características especiales del Excel

* Manejo del **color verde** para identificar grupos/categorías.
* Reparación avanzada de rango (`value` clip).
* Compatibilidad con celdas vacías y headers dinámicos.

---

# 4. Arquitectura de **Keyter.py** (Procesador HTML)

## 4.1 Flujo principal

```
process_html() → recibe bytes de HTML
│
└─> pd.read_html() para extraer tablas
│
├─ Filtrar tabla 0 (suele ser título/cabecera)
└─ Procesar tablas 1..N con _process_dataframe()
```

## 4.2 Diferencias con el procesador Excel

* No existe sistema de colores (no hay "is_green").
* Detecta columnas "Read/Write" o "Direction".
* Normaliza categorías: ANALOG, INTEGER, DIGITAL.
* Análisis de alarmas por patrones en `name`.
* Inserta `l10n` en inglés por defecto.

## 4.3 Funciones principales

* `_apply_column_mapping1()` → mapea columnas HTML propias.
* `_process_access_permissions()` → permisos según tipo.
* `_process_specific_columns()` → normalización `category`, alarmas, duplicados.
* `_apply_deep_classification()` → clasificación avanzada SET_POINT, COMMAND, etc.
* `_determine_data_length()` → 16bit/s16 según min/max.
* `_apply_sampling_rules()`.
* `_apply_view_rules()`.
* `_apply_specific_rules()`.
* `_add_default_columns()`.

---

# 5. Modelo de Datos Final

Ambos backends generan un DataFrame final con las columnas definidas en `LIBRARY_COLUMNS`, asegurando:

* Identificador único (`id`).
* Campos R/W normalizados.
* Categoría final (`system_category`).
* Localización JSON (`l10n`).
* `tags`, `metadata`, `alarm`, etc.
* Columnas opcionales (`mqtt`, `json`, `notes`, etc.).

---

# 6. Principios de Diseño

* **Idempotencia**: procesar dos veces produce el mismo resultado.
* **Tolerancia a errores**: si una hoja fallaba, continúa con el resto.
* **Escalabilidad**: permite añadir nuevos mapeos por reglas.
* **Multi-input**: acepta Excel multipestaña o HTML multitabla.
* **Salida unificada**: siempre mismo formato final.

---

# 7. Posibles Extensiones Futuras

* Integración con API REST.
* Validación de esquemas mediante Pydantic.
* Generación automática de documentación de columnas.
* Modo debug visual mostrando transformaciones paso a paso.

-------------------------------------------------------------------------------------

## Backend iPro

# Arquitectura del Backend iPro

Este documento describe la arquitectura interna del módulo **iPro.py**, encargado de procesar archivos Excel que contienen variables de sistema provenientes de controladores iPro, y convertirlos en un DataFrame estandarizado compatible con la UI general.

---

# 1. Objetivo del Backend iPro

El backend **iPro** procesa archivos Excel que contienen variables del sistema, normalmente con estructuras heterogéneas. Su propósito es:

* Leer todas las hojas del Excel.
* Normalizar columnas y formatos.
* Expandir dimensiones (arrays) en variables individuales.
* Categorizar cada variable en una de las categorías del sistema.
* Aplicar reglas de permisos, tags, máscaras y longitudes.
* Unificar el DataFrame en el formato estándar Keyter.
* Devolver el resultado a la UI sin escribir archivos.

---

# 2. Flujo General del Backend

```
┌────────────────────────┐
│ Bytes de archivo Excel │
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│ Lectura con pd.Excel   │
└──────────┬─────────────┘
           │  hojas
           ▼
┌────────────────────────────────────────┐
│ Procesamiento por hoja                 │
│ - Limpieza columnas                    │
│ - Renombrado                           │
│ - Conversión de registros              │
│ - Expansión de dimension ([1..N])      │
│ - Categorización system_category       │
│ - Permisos R/W                         │
│ - Tags, máscaras, sampling             │
└──────────┬─────────────────────────────┘
           │ concat
           ▼
┌───────────────────────────────┐
│ DataFrame unificado (raw)     │
└──────────┬────────────────────┘
           │ filtro y orden
           ▼
┌───────────────────────────────┐
│ finalize_dataframe()           │
│ - columnas por defecto         │
│ - reindexado LIBRARY_COLUMNS   │
└──────────┬────────────────────┘
           │
           ▼
┌────────────────────────┐
│ DataFrame final iPro   │
└────────────────────────┘
```

---

# 3. Componentes Principales

## 3.1 Carga y lectura del Excel

El backend opera siempre desde **bytes** para integrarse con la UI.

Cada hoja se procesa por separado:

* Se elimina la primera fila (cabecera doble habitual).
* Se normalizan nombres de columnas.
* Se eliminan columnas `Unnamed`.
* Se renombran usando `COLUMN_MAPPING`.

---

# 4. Módulos de Procesamiento Interno

Este backend trabaja por etapas, aplicando funciones puras sobre el DataFrame.

## 4.1 Expansión de dimensiones (`expand_dimension_to_rows_name_bits`)

Convierte filas del tipo:

```
NOMBRE: SONDAS
DIMENSION: [1..4]
```

en 4 filas hijas:

```
SONDAS_1
SONDAS_2
SONDAS_3
SONDAS_4
```

Con reglas:

* Cada hija tiene length=1bit.
* El padre conserva una fila que indica el total de bits.
* Se ajustan registros correlativos.

---

## 4.2 Categorización del sistema (`categorize_system`)

Define `system_category` mediante reglas:

### Por columnas:

* PARAMETROS_CONFIGURACION → CONFIG_PARAMETER
* ALARMAS, WARNINGS → ALARM
* COMANDOS → COMMAND
* ESTADOS → STATUS
* INSTANCIAS/REGISTRO → DEFAULT
* SISTEMA → SYSTEM

### Por nombre:

* PB_, SONDAS_ → ANALOG_INPUT
* AO_, SALIDA_ANALOG_ → ANALOG_OUTPUT
* DI_ → DIGITAL_INPUT
* RELE_, RL_ → DIGITAL_OUTPUT
* VERSION_ → SYSTEM

### Resultado:

Solo se conservan las categorías válidas.

---

## 4.3 Permisos R/W (`apply_rw_permissions`)

Basado en:

* Columna `attribute`: READ, READWRITE, WRITE.
* Tipo de sistema (ALARM, STATUS, COMMAND…)

Resultado:

* R = 3, W = 0
* RW = 3/16 o 0/16 según categoría

---

## 4.4 Reglas de min/max (`apply_min_max`)

Asignación simple:

* COMMAND, CONFIG_PARAMETER, ALARM → min=0, max=1
* Otros tipos → 0/0

---

## 4.5 Normalización de longitudes (`normalize_length`)

Convierte cualquier valor a:

* 1bit, 2bit, 4bit, 8bit, 16bit

---

## 4.6 Eliminación y corrección de nombres duplicados (`fix_duplicate_names`)

Sufijos automáticos: `NAME`, `NAME_2`, `NAME_3`, etc.

---

## 4.7 Lógica de máscaras (`_apply_mask_logic`)

Reglas especiales:

* Para cada padre sin sufijo, asignar máscaras 0x1, 0x2, 0x4... a hijas.
* Si existen más de 16, reiniciar secuencia.

---

## 4.8 Tags (`assign_tags`)

Asigna:

* SISTEMA → ["library_identifier"]
* Otros → []

---

## 4.9 Sampling (`_apply_sampling_rules`)

Frecuencias según categoría:

* ALARM → 30
* STATUS → 60
* ANALOG_INPUT → 60
* COMMAND / CONFIG_PARAMETER → 0

---

## 4.10 Finalización (`finalize_dataframe`)

Aplica valores por defecto y crea el DataFrame final:

* Relleno de metadatos.
* Campo l10n mínimo.
* Orden de columnas por LIBRARY_COLUMNS.

---

# 5. Función Principal `convert_excel_to_dataframe`

Es el punto de entrada para la UI.

Responsabilidades:

1. Leer todas las hojas.
2. Procesar cada una.
3. Unificarlas.
4. Filtrar registros válidos.
5. Ordenar, asignar IDs, fijar view="simple".
6. Ejecutar `finalize_dataframe`.

Devuelve un DataFrame completamente homogéneo.

---

# 6. Arquitectura Resumida en Módulos

```
iPro Backend
│
├── Lectura de Excel
│
├── Limpieza y normalización
│
├── Expansión de dimensiones
│
├── Categorization engine
│   ├── by groups
│   ├── by name
│   ├── tag logic
│   └── system filtering
│
├── Permissions engine
│
├── Mask engine
│
├── Sampling engine
│
├── Normalize bit-length
│
└── Finalization
    ├── default columns
    ├── id + view
    └── reindex
```

---

# 7. Principios de Diseño

* **Pure functions**: cada paso es una transformación aislada.
* **Extensibilidad**: permite agregar nuevas reglas fácilmente.
* **Robustez**: ignora hojas inválidas.
* **Homogeneidad**: siempre regresa formato LIBRARY_COLUMNS.
* **Soporte multilenguaje mínimo** mediante l10n por defecto.

---

# 8. Mejoras Futuras

* Auto-detección avanzada de categorías.
* Validación estructural con Pydantic.
* Mapeos por configuración externa (YAML).
* Módulo de exportación opcional.
* Vista previa visual de jerarquía padre → hijas.

-----------------------------------------------------------------------------------------

## Backend cefa.py

# Arquitectura del Backend CEFA (procesamiento PDF)

Este documento describe la arquitectura interna del módulo **cefa.py**, encargado de procesar archivos PDF que contienen tablas con información de registros Modbus o similares, y convertirlos en un DataFrame estandarizado compatible con el modelo de datos general Keyter.

---

# 1. Objetivo del Backend CEFA

El backend **CEFA** se especializa en:

* Extraer tablas desde PDFs escaneados o generados digitalmente.
* Limpiar encabezados y normalizar columnas.
* Interpretar bloques de escritura/lectura.
* Propagar categorías basadas en duplicados y filas vacías.
* Clasificar cada variable en system_category.
* Aplicar reglas de unidades, rangos, máscaras y permisos.
* Devolver un DataFrame estandarizado según `LIBRARY_COLUMNS`.

Su enfoque es transformar documentos PDF no estructurados en una biblioteca digital normalizada.

---

# 2. Flujo General del Backend

```
┌────────────────────────────┐
│ Bytes PDF                  │
└───────────┬────────────────┘
            ▼
┌────────────────────────────┐
│ pdfplumber.extract_tables  │ → múltiples DataFrames crudos
└───────────┬────────────────┘
            ▼ concat
┌────────────────────────────┐
│ Normalización inicial      │
│ - Limpieza de encabezados  │
│ - Renombrado de columnas   │
│ - Conversión de números    │
└───────────┬────────────────┘
            ▼
┌──────────────────────────────────────┐
│ Motor de Procesamiento CEFA          │
│ - apply_read_write_flags             │
│ - propagate_context                  │
│ - propagate_empty_register_category  │
│ - adjust_system_category             │
│ - _apply_view_rules                  │
│ - _apply_sampling_rules              │
│ - _process_access_permissions        │
│ - _apply_range_rules                 │
│ - _apply_unit_rules                  │
│ - _apply_mask_logic                  │
│ - _apply_length_rules                │
└───────────┬──────────────────────────┘
            ▼
┌────────────────────────────┐
│ Agregar columnas faltantes │
└───────────┬────────────────┘
            ▼
┌──────────────────────────────────────────┐
│ DataFrame final (LIBRARY_COLUMNS)        │
└──────────────────────────────────────────┘
```

---

# 3. Componentes Principales

## 3.1 Lectura del PDF

* Usa **pdfplumber** para extraer todas las tablas de cada página.
* Cada tabla se convierte en un DataFrame.
* Se concatenan todas en un único DataFrame crudo.

## 3.2 Limpieza de encabezados

* La primera fila del PDF suele contener los encabezados.
* Se eliminan duplicados añadiendo sufijos (`col`, `col_1`, `col_2`, ...).
* Se renombran columnas según `COLUMN_MAPPING_PDF`:

  * `DIRECCION` → register
  * `Nombre` → name
  * `Longitud Word Dato` → length
  * `Valores` → description

## 3.3 Normalización inicial

* Se convierten minvalue, maxvalue, offset a numéricos.
* Se limpian strings en register, name, description.

---

# 4. Módulos de Procesamiento Interno

## 4.1 apply_read_write_flags(df)

Interpreta bloques del PDF:

* "LECTURA" activa modo lectura.
* "ESCRITURA" activa modo escritura.
* Los registros posteriores heredan `R` o `W`.
* Las filas de encabezado se eliminan.

## 4.2 propagate_context(df)

Usa duplicados de `register` para crear categorías:

* La primera aparición define un nombre de categoría.
* Las repeticiones heredan la categoría.
* Se eliminan encabezados excepto si empiezan por `AL`.

## 4.3 propagate_empty_register_category(df)

Permite interpretar **bloques vacíos** como encabezados.

* Cuando register está vacío → el name define una categoría.
* Las filas siguientes heredan esa categoría.
* Luego se elimina la fila vacía.

## 4.4 adjust_system_category(df)

Clasificador central basado en reglas:

* category empieza por AL → ALARM
* name empieza por CONTROL, RESET → COMMAND
* name empieza por SP, CONSIGNA → SET_POINT
* P_, NIVEL, TPO, OFFSET → CONFIG_PARAMETER
* ANALOGICAS, CONTROL_EQUIPOS, ESTADO_EQUIPOS → mapeo directo a tipos del sistema

## 4.5 _apply_view_rules()

Define la vista recomendada:

* ALARM → simple
* STATUS → basic
* SET_POINT → simple
* COMMAND → simple

## 4.6 _apply_length_rules()

Longitudes por system_category:

* ALARM → 1bit
* COMMAND → 1bit
* STATUS → f32cdab
* SET_POINT → f32cdab
* DEFAULT → s16

## 4.7 _apply_sampling_rules()

Asigna tiempos de muestreo:

* ALARM → 30
* STATUS → 60
* SET_POINT → 300
* COMMAND → 0

También asigna **tags** cuando system_category = SYSTEM.

## 4.8 _process_access_permissions()

Convierte access_type y system_category en permisos numéricos:

* ALARM → read=1 / write=0
* STATUS → read=4 / write=0
* COMMAND → read=0 / write=6
* SET_POINT → read=3 / write=6

## 4.9 _apply_range_rules()

Rangos según tipo:

* ALARM, COMMAND → [0,1]
* ANALOG_OUTPUT TEMP → [-270,270]
* ANALOG_OUTPUT otros → [0,9999]
* CONFIG_PARAMETER → reglas P_, NIVEL, AJUSTE...
* SET_POINT → [0,9999]

## 4.10 _apply_unit_rules()

Unidades automáticas:

* TEMP → ºC
* PRESION → bar
* CAUDALIMETRO → m3/s

## 4.11 _apply_mask_logic()

Asigna máscaras para registros tipo BIT:

* 0x1, 0x2, 0x4, ..., 0x8000
* Reinicio cada 16 bits

---

# 5. Función Principal: process_pdf(pdf_content)

Responsabilidades:

1. Leer PDF y extraer tablas.
2. Normalizar encabezados.
3. Renombrar columnas y limpiar tipos.
4. Ejecutar el pipeline completo de reglas.
5. Asegurar columnas por defecto.
6. Reindexar según LIBRARY_COLUMNS.
7. Asignar ID secuencial.

Devuelve un DataFrame completamente estandarizado.

---

# 6. Arquitectura Resumida

```
CEFA Backend
│
├── Extracción PDF
│
├── Normalización inicial
│
├── Motor de categorías
│   ├── propagate_context
│   └── propagate_empty_register_category
│
├── Clasificación
│   └── adjust_system_category
│
├── Reglas adicionales
│   ├── read/write
│   ├── ranges
│   ├── units
│   ├── sampling
│   ├── masks
│   └── length
│
└── Finalización
    └── LIBRARY_COLUMNS
```

---

# 7. Principios de Diseño

* **Robustez ante PDFs desestructurados**.
* **Heurísticas fuertes** para interpretar encabezados.
* **Pipeline secuencial** claro y extendible.
* **Normalización consistente** con otros backends.
* **Total alineación con LIBRARY_COLUMNS**.

---

# 8. Mejoras Futuras

* OCR opcional para PDFs sin tablas.
* Reconocimiento automático de estructuras mediante ML.
* Configuración YAML para reglas externas.
* Visualización del árbol de categorías.

--------------------------------------------------------------------------------------------

## Backend dixell2.py

## Arquitectura: Backend dixell2.py

# 1. Visión General

El backend dixell2.py procesa manuales Dixell en PDF que son complejos y multiformato, y extrae tablas de parámetros estructuradas para producir un DataFrame unificado que coincide con el esquema de la biblioteca de la aplicación. Realiza un análisis robusto de PDF, clasificación de secciones, inferencia de encabezados, normalización de valores y generación de metadatos de campos Modbus.

Este backend está diseñado para:

* **Parsear múltiples formatos de tablas PDF heterogéneas.**
* **Detectar límites de secciones mediante reglas de equivalencia de encabezados.**
* **Normalizar estructuras de tabla múltiples (dos familias principales: COLUMNAS_VALIDAS1 y COLUMNAS_VALIDAS2).**
* **Extraer registro, nombre, tipo, rango, unidades, permisos, categorías.**
* **Limpiar texto, eliminar duplicados de nombres de variables y sanear caracteres especiales.**
* **Mapear los datos extraídos al esquema unificado LIBRARY_COLUMNS.**

Es uno de los backends más complejos debido a la estructura extremadamente inconsistente de los documentos Dixell.

---

# 2. Flujo de Datos

# Pipeline de Alto Nivel

Bytes PDF
   ↓
process_dixell()
   ↓  (PyMuPDF)
Detectar zonas de dibujo/color (metadatos opcionales)
   ↓  (pdfplumber)
Extraer tablas crudas página por página
   ↓
Clasificador de secciones usando ENCABEZADOS_EQUIVALENTES
   ↓
Agrupar tablas por sección detectada
   ↓
Para cada sección:
    - Limpiar filas vacías
    - Detectar fila de encabezado
    - Eliminar filas meta (HEX, DEC, etc.)
    - Normalizar nombres de columnas
    - Seleccionar esquema de columnas apropiado (1 o 2)
   ↓
Unir todas las tablas estructuradas
   ↓
Aplicar mapeo de columnas
   ↓
Decodificación de registros (hex → dec)
   ↓
Inferencia de categoría
   ↓
Inferencia de permisos de acceso (R/W)
   ↓
Reglas de muestreo
   ↓
Reglas de vista
   ↓
Derivación de longitud/tipo de dato
   ↓
Inferencia de unidades
   ↓
Inferencia de rangos (min/max)
   ↓
Limpieza de texto + eliminación de caracteres inválidos
   ↓
Reindexado al esquema final → LIBRARY_COLUMNS

--

# 3. Componentes Principales

## 3.1 Extracción de Tablas del PDF

* **Usa PyMuPDF (fitz) para detectar zonas coloreadas — usadas como metadatos opcionales.**
* **Usa pdfplumber como extractor principal porque tolera mejor filas irregulares.**
* **Cada página puede contener:**
   *Secciones nombradas (usando ENCABEZADOS_EQUIVALENTES)*
   *Subtablas crudas añadidas a la última sección detectada*
   *Secciones que caen en SinClasificar si no se detecta encabezado*

## 3.2 Normalización de Secciones

Las secciones se identifican escaneando el texto de la primera fila de cada tabla y haciendo match con **ENCABEZADOS_EQUIVALENTES**. Ejemplos:

```
"ANALOG INPUT" → ANALOG INPUT
"SET POINT", "SP" → SET POINT
"DEVICE STATUS" → Device Status
"ALARM", "ALARMS" → ALARMS
```

Estos nombres canónicos se convierten en la system_category inicial de la variable.

---

# 4. Detección y Mapeo de Encabezados

Las tablas Dixell siguen dos formatos principales:

```
Familia 1 (COLUMNAS_VALIDAS1) → tablas típicas de ingeniería
Familia 2 (COLUMNAS_VALIDAS2) → tablas compactas en formato hexadecimal
```

El backend decide dinámicamente qué mapeo usar por tabla mediante:

* **Escaneo de la primera fila utilizable**
* **Conteo de coincidencias de nombre de columna con cada familia**
* **Selección de la familia con el puntaje más alto**

Luego las columnas se normalizan usando:

* **COLUMN_MAPPING1**
* **COLUMN_MAPPING2**

Estos mapean campos legibles como "Read Register", "Format", "VAR NAME" a campos internos como register, length, name, etc.

# 5. Lógica de Extracción de Valores

## 5.1 Parseo de Registro

Los registros pueden venir de cualquiera de estas columnas:

* **Read Register**
* **Write Register**
* **Register**
* **REGISTER[hex]**

Los registros se normalizan usando hex_to_dec().

# 5.2 Extracción de min/max

Los rangos se extraen de la columna “Type” usando patrones regex:

* **"0°C to 50°C"**

* **"-10 to 200"**

* **"0 bar to 16 bar"**

```
Resultado → minvalue, maxvalue, unit.
``` 

# 5.3 Unidades

La normalización de unidades incluye:

* **°C, C → "°C"**
* **sec, seg → "s"**
* **m → "min"**

--------------------------------------------------------------------------

# 6. Inferencia de Categoría del Sistema

Las reglas están en _process_specific_columns():

* **Basado en nombre de sección → categoría primaria**
* **Basado en coincidencias del nombre (contiene "input" → DIGITAL_INPUT; "output" → DIGITAL_OUTPUT)**
* **Etiquetas agregadas automáticamente para SYSTEM**

---------------------------------------------------------------------------

# 7. Inferencia de Permisos (R/W)

Los permisos se derivan de:

* **Columna R / W o R/W**

* **Sobrescrituras dependientes de categoría:**
     *ALARM → read=1*
     *STATUS → read=1*
     *SET_POINT → read=3, write=16*
     *COMMAND → solo escritura*
     *DIGITAL_OUTPUT → read=1 / write=0*