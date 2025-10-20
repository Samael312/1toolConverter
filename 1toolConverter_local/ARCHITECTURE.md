🏗️ Arquitectura del Proyecto: Conversor HTML → Excel
🧱 Separación de Responsabilidades
El proyecto sigue una arquitectura limpia por capas, separando claramente:
- Lógica de negocio: procesamiento, validación y generación de datos.
- Presentación: interfaz de usuario, visualización y control de interacción.
📁 Estructura del Proyecto
1toolConverter_local/
│
├── main.py                      # Lógica de negocio y punto de entrada
├── presentation/                # Capa de presentación (UI/UX)
│   ├── __init__.py
│   └── ui.py                    # Componentes visuales y controladores de eventos
│
├── requirements.txt             # Dependencias del proyecto
└── ARCHITECTURE.md              # Documentación de arquitectura
🎯 Responsabilidades — main.py
Responsabilidades principales:
- Procesar archivos HTML y extraer tablas.
- Limpiar, validar y mapear datos.
- Calcular permisos R/W, offsets y longitudes.
- Normalizar unidades y categorías.
- Combinar resultados en un DataFrame exportable.
- Proveer una interfaz para que la UI invoque la lógica de negocio.
🖥️ Responsabilidades — presentation/ui.py
Responsabilidades principales:
- Gestionar componentes visuales.
- Manejar eventos (carga, procesamiento, clasificación, descarga).
- Mostrar resultados procesados en tablas interactivas.
- Permitir clasificación manual por grupo.
- Controlar exportación a Excel.
🔄 Flujo de Datos Completo
Usuario ↓
[UI Component] (presentation/ui.py)
↓
handle_upload() → process_file() → process_html()
↓
[Business Logic] (main.py)
↓
process_html() → Limpieza y combinación de tablas
↓
DataFrame procesado → display_table() → Usuario descarga Excel

🧮 Procesamiento Interno de Datos
- Extracción con pandas.read_html y BeautifulSoup4.
- Limpieza y normalización.
- Mapeo de columnas.
- Interpretación de permisos R/W.
- Clasificación automática.
- Generación de DataFrame final.

🎨 Patrón de Diseño Aplicado
Arquitectura por Capas (Layered Architecture):
1. Capa de Presentación (UI)
2. Capa de Negocio (main.py)
🚀 Características Clave
🧠 Procesamiento automático de HTML.
🧹 Limpieza configurable.
🧩 Clasificación manual y automática.
🎨 Interfaz NiceGUI.
💾 Exportación Excel.
📊 Sincronización dinámica.
🧾 Logging detallado.
🧭 Ejecución del Proyecto
Instalación:
  pip install -r requirements.txt

Ejecución:
  python main.py

NiceGUI abre la interfaz en http://localhost:8080
📚 Dependencias Principales
- nicegui: Interfaz gráfica web.
- pandas: Limpieza y procesamiento de datos.
- numpy: Cálculos numéricos.
- openpyxl: Exportación a Excel.
- bs4: Interpretación de HTML.
- logging: Registro de eventos.
