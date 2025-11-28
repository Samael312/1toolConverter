from io import BytesIO
from typing import Optional
import pandas as pd
import numpy as np
from nicegui import ui
import logging
from tempfile import NamedTemporaryFile
import os
import asyncio

logger = logging.getLogger(__name__)


class HTMLConverterUI:
    """
    Controlador de la interfaz de usuario para el conversor HTML a Excel.
    Maneja todos los componentes visuales y la interacción con el usuario.
    """

    def __init__(self, process_html_callback):
        self.process_html_callback = process_html_callback
        self.uploaded_file_names: list[str] = []
        self.pagination_main = {'rowsPerPage': 10, 'page': 1, 'sortBy': 'id', 'descending': False}
        self.pagination_group = {'rowsPerPage': 10, 'page': 1, 'sortBy': 'id', 'descending': False}


        # Estado
        self.uploaded_file_contents: list[bytes] = []
        self.processed_data: Optional[pd.DataFrame] = None
        self.grouped_data: Optional[pd.DataFrame] = pd.DataFrame()
        self.backend_selected: Optional[str] = None  
        self.error_filter_active = False
        


        # Componentes UI
        self.backend_selector = None   
        self.upload_component = None   
        self.process_button = None
        self.table = None
        self.table_card = None
        self.group_selector = None
        self.assign_button = None
        self.selected_rows = []
        self.group_table = None
        self.group_table_card = None
        self.delete_rows_button = None
        self.clear_table_button = None
        self.download_button = None
        self.selected_group_rows = []
        


    async def handle_upload(self, e):
        """
        Maneja la carga de archivos.
        - Para backends no-Dixell: reemplaza el archivo actual (solo 1).
        - Para Dixell: permite múltiples archivos (append).
        """
        try:
            logger.info(f"Iniciando carga de archivo: {e.file.name}")
            file_bytes = await e.file.read()
            filename = e.file.name

            # Si el backend es Dixell (multiples PDFs) permitimos append.
            if self.backend_selected == "Dixell":
                self.uploaded_file_contents.append(file_bytes)
                self.uploaded_file_names.append(filename)
            else:
                # Para otros backends, sobrescribimos el archivo (comportamiento 'single file')
                self.uploaded_file_contents = [file_bytes]
                self.uploaded_file_names = [filename]

            logger.info(f"Archivo leído correctamente: {len(file_bytes)} bytes")

            # UI state
            if self.process_button:
                self.process_button.enable()
            if self.download_button:
                self.download_button.disable()
            if self.table_card:
                self.table_card.visible = False
            if self.group_table_card:
                self.group_table_card.visible = False

            ui.notify(f"Archivo '{filename}' cargado correctamente.", type='positive')

        except Exception as ex:
            logger.error(f"Error al cargar archivo: {ex}", exc_info=True)
            ui.notify(f"Error al cargar archivo: {ex}", type='negative')

    def process_file(self, e):
        """Procesa el archivo cargado con el backend seleccionado."""
        if not self.uploaded_file_contents:
            ui.notify("No hay archivo para procesar.", type='negative')
            return

        # Reiniciar tablas y datos previos
        self.processed_data = None
        self.grouped_data = pd.DataFrame()
        self.selected_rows = []
        self.selected_group_rows = []
        self.reset_search_input(e)
        self.reset_group_search_input(e)

        if self.table:
            self.table.rows = []
            self.table.update()
        if self.group_table:
            self.group_table.rows = []
            self.group_table.update()
        if self.table_card:
            self.table_card.visible = False
        if self.group_table_card:
            self.group_table_card.visible = False
        if self.download_button:
            self.download_button.disable()

        # Llamar al backend correcto
        if self.backend_selected == "Dixell":
            df = self.process_html_callback(self.uploaded_file_contents)
        else:
            df = self.process_html_callback(self.uploaded_file_contents[-1])

        if df is not None and not df.empty:
            self.processed_data = df
            self.display_table()
            self.update_group_table()
            if self.download_button:
                self.download_button.enable()

            # --- Detectar filas ya clasificadas ---
            valid_groups1 = [
                'ALARM', 'SET_POINT', 'CONFIG_PARAMETER', 'COMMAND',
                'ANALOG_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT', 'STATUS',
                'SYSTEM'
            ]

            valid_groups2 = ['basic', 'primary']

            auto_grouped1 = df[df['system_category'].isin(valid_groups1)]
            auto_grouped2 = df[df['view'].isin(valid_groups2)]
            combined_grouped = pd.concat([auto_grouped1, auto_grouped2]).drop_duplicates()

            if not combined_grouped.empty:
                self.grouped_data = combined_grouped.reset_index(drop=True)
                ui.notify(
                    f"{len(combined_grouped)} variables clasificadas detectadas automáticamente.",
                    type='positive',
                    timeout=2.5
                )

            ui.notify(f"{len(df)} parámetros procesados.", type='positive')
            self.display_table()
            self.update_group_table()
        else:
            self.processed_data = None
            ui.notify("No se obtuvieron datos del procesamiento.", type='warning')
            if self.download_button:
                self.download_button.disable()
        
        # Convertir DataFrame a lista de diccionarios
            rows = df.to_dict(orient='records')

            # Cargar filas en la tabla
            self.load_rows(rows)

            # Marcar errores
            for row in self.table.rows:
                descripcion = row.get("description", "")
                resultado = self.validate_description_e(descripcion)
                row["error_flag"] = "Error" if resultado is not True else ""

            # Actualizar contador de errores
            error_count = sum(1 for r in self.table.rows if r.get("error_flag") == "Error")
            self.error_label.set_text(f"Errores: {error_count}")
            self.filter_button.set_text(f"Errores: {error_count}")

            # Refrescar tabla
            self.table.update()
    
    def load_rows(self, rows):
        for r in rows:
            r["error_flag"] = ""
        self.table.rows = rows
    
    def remove_uploaded_files(self):
        """Elimina todos los archivos subidos y resetea el estado."""
        self.uploaded_file_contents = []
        self.uploaded_file_names = []
        self.processed_data = None
        self.grouped_data = pd.DataFrame()
        self.selected_rows = []
        self.selected_group_rows = []
        if self.table:
            self.table.rows = []
            self.table.update()
        if self.group_table:
            self.group_table.rows = []
            self.group_table.update()
        if self.table_card:
            self.table_card.visible = False
        if self.group_table_card:
            self.group_table_card.visible = False
        if self.download_button:
            self.download_button.disable()
        if self.process_button:
            self.process_button.disable()
        ui.notify("Archivos eliminados.", type='info')
    
    def mark_error_flags(self, rows):
        """Marca error_flag = 1 para filas con descripción inválida."""
        for row in rows:
                descripcion = row.get("description", "")
                resultado = self.validate_description_e(descripcion)
                row["error_flag"] = 0 if resultado is True else 1
        return rows


    def display_table(self):
        """Actualiza la tabla existente con los datos procesados."""
        if self.processed_data is None:
            ui.notify("No hay datos procesados.", type='warning')
            return

        # --- Sincroniza system_category desde grouped_data ---
        df_display = self.processed_data.copy()

        if self.grouped_data is not None and not self.grouped_data.empty:
            category_map = dict(zip(
                self.grouped_data['id'].astype(str),
                self.grouped_data['system_category']
            ))

            # Solo actualizar las filas que aparecen en grouped_data
            df_display.loc[
                df_display['id'].astype(str).isin(category_map.keys()),
                'system_category'
            ] = df_display['id'].astype(str).map(category_map)


        cols = ["id", "estado", "register", "name", "description", "system_category",
                "read", "write", "sampling", "minvalue", "maxvalue", "unit","view", "error_flag"]

        rows = df_display.replace({np.nan: ''}).to_dict('records')

        # 🔹 Marcar errores automáticamente al cargar
        rows = self.mark_error_flags(rows)
        self.update_error_counter()


        for row in rows:
            row['_isGrouped'] = bool(row.get('system_category'))

        self.table.columns = [
            {
                'name': c,
                'label': c.replace('_', ' ').title(),
                'field': c,
                'sortable': True,
            } for c in cols
        ]
        self.table.rows = rows
        self.table.update()

        # Mostrar tarjetas
        if self.table_card:
            self.table_card.visible = True
        if self.group_table_card:
            self.group_table_card.visible = True

    def download_excel(self):
        if self.processed_data is None or self.processed_data.empty:
            ui.notify("No hay datos para exportar.", type='warning')
            return
        try:
            if self.grouped_data is not None and not self.grouped_data.empty:
                df_to_export = self.grouped_data
                file_name = 'parametros_clasificados.xlsx'
            else:
                df_to_export = self.processed_data
                file_name = 'parametros_convertidos.xlsx'

            if 'category' in df_to_export.columns:
               df_to_export['category'] = np.nan
            
            if 'id' in df_to_export.columns:
                df_to_export['id']=np.nan

            with NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                with pd.ExcelWriter(tmp.name, engine='openpyxl') as writer:
                    df_to_export.to_excel(writer, sheet_name="Parametros", index=False)
                tmp.flush()
                file_path = tmp.name

            ui.download(file_path, filename=file_name)
            ui.notify(f"Descarga iniciada: {file_name}", type='info')

            async def cleanup_file(path):
                await asyncio.sleep(60)
                if os.path.exists(path):
                    os.remove(path)
                    logger.debug(f"Archivo temporal eliminado: {path}")

            ui.timer(1.0, lambda: asyncio.create_task(cleanup_file(file_path)), once=True)

        except Exception as ex:
            logger.error(f"Error al generar Excel: {ex}", exc_info=True)
            ui.notify(f"Error al generar Excel: {ex}", type='negative')

    def create_ui(self):
        # Fondo suave general
        ui.query('body').style('background-color: #f8fafc;') 
        ui.dark_mode().set_value(False)
        
        # Estilos CSS personalizados
        ui.add_head_html("""
        <style>
        .q-table td, .q-table th {
            white-space: normal !important;
            word-wrap: break-word !important;
            line-height: 1.4em;
            vertical-align: middle;
            padding: 8px 12px !important;
        }
        .q-table__card {
            box-shadow: none !important;
            border: 1px solid #e2e8f0;
        }
        .q-table__container {
            max-height: 650px;
        }
        /* Título de la tabla sticky */
        .q-table th {
            position: sticky;
            top: 0;
            background: #f1f5f9;
            z-index: 1;
            font-weight: 700;
            color: #334155;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
        }
        </style>
        """)

        # --- HEADER PROFESIONAL ---
        with ui.header().classes('bg-slate-800 text-white shadow-md q-py-sm items-center justify-between'):
            with ui.row().classes('items-center gap-3 q-pl-md'):
                ui.icon('library_books', size='md').classes('text-blue-400')
                with ui.column().classes('gap-0'):
                    ui.label('Creador de Librerías').classes('text-xl font-bold tracking-tight')
                    ui.label('Herramienta de conversión y gestión').classes('text-xs text-slate-400')
            
            # Espacio para info de usuario o versión si fuera necesario
            ui.label('v1.0').classes('q-pr-md text-slate-500 text-xs')

        # --- CONTENEDOR PRINCIPAL ---
        with ui.column().classes('w-full max-w-7xl mx-auto p-6 gap-8'):
            
            # PASO 0: BACKEND
            with ui.card().classes('w-full p-6 rounded-xl shadow-sm border border-slate-200 bg-white'):
                with ui.row().classes('items-center gap-2 mb-4'):
                    ui.icon('settings', size='sm').classes('text-slate-600')
                    ui.label('0. Configuración Inicial').classes('text-lg font-semibold text-slate-800')
                
                ui.separator().classes('mb-6')
                
                with ui.row().classes('items-center gap-4'):
                    self.backend_selector = ui.select(
                        options=['Keyter', 'iPro', 'Cefa', 'Dixell'],
                        label='Selecciona Backend',
                        on_change=self.handle_backend_selection
                    ).props('outlined dense options-dense behavior="menu"').classes('w-64')
                    
                    ui.label('Selecciona el sistema de entrada para configurar los formatos aceptados.').classes('text-sm text-slate-500 italic')

            self._create_upload_section()
            self._create_process_section()
            self._create_table_section()
            self._create_group_table_section()

            # Estado inicial desactivado
            if self.process_button: self.process_button.disable()
            if self.upload_component: self.upload_component.disable()
            if self.table_card: self.table_card.visible = False
            if self.group_table_card: self.group_table_card.visible = False

    def handle_backend_selection(self, e):
        """🆕 Activa o desactiva la UI según el backend seleccionado."""
        backend = e.value
        self.backend_selected = backend

        # 🔹 Reiniciar interfaz al cambiar de backend
        self._reset_ui_state()

        # 🔹 Reiniciar también los filtros de búsqueda
        try:
            self.reset_search_input(e)
            self.reset_group_search_input(e)
        except Exception as ex:
            logger.warning(f"No se pudieron reiniciar los filtros de búsqueda: {ex}")

        if not backend:
            ui.notify("Selecciona un backend para continuar.", type='warning')
            if self.upload_component:
                self.upload_component.disable()
            if self.process_button:
                self.process_button.disable()
            return

        # Configurar tipo de archivo permitido según backend
        if backend == 'Keyter':
            file_accept = '.xlsx,.xls,.xlsm,.html,.htm'
        elif backend == 'iPro':
            file_accept = '.xlsx'
        elif backend == 'Cefa':
            file_accept = '.pdf'
        elif backend == 'Dixell':
            file_accept = '.pdf'
        elif backend == 'General':
            file_accept = '.xlsx,.xls,.xlsm,.html,.htm,.pdf'
        else:
            file_accept = ''

        if self.upload_component:
            self.upload_component.enable()
            self.upload_component.props(f'accept="{file_accept}"')

        ui.notify(
            f"Backend seleccionado: {backend}. Ahora puedes subir un archivo {file_accept}.",
            type='positive'
        )



    def _reset_ui_state(self):
        """Reinicia el estado de la interfaz al cambiar de backend."""
        # Limpiar archivo subido
        self.uploaded_file_contents = []
        self.uploaded_file_names = []

        # Limpiar DataFrames
        self.processed_data = None
        self.grouped_data = pd.DataFrame()

        # Limpiar tablas visuales
        if self.table:
            self.table.rows = []
            self.table.update()

        if self.group_table:
            self.group_table.rows = []
            self.group_table.update()

        # Ocultar las tarjetas
        if self.table_card:
            self.table_card.visible = False
        if self.group_table_card:
            self.group_table_card.visible = False

        # Deshabilitar botones
        if self.download_button:
            self.download_button.disable()
        if self.process_button:
            self.process_button.disable()
        
        self._recreate_upload_component()

        ui.notify("Interfaz reiniciada tras cambiar de backend.", type='info', timeout=2.5)

    def _recreate_upload_component(self):
        """Recrea el componente de subida para limpiar archivos cargados y mantener el estilo."""
        if hasattr(self, "upload_container"):
            self.upload_container.clear()  # Limpia el contenedor anterior

        with self.upload_container:
            # Configuración base del componente
            max_files = 1
            accept_types = ""

            # 🔹 Configurar según backend seleccionado
            if self.backend_selected == "Keyter":
                accept_types = ".xls,.xlsx,.xlsm,.html,.htm"
            elif self.backend_selected == "iPro":
                accept_types = ".xlsx"
            elif self.backend_selected == "Cefa":
                accept_types = ".pdf"
            elif self.backend_selected == "Dixell":
                accept_types = ".pdf"
                max_files = 2  
            elif self.backend_selected == "General":
                accept_types = ".xls,.xlsx,.xlsm,.html,.htm,.pdf"
            else:
                accept_types = ""
                max_files = 0

            # 🔹 Crear componente de subida
            self.upload_component = ui.upload(
                label="Arrastra tu archivo aquí o haz clic",
                auto_upload=True,
                max_files=max_files,
            ).props(f'flat bordered accept="{accept_types}" color="primary"').classes(
                'w-full h-auto min-h-[120px] rounded-lg border-2 border-dashed border-slate-300 '
                'bg-slate-50 hover:bg-blue-50 hover:border-blue-400 transition-colors duration-300'
            )

            # Asociar el manejador de subida
            self.upload_component.on_upload(self.handle_upload)
            self.upload_component.on('removed', lambda e: self.remove_uploaded_files())

            # 🔹 Deshabilitar si el backend no tiene formatos válidos
            if not accept_types:
                self.upload_component.disable()



    def _create_upload_section(self):
        # Usamos card con bordes redondeados y sombra suave
        with ui.card().classes('w-full p-6 rounded-xl shadow-sm border border-slate-200 bg-white'):
            with ui.row().classes('items-center gap-2 mb-2'):
                ui.icon('cloud_upload', size='sm').classes('text-slate-600')
                ui.label('1. Cargar Archivo').classes('text-lg font-semibold text-slate-800')
            
            ui.separator().classes('mb-6')
            self.upload_container = ui.column().classes('w-full')
            self._recreate_upload_component()



    def _create_process_section(self):
         with ui.card().classes('w-full p-6 rounded-xl shadow-sm border border-slate-200 bg-white'):
            with ui.row().classes('items-center justify-between w-full'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('build_circle', size='sm').classes('text-slate-600')
                    ui.label('2. Procesamiento').classes('text-lg font-semibold text-slate-800')
                
                self.process_button = ui.button(
                    'Procesar Archivo',
                    on_click=self.process_file,
                    icon='play_arrow'
                ).props('unelevated rounded color=primary').classes('px-6 py-2 font-bold shadow-md')
                self.process_button.disable()

    
    def validate_description_e(self, texto):
        if texto is None:
            return "El texto está vacío"

        # 1. Limpiar caracteres no válidos y comparar
        cleaned = re.sub(r"[^a-zA-Z0-9\s\.,;:_\-/'º°ª|@#!·$=?¿%&C-_çÇ<>~¬*-+–ΣβßηθΘδΔφΦωΩτΣπΠεØñÑáéíóúÁÉÍÓÚ()]", "", texto)
        if cleaned != texto:
            return "Caracteres no permitidos encontrados"

# 2. Validar longitud máximagit  absoluta
        if len(texto) == 0:
            self.download_button.disable()
            return "La descripcion no puede estar vacia"

        # 2. Validar longitud máxima absoluta
        if len(texto) > 150:
            self.download_button.disable()
            return "Máximo 150 caracteres permitidos"

        # 3. Límite suave
        if len(texto) > 60:
            self.download_button.disable()
            return "La descripción supera el límite recomendado de 60 caracteres"

        return True
    

    
    def handle_error_click(self, e):
        error_label = None

        with ui.dialog() as dialog_error, ui.card():
            error_label = ui.label('Información del error')
            ui.button('Cerrar', on_click=dialog_error.close)

        # Ahora SÍ obtienes props.row
        row = e.args if isinstance(e.args, dict) else e.args[0]

        # row AHORA es el diccionario que Vue envió
        description = row.get('description', '')

        resultado = self.validate_description_e(description)

        if resultado is not True:
            error_label.set_text(resultado)
            dialog_error.open()
    
        
    
    def load_rows(self, rows):
        # Inicializar la clave
        for r in rows:
            r["error_flag"] = ""

        self.table.rows = rows

        # 🔥 Aquí sí se puede validar porque ya hay filas cargadas
        self.update_error_counter()


    def add_editable_slot(self, field_name: str, label: str, input_type: str = "text", max_length: int = 150, 
                          style_overrides: dict | str | None = None, input_style: str = "width: auto; min-width: 1ch;", 
                          validator=None, placeholder: str | None = None):
        # ... (LÓGICA INTACTA, SOLO AJUSTES VISUALES EN HTML)
        event_name = f"{field_name}-change"
        slot_name = f"body-cell-{field_name}"

        if isinstance(style_overrides, dict):
            style_str = "; ".join(f"{k}: {v}" for k, v in style_overrides.items())
        elif isinstance(style_overrides, str):
            style_str = style_overrides
        else:
            style_str = "width: 100%;"

        placeholder_text = placeholder or ""
        slot_html = f"""
        <q-td :props="props">
          <div style="display: flex; flex-direction: column; gap: 4px;">
            <q-input dense outlined bg-color="white" type="{input_type}" v-model="props.row.{field_name}"
              placeholder="{placeholder_text}" maxlength="{max_length}" style="{style_str}" input-style="{input_style}" />
            <q-btn dense flat round size="sm" 
              :icon="props.row.description && props.row.description.length <= 60 && /^[a-zA-Z0-9\s\.,;:_\-/'º°ª|@#!·$=?¿%&C-_çÇ<>~¬*-+–ΣβßηθΘδΔφΦωΩτΣπΠεØñÑáéíóúÁÉÍÓÚ()]*$/.test(props.row.description) ? 'check_circle' : 'cancel'" 
              :color="props.row.description && props.row.description.length <= 60 && /^[a-zA-Z0-9\s\.,;:_\-/'º°ª|@#!·$=?¿%&C-_çÇ<>~¬*-+–ΣβßηθΘδΔφΦωΩτΣπΠεØñÑáéíóúÁÉÍÓÚ()]*$/.test(props.row.description) ? 'positive' : 'negative'" 
              @click="props.row.description && props.row.description.length <= 60 && /^[a-zA-Z0-9\s\.,;:_\-/'º°ª|@#!·$=?¿%&C-_çÇ<>~¬*-+–ΣβßηθΘδΔφΦωΩτΣπΠεØñÑáéíóúÁÉÍÓÚ()]*$/.test(props.row.description) ? $parent.$emit('{event_name}', props.row) :$parent.$emit('openError', props.row)"
            />
          </div>
        </q-td>
        """
        self.table.add_slot(slot_name, slot_html)

        def wrapped_handler(e, fn=field_name, lbl=label):
            self.toggle_error_filter(e)
            self.update_error_counter()
            if validator:
                args = getattr(e, 'args', e)
                row = args if isinstance(args, dict) else args[0]
                val = row.get(fn)
                result = validator(val)
                if result is False: ui.notify(f"Valor inválido para {lbl}", type='warning'); return
                elif isinstance(result, str): ui.notify(result, type='warning'); return
            self.handle_field_change(e, fn, lbl)

        self.table.on(event_name, wrapped_handler)

        logger.info(f"✅ Slot editable '{field_name}' registrado (tipo={input_type})")


    def _create_table_section(self):
        with ui.card().classes('w-full p-0 rounded-xl shadow-md border border-slate-200 overflow-hidden bg-white') as table_card:
            # Header de la tarjeta
            with ui.row().classes('p-4 bg-slate-50 border-b border-slate-200 items-center justify-between'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('table_chart', size='sm').classes('text-slate-600')
                    ui.label("3. Parámetros Detectados").classes('text-lg font-semibold text-slate-800')
                
                # Botón de errores destacado
                self.error_button = ui.button("Errores: 0", on_click=self.toggle_error_filter).props("icon=warning color=negative outline rounded")

            self.table_card = table_card
            self.table_card.visible = False

            # Filtros en barra gris claro
            with ui.row().classes('p-4 gap-4 items-end bg-white'):
                self.search_column_selector = ui.select(
                    options=['register', 'name', 'description', 'system_category'], value='name', label='Buscar columna',
                    on_change=self.reset_search_input
                ).props('outlined dense options-dense').classes('w-48')

                self.search_input = ui.input(placeholder='Escribe para buscar...', on_change=self.apply_search_filter
                ).props('outlined dense clearable').classes('flex-1 min-w-[100px]')

                self.category_filter = ui.select(
                    options=['ALARM', 'SET_POINT', 'CONFIG_PARAMETER', 'COMMAND', 'ANALOG_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT', 'DEFAULT', 'STATUS', 'SYSTEM'],
                    multiple=True, label='Filtrar por grupo', clearable=True, on_change=self.apply_category_filter
                ).props('outlined dense use-chips clearable').classes('w-full md:w-1/3')

            # Tabla
            cols = ["id", "register", "name", "description", "read", "write", "sampling", "minvalue", "maxvalue", "unit", "view", "error_flag"]
            
            self.table = ui.table(
                columns=[{'name': c, 'label': c.replace('_', ' ').title(), 'field': c, 'sortable': True} for c in cols],
                rows=[],
                row_key='id',
                selection='multiple',
                pagination=self.pagination_main,
                on_pagination_change=self.handle_main_pagination,
            ).classes('w-full').props('flat dense') # Quitamos bordered aquí porque el card ya tiene borde

            self.table.on('selection', self.handle_selection)
            self.table.on('openError', self.handle_error_click)

            # --- SLOT: ESTADO (Category) con diseño de Chips ---
            self.table.add_slot('body-cell-estado', '''
            <q-td key="estado" :props="props">
                <q-select v-model="props.row.system_category" dense borderless emit-value map-options
                    :options="['ALARM', 'SET_POINT', 'CONFIG_PARAMETER', 'COMMAND', 'ANALOG_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT', 'STATUS', 'SYSTEM']"
                    @update:model-value="$parent.$emit('estado-change', props.row)">
                    <template v-slot:selected-item="scope">
                        <q-chip dense :style="{backgroundColor: ({
                            'ALARM': '#ef4444', 'SET_POINT': '#3b82f6', 'CONFIG_PARAMETER': '#06b6d4', 'COMMAND': '#a855f7',
                            'ANALOG_INPUT': '#22c55e', 'ANALOG_OUTPUT': '#15803d', 'DIGITAL_INPUT': '#3b82f6', 'DIGITAL_OUTPUT': '#1e293b',
                            'STATUS': '#0f766e', 'SYSTEM': '#eab308'
                        }[props.row.system_category] || '#94a3b8'), color: 'white'}">
                            {{ props.row.system_category }}
                        </q-chip>
                    </template>
                </q-select>
            </q-td>
            ''')
            self.table.on('estado-change', self.handle_estado_change)

            # --- SLOT: VIEW ---
            self.table.add_slot('body-cell-view', '''
            <q-td key="view" :props="props">
                <q-select v-model="props.row.view" dense borderless emit-value map-options
                    :options="['basic', 'simple', 'primary']"
                    @update:model-value="$parent.$emit('view-change', props.row)">
                    <template v-slot:selected-item="scope">
                         <q-badge :color="({ 'basic': 'black', 'primary': 'blue', 'simple': 'teal' }[props.row.view] || 'grey')">
                            {{ props.row.view }}
                        </q-badge>
                    </template>
                </q-select>
            </q-td>
            ''')
            self.table.on('view-change', self.handle_view_change)

            # Re-añadir slots editables con estilo
            self.add_editable_slot('register', 'Register', input_type='number', style_overrides={'width': '80px'})
            self.add_editable_slot('read', 'Read', input_type='number', style_overrides={'width': '60px'})
            self.add_editable_slot('write', 'Write', input_type='number', style_overrides={'width': '60px'})
            self.add_editable_slot('sampling', 'Sampling', input_type='number', style_overrides={'width': '60px'})
            self.add_editable_slot('minvalue', 'Min', input_type='number', style_overrides={'width': '70px'})
            self.add_editable_slot('maxvalue', 'Max', input_type='number', style_overrides={'width': '70px'})
            self.add_editable_slot('unit', 'Unit', style_overrides={'width': '50px'}, placeholder="°C")
            self.add_editable_slot('description', 'Description', style_overrides={'min-width': '250px'})
            self.add_editable_slot('name', 'Nombre', style_overrides={'min-width': '150px'})

            # --- Panel de Acciones en Lote (Pie de tabla) ---
            with ui.row().classes('p-4 bg-slate-50 border-t border-slate-200 gap-4 items-center justify-between'):
                with ui.row().classes('items-center gap-3'):
                    self.group_selector = ui.select(
                        options=['ALARM', 'SET_POINT', 'CONFIG_PARAMETER', 'COMMAND', 'ANALOG_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT', 'STATUS', 'SYSTEM'],
                        label='Asignar Grupo a Selección'
                    ).props('outlined dense options-dense behavior="menu"').classes('w-64 bg-white')
                    
                    self.assign_button = ui.button('Asignar', on_click=self.assign_group_to_selection).props('unelevated color=primary icon=low_priority')
                
                ui.button('Agregar Fila Manual', on_click=self.add_new_row).props('outline color=secondary icon=add')
                ui.button('Generar Mapa de Variables', on_click=self.download_variable_map).props('outline color=info icon=map')

        self.table.on('click', lambda e: logger.info("✅ Evento click detectado en tabla"))

    def load_rows(self, rows):
        for row in rows:
            row["error_flag"] = ""  # Inicialmente
            descripcion = row.get("description", "")
            resultado = self.validate_description_e(descripcion)
            if resultado is not True:
                row["error_flag"] = "Error"
        self.table.rows = rows
        self.update_error_counter()
        self.table.update()

    def update_error_counter(self):
        """Actualiza el botón de contador con el número real de errores."""
        error_count = sum(r.get("error_flag", 0) for r in self.table.rows)
        if error_count > 0:
            self.download_button.disable()
        else:
            self.download_button.enable()
        
        if hasattr(self, "error_button"):
            self.error_button.set_text(f"Errores: {error_count}")
    
    def toggle_error_filter(self, e):
        """Activa/desactiva el filtro de errores."""
        self.error_filter_active = not self.error_filter_active

        if self.error_filter_active:
            # 🔥 FILTRAR SOLO ERRORES
            filtered = [r for r in self.table.rows if r.get("error_flag", 0) == 1]
            self.table.rows = filtered

            # Cambiar a rojo oscuro
            self.error_button.props("color=positive")

        else:
            # 🔥 Restaurar todas las filas desde processed_data
            df_display = self.processed_data.copy()
            rows = df_display.replace({np.nan: ''}).to_dict('records')
            rows = self.mark_error_flags(rows)

            self.table.rows = rows

            # Rojo normal
            self.error_button.props("color=negative outlined")

        self.update_error_counter()
        self.table.update()


    def _create_group_table_section(self):
        with ui.card().classes('w-full p-0 rounded-xl shadow-md border border-slate-200 overflow-hidden bg-white mt-6') as group_card:
            # Header
            with ui.row().classes('p-4 bg-slate-50 border-b border-slate-200 items-center gap-2'):
                ui.icon('category', size='sm').classes('text-slate-600')
                ui.label("4. Clasificación Final").classes('text-lg font-semibold text-slate-800')

            self.group_table_card = group_card
            self.group_table_card.visible = False

            # Filtros
            with ui.row().classes('p-4 gap-4 bg-white'):
                self.group_search_column_selector = ui.select(
                    options=['register', 'name', 'description', 'system_category'], value='name', label='Buscar columna',
                    on_change=self.reset_group_search_input
                ).props('outlined dense').classes('w-48')
                self.group_search_input = ui.input(placeholder='Buscar...', on_change=self.apply_group_search_filter).props('outlined dense clearable').classes('flex-1')
                self.group_category_filter = ui.select(
                    options=['ALARM', 'SET_POINT', 'CONFIG_PARAMETER', 'COMMAND', 'ANALOG_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT', 'DEFAULT', 'STATUS', 'SYSTEM'],
                    multiple=True, label='Filtrar grupos', clearable=True, on_change=self.apply_group_category_filter
                ).props('outlined dense use-chips').classes('w-1/3')

            self.group_table = ui.table(
                columns=[], rows=[], row_key='id', selection='multiple',
                pagination=self.pagination_group, on_pagination_change=self.handle_group_pagination,
            ).classes('w-full').props('flat dense')
            self.group_table.on('selection', self.handle_group_selection)

            # Footer con acciones
            with ui.row().classes('p-4 bg-slate-50 border-t border-slate-200 justify-between items-center'):
                with ui.row().classes('gap-2'):
                    self.delete_rows_button = ui.button('Eliminar Selección', on_click=self.delete_selected_group_rows).props('outline color=negative icon=delete')
                    self.clear_table_button = ui.button('Limpiar Todo', on_click=self.clear_group_table).props('flat color=warning icon=delete_forever')
                
                self.download_button = ui.button('Descargar Excel Final', on_click=self.download_excel).props('unelevated color=positive icon=download size=md').classes('px-6 shadow-md')
                self.download_button.disable()

            self.group_table_card = group_card
            self.group_table_card.visible = False

    # --- Manejo de selección y agrupamiento ---
    def handle_selection(self, e):
        try:
            args = getattr(e, 'args', e)
            payload = None
            if isinstance(args, (list, tuple)):
                payload = args[0] if len(args) == 1 else args
            else:
                payload = args

            selected_now = []
            if isinstance(payload, dict):
                selected_now = payload.get('value') or payload.get('rows') or payload.get('selected', [])
            elif isinstance(payload, (list, tuple)):
                selected_now = list(payload)
            elif payload is not None:
                selected_now = [payload]

            new_selection = []
            for item in selected_now:
                if isinstance(item, dict):
                    new_selection.append(item.get('id'))
                elif isinstance(item, str):
                    new_selection.append(item)

            if hasattr(self.table, 'selected'):
                current_selection = [
                    row['id'] if isinstance(row, dict) and 'id' in row else row
                    for row in getattr(self.table, 'selected', [])
                ]
                self.selected_rows = current_selection
            else:
                self.selected_rows = new_selection

            self.selected_rows = list(dict.fromkeys(self.selected_rows))
            logger.debug(f"Selección actualizada: {self.selected_rows}")
        except Exception as ex:
            logger.exception(f"Error procesando selección: {ex}")
            self.selected_rows = []

    def handle_group_selection(self, e):
        try:
            args = getattr(e, 'args', e)
            payload = None
            if isinstance(args, (list, tuple)):
                payload = args[0] if len(args) == 1 else args
            else:
                payload = args

            selected_now = []
            if isinstance(payload, dict):
                selected_now = payload.get('value') or payload.get('rows') or payload.get('selected', [])
            elif isinstance(payload, (list, tuple)):
                selected_now = list(payload)
            elif payload is not None:
                selected_now = [payload]

            new_selection = []
            for item in selected_now:
                if isinstance(item, dict):
                    new_selection.append(item.get('id'))
                elif isinstance(item, str):
                    new_selection.append(item)

            if hasattr(self.group_table, 'selected'):
                current_selection = [
                    row['id'] if isinstance(row, dict) and 'id' in row else row
                    for row in getattr(self.group_table, 'selected', [])
                ]
                self.selected_group_rows = current_selection
            else:
                self.selected_group_rows = new_selection

            self.selected_group_rows = list(dict.fromkeys(self.selected_group_rows))
            logger.debug(f"Selección actualizada en tabla de grupos: {self.selected_group_rows}")
        except Exception as ex:
            logger.exception(f"Error procesando selección en tabla de grupos: {ex}")
            self.selected_group_rows = []

    def assign_group_to_selection(self):
        if not self.selected_rows:
            ui.notify('Selecciona una o más filas primero.', type='warning')
            return

        group = self.group_selector.value
        if not group:
            ui.notify('Selecciona un grupo.', type='warning')
            return

        try:
            # Convertir ids seleccionados a string
            selected_as_str = [str(x) for x in self.selected_rows]

            # Filtrar filas seleccionadas del DataFrame original
            selected_rows_df = self.processed_data.loc[
                self.processed_data['id'].astype(str).isin(selected_as_str)
            ].copy()

            # Asignar nuevo grupo
            selected_rows_df['system_category'] = group

            # Si se asigna STATUS, poner view como basic
            if group == 'STATUS':
                selected_rows_df['view'] = 'basic'
                self.processed_data.loc[
                    self.processed_data['id'].astype(str).isin(selected_as_str), 'view'
                ] = 'basic'
            
            if group == 'ALARM':
                selected_rows_df['view'] = np.nan
                self.processed_data.loc[
                    self.processed_data['id'].astype(str).isin(selected_as_str), 'view'
                ] = np.nan


            # Si la tabla de grupos está vacía, se inicializa
            if self.grouped_data is None or self.grouped_data.empty:
                self.grouped_data = selected_rows_df
            else:
                # Asegurar que las columnas coincidan
                all_cols = list(self.grouped_data.columns)
                selected_rows_df = selected_rows_df.reindex(columns=all_cols, fill_value=np.nan)

                # Convertimos los IDs a string para asegurar coincidencia
                self.grouped_data['id'] = self.grouped_data['id'].astype(str)
                selected_rows_df['id'] = selected_rows_df['id'].astype(str)

                # Eliminar filas existentes con esos IDs (para sobrescribir)
                self.grouped_data = self.grouped_data[
                    ~self.grouped_data['id'].isin(selected_rows_df['id'])
                ]

                # Agregar filas nuevas o actualizadas
                self.grouped_data = pd.concat(
                    [selected_rows_df, self.grouped_data],
                    ignore_index=True
                )

            # Actualizamos ambas tablas
            self.update_group_table()
            self.display_table()

            # Limpiamos la selección
            self.selected_rows = []
            if hasattr(self.table, 'selected'):
                self.table.selected = []
                self.table.update()

            ui.notify(f'Se asignó "{group}" a {len(selected_rows_df)} fila(s).', type='positive')

        except Exception as ex:
            logger.exception(f"Error al asignar grupo: {ex}")
            ui.notify(f"Error al asignar grupo: {ex}", type='negative')


    def delete_selected_group_rows(self):
        if not self.selected_group_rows:
            ui.notify('Selecciona una o más filas para eliminar.', type='warning')
            return

        try:
            before_count = len(self.grouped_data)
            
            # Convertir la selección a strings (por si acaso)
            ids_to_delete = [str(i) for i in self.selected_group_rows]

            # Filtrar filas que NO están seleccionadas
            self.grouped_data = self.grouped_data[~self.grouped_data['id'].astype(str).isin(ids_to_delete)]
            
            # Reiniciar índice
            self.grouped_data.reset_index(drop=True, inplace=True)
            
            # Limpiar selección antes de actualizar la tabla
            self.selected_group_rows.clear()
            
            # Actualizar tabla
            self.update_group_table()
            self.display_table()
            
            after_count = len(self.grouped_data)
            deleted = before_count - after_count
            
            ui.notify(f'Se eliminaron {deleted} fila(s).', type='positive')
       
        except Exception as ex:
            logger.exception(f"Error al eliminar filas: {ex}")
            ui.notify(f"Error al eliminar filas: {ex}", type='negative')


    def clear_group_table(self):
        try:
            count = len(self.grouped_data)
            self.grouped_data = pd.DataFrame()
            self.update_group_table()
            self.display_table()
            ui.notify(f'Tabla vaciada ({count} filas eliminadas).', type='info')
        except Exception as ex:
            logger.exception(f"Error al limpiar tabla: {ex}")
            ui.notify(f"Error al limpiar tabla: {ex}", type='negative')

    def update_group_table(self):
        if self.group_table is None:
            return

        if self.grouped_data is not None and not self.grouped_data.empty:
            cols = ["id", "register", "name", "description", "system_category",
                "read", "write", "sampling", "minvalue", "maxvalue", "unit", "view"]

            self.group_table.columns = [
                {'name': c, 'label': c.replace('_', ' ').title(), 'field': c, 'sortable': True}
                for c in cols
            ]
            self.group_table.rows = self.grouped_data.replace({np.nan: ''}).to_dict('records')
            self.group_table_card.visible = True
        else:
            self.group_table.rows = []
            self.group_table_card.visible = True
    
    def handle_main_pagination(self, e):
        """Manejo de paginación para la tabla principal."""
        try:
            
            if isinstance(e.value, dict):
                self.pagination_main.update(e.value)
            logger.debug(f"Paginación principal actualizada: {self.pagination_main}")
        except Exception as ex:
            logger.exception(f"Error al manejar paginación principal: {ex}")
            ui.notify(f"Error al manejar paginación principal: {ex}", type='negative')


    def handle_group_pagination(self, e):
        """Manejo de paginación para la tabla de grupos."""
        try:
            if isinstance(e.value, dict):
                self.pagination_group.update(e.value)
            logger.debug(f"Paginación de grupos actualizada: {self.pagination_group}")
        except Exception as ex:
            logger.exception(f"Error al manejar paginación de grupos: {ex}")
            ui.notify(f"Error al manejar paginación de grupos: {ex}", type='negative')
    
    def apply_search_filter(self, e):
        """Filtra las filas de la tabla principal según el texto ingresado y la columna seleccionada."""
        try:
            if self.processed_data is None or self.processed_data.empty:
                ui.notify('No hay datos cargados para filtrar.', type='warning')
                return

            column = self.search_column_selector.value
            query = (e.value or '').strip().lower()

            if not column or column not in self.processed_data.columns:
                ui.notify('Selecciona una columna válida para buscar.', type='warning')
                return

            if not query:
                # Si no hay búsqueda, mostrar todos los datos
                filtered = self.processed_data
            else:
                # Filtrar solo en la columna seleccionada
                filtered = self.processed_data[
                    self.processed_data[column].astype(str).str.lower().str.startswith(query, na=False)
                ]

            # Actualizar la tabla con los resultados filtrados
            self.table.rows = filtered.to_dict(orient='records')
            self.table.update()

            ui.notify(f"{len(filtered)} resultado(s) encontrados en '{column}'.", type='info', timeout=1.5)

        except Exception as ex:
            logger.exception(f"Error al aplicar filtro de búsqueda: {ex}")
            ui.notify(f"Error al aplicar filtro de búsqueda: {ex}", type='negative')
    
    def show_only_errors(self, e=None):
        """Filtra la tabla para mostrar solo filas con error_flag = 1."""
        if not self.table or not hasattr(self, "table"):
            return

        # Filtrar filas con error
        error_rows = [row for row in self.table.rows if row.get("error_flag", 0) == 1]

        # Si no hay errores, avisar
        if not error_rows:
            ui.notify("No hay filas con errores.", type="info")
            return

        # Mostrar solo esas filas
        self.table.rows = error_rows
        self.table.update()

        ui.notify(f"Mostrando {len(error_rows)} filas con errores.", type="warning")
    
    def apply_category_filter(self, e):
        """Filtra la tabla principal según las categorías seleccionadas."""
        try:
            if self.processed_data is None or self.processed_data.empty:
                ui.notify('No hay datos cargados para filtrar.', type='warning')
                return

            selected_categories = e.value or []

            # Si no hay selección, mostrar todos los datos
            if not selected_categories:
                filtered = self.processed_data
            else:
                filtered = self.processed_data[
                    self.processed_data['system_category'].isin(selected_categories)
                ]

            self.table.rows = filtered.replace({np.nan: ''}).to_dict('records')
            self.table.update()

            ui.notify(f"Mostrando {len(filtered)} filas filtradas por categoría.", type='info', timeout=1.5)

        except Exception as ex:
            logger.exception(f"Error al aplicar filtro por categoría: {ex}")
            ui.notify(f"Error al aplicar filtro por categoría: {ex}", type='negative')
    
    def apply_group_search_filter(self, e):
        """Filtra la tabla de grupos según el texto ingresado y la columna seleccionada."""
        try:
            if self.grouped_data is None or self.grouped_data.empty:
                ui.notify('No hay datos clasificados para filtrar.', type='warning')
                return

            column = self.group_search_column_selector.value
            query = (e.value or '').strip().lower()

            if not column or column not in self.grouped_data.columns:
                ui.notify('Selecciona una columna válida para buscar.', type='warning')
                return

            if not query:
                filtered = self.grouped_data
            else:
                filtered = self.grouped_data[
                    self.grouped_data[column].astype(str).str.lower().str.startswith(query, na=False)
                ]

            self.group_table.rows = filtered.replace({np.nan: ''}).to_dict('records')
            self.group_table.update()

            ui.notify(f"{len(filtered)} resultado(s) encontrados en '{column}'.", type='info', timeout=1.5)

        except Exception as ex:
            logger.exception(f"Error al aplicar filtro de búsqueda en tabla de grupos: {ex}")
            ui.notify(f"Error al aplicar filtro de búsqueda: {ex}", type='negative')

    def apply_group_category_filter(self, e):
        """Filtra la tabla de grupos según las categorías seleccionadas."""
        try:
            if self.grouped_data is None or self.grouped_data.empty:
                ui.notify('No hay datos clasificados para filtrar.', type='warning')
                return

            selected_categories = e.value or []

            if not selected_categories:
                filtered = self.grouped_data
            else:
                filtered = self.grouped_data[
                    self.grouped_data['system_category'].isin(selected_categories)
                ]

            self.group_table.rows = filtered.replace({np.nan: ''}).to_dict('records')
            self.group_table.update()

            ui.notify(f"Mostrando {len(filtered)} filas filtradas por categoría.", type='info', timeout=1.5)

        except Exception as ex:
            logger.exception(f"Error al aplicar filtro por categoría en tabla de grupos: {ex}")
            ui.notify(f"Error al aplicar filtro por categoría: {ex}", type='negative')

    def handle_estado_change(self, e):
        """Maneja el evento cuando cambia el estado (categoría del sistema)."""
        try:
            args = getattr(e, 'args', e)
            row = args if isinstance(args, dict) else args[0] if isinstance(args, (list, tuple)) and len(args) > 0 else None
            if not row or 'id' not in row:
                logger.debug('Evento estado-change sin payload válido')
                return

            row_id = str(row.get('id'))
            new_group = row.get('system_category')

            if self.processed_data is None:
                logger.debug('No hay datos procesados al cambiar estado')
                return

            # === Actualizar categoría ===
            self.processed_data.loc[self.processed_data['id'].astype(str) == row_id, 'system_category'] = new_group

            # === Detectar backend activo ===
            backend = getattr(self, "backend_selected", "ipro").lower()

            # === Asignar permisos según backend ===
            read_val, write_val = 0, 0

            if backend == "ipro":
                permission_map = {
                    'ALARM': (1, 0),
                    'STATUS': (3, 0),
                    'SET_POINT': (3, 16),
                    'CONFIG_PARAMETER': (3, 16),
                    'COMMAND': (3, 16),
                    'ANALOG_INPUT': (3, 0),
                    'ANALOG_OUTPUT': (3, 0),
                    'DIGITAL_INPUT': (1, 0),
                    'DIGITAL_OUTPUT': (3, 16),
                    'SYSTEM': (3, 0)
                    }
                read_val, write_val = permission_map.get(new_group, (0, 0))

            elif backend == "cefa":
                # Valores típicos de permisos CEFA (ajústalos según la lógica real)
                permission_map = {
                    'ALARM': (1, 0),
                    'STATUS': (3, 0),
                    'SET_POINT': (3, 6),
                    'CONFIG_PARAMETER': (1, 6),
                    'COMMAND': (1, 5),
                    'ANALOG_INPUT': (3, 0),
                    'ANALOG_OUTPUT': (3, 0),
                    'DIGITAL_INPUT': (1, 0),
                    'DIGITAL_OUTPUT': (1, 5),
                    'SYSTEM': (3, 0)
                    }
                read_val, write_val = permission_map.get(new_group, (0, 0))

            elif backend == "keyter":
                    permission_map = {
                        'ALARM': (1, 0),
                        'STATUS': (3, 0),
                        'SET_POINT': (3, 6),
                        'CONFIG_PARAMETER': (1, 5),
                        'COMMAND': (1, 5),
                        'ANALOG_INPUT': (3, 0),
                        'ANALOG_OUTPUT': (3, 0),
                        'DIGITAL_INPUT': (1, 0),
                        'DIGITAL_OUTPUT': (1, 5),
                        'SYSTEM': (3, 0)
                    }
                    read_val, write_val = permission_map.get(new_group, (0, 0))
            else:  # Excel o genérico
                    permission_map = {
                    'ALARM': (1, 0),
                    'STATUS': (3, 0),
                    'SET_POINT': (3, 6),
                    'CONFIG_PARAMETER': (1, 7),
                    'COMMAND': (1, 5),
                    'ANALOG_INPUT': (3, 0),
                    'ANALOG_OUTPUT': (3, 0),
                    'DIGITAL_INPUT': (1, 0),
                    'DIGITAL_OUTPUT': (1, 5),
                    'SYSTEM': (3, 0)
                    }
                    read_val, write_val = permission_map.get(new_group, (0, 0))

            # === Aplicar permisos ===
            self.processed_data.loc[self.processed_data['id'].astype(str) == row_id, ['read', 'write']] = (read_val, write_val)

            # === Ajustes visuales ===
            if new_group == 'STATUS':
                self.processed_data.loc[self.processed_data['id'].astype(str) == row_id, 'view'] = 'basic'
            elif new_group == 'ALARM':
                self.processed_data.loc[self.processed_data['id'].astype(str) == row_id, 'view'] = 'simple'

                # === Asignar valor de sampling ===
            mapping = {
                "ALARM": 30,
                "SET_POINT": 300,
                "ANALOG_INPUT": 60,
                "ANALOG_OUTPUT":60,
                "DIGITAL_INPUT":60,
                "DEFAULT": 0,
                "COMMAND": 0,
                "STATUS": 60,
                "SYSTEM": 0,
                "CONFIG_PARAMETER": 0
            }

            sampling_val = mapping.get(new_group, mapping["DEFAULT"])

            # === Aplicar valor de sampling ===
            self.processed_data.loc[self.processed_data['id'].astype(str) == row_id, 'sampling'] = sampling_val
            

            # === Actualizar grouped_data ===
            selected_row_df = self.processed_data.loc[self.processed_data['id'].astype(str) == row_id].copy()
            selected_row_df = selected_row_df.reindex(columns=self.grouped_data.columns, fill_value=np.nan)
            self.grouped_data = self.grouped_data[~self.grouped_data['id'].astype(str).isin([row_id])]
            self.grouped_data = pd.concat([selected_row_df, self.grouped_data], ignore_index=True)

            # === Actualizar interfaz ===
            self.update_group_table()
            self.display_table()
            ui.notify(f'Fila {row_id} clasificada como {new_group} ({backend.upper()}).', type='positive')

        except Exception as e:
            logger.error(f"Error en handle_estado_change: {e}", exc_info=True)



    
    def handle_view_change(self, e):
        """Maneja el evento emitido desde el slot 'estado' cuando se cambia el dropdown.
        El payload esperado contiene la fila completa (props.row)."""
        try:
            args = getattr(e, 'args', e)
            row = None
            if isinstance(args, dict):
                row = args
            elif isinstance(args, (list, tuple)) and len(args) > 0 and isinstance(args[0], dict):
                row = args[0]

            if not row or 'id' not in row:
                logger.debug('Evento view-change sin payload válido')
                return

            row_id = str(row.get('id'))
            new_view = row.get('view')

            if self.processed_data is None:
                return

            # ✅ Si se selecciona "primary", removerlo de otras filas.
            if new_view == 'primary':
                # Encontrar cualquier fila que tenga "primary" excepto la actual
                mask_primary = (
                    (self.processed_data['view'] == 'primary') &
                    (self.processed_data['id'].astype(str) != row_id)
                )

                # Cambiar esas vistas a "simple"
                self.processed_data.loc[mask_primary, 'view'] = 'simple'

            # ✅ Ahora aplicar el nuevo valor a la fila actual
            self.processed_data.loc[self.processed_data['id'].astype(str) == row_id, 'view'] = new_view

            # Reconstruir dataframe de la fila actualizada
            selected_row_df = self.processed_data.loc[self.processed_data['id'].astype(str) == row_id].copy()

            if selected_row_df.empty:
                return

           # ✅ Sincronizar grouped_data con los cambios en processed_data (especialmente para el caso "primary")
            if self.grouped_data is not None and not self.grouped_data.empty:
                # Actualizamos todas las vistas desde processed_data
                self.grouped_data['view'] = self.grouped_data['id'].astype(str).map(
                    dict(zip(self.processed_data['id'].astype(str), self.processed_data['view']))
                )

            # ✅ Agregar o reemplazar solo la fila actualizada
            if self.grouped_data is None or self.grouped_data.empty:
                self.grouped_data = selected_row_df
            else:
                all_cols = list(self.grouped_data.columns)
                selected_row_df = selected_row_df.reindex(columns=all_cols, fill_value=np.nan)

                self.grouped_data['id'] = self.grouped_data['id'].astype(str)
                selected_row_df['id'] = selected_row_df['id'].astype(str)

                self.grouped_data = self.grouped_data[~self.grouped_data['id'].isin(selected_row_df['id'])]
                self.grouped_data = pd.concat([selected_row_df, self.grouped_data], ignore_index=True)


            # ✅ Refrescar tablas
            self.update_group_table()
            self.display_table()

            ui.notify(f'Fila {row_id} ahora tiene vista "{new_view}".', type='positive')

        except Exception as ex:
            logger.exception(f"Error manejando cambio de vista: {ex}")
            ui.notify(f"Error manejando cambio de vista: {ex}", type='negative')

    def reset_search_input(self, e):
        """Limpia el cuadro de búsqueda y restaura la tabla principal al cambiar de columna."""
        logger.info("🧩 Ejecutando reset_search_search_input...")
        if self.search_input:
            self.search_input.value = ''
        if self.processed_data is not None and not self.processed_data.empty:
            self.table.rows = self.processed_data.to_dict('records')
            self.table.update()
        

    def reset_group_search_input(self, e):
        """Limpia el cuadro de búsqueda y restaura la tabla de grupos al cambiar de columna."""
        logger.info("🧩 Ejecutando reset_group_search_input...")
        if self.group_search_input:
            self.group_search_input.value = ''
        if self.grouped_data is not None and not self.grouped_data.empty:
            self.group_table.rows = self.grouped_data.to_dict('records')
            self.group_table.update()
    
    def handle_field_change(self, e, field_name: str, label: str = None):
        """Manejador genérico para cambios en un campo editable de la tabla."""
        try:
            logger.info(f"🟢 [handle_field_change:{field_name}] Evento recibido.")
            logger.info(f"Contenido bruto del evento: {repr(e)}")
            

            # --- Extraer fila del evento ---
            args = getattr(e, 'args', e)
            if isinstance(args, dict):
                row = args
            elif isinstance(args, (list, tuple)) and args and isinstance(args[0], dict):
                row = args[0]
            else:
                ui.notify('Evento sin datos válidos', type='warning')
                return

            row_id = str(row.get('id'))
            self.update_error_counter()

            try:
                raw_value = row.get(field_name, '')
                new_value = raw_value.strip() if isinstance(raw_value, str) else raw_value
                self.update_error_counter()
            except Exception:
                ui.notify("No hay cambios para realizar")
                return

            logger.info(f"🧾 Actualizando {label} (ID={row_id}) -> '{new_value}'")

            # --- Actualizar processed_data ---
            if self.processed_data is not None and not self.processed_data.empty:
                mask = self.processed_data['id'].astype(str) == row_id
                self.update_error_counter()
                if mask.any():
                    self.processed_data.loc[mask, field_name] = new_value
                    logger.info(f"✅ processed_data.{field_name} actualizado")

            # --- Actualizar grouped_data ---
            if self.grouped_data is not None and not self.grouped_data.empty:
                mask = self.grouped_data['id'].astype(str) == row_id
                self.update_error_counter()
                if mask.any():
                    self.grouped_data.loc[mask, field_name] = new_value
                    logger.info(f"✅ grouped_data.{field_name} actualizado")

            # --- Actualizar visualmente la tabla ---
            if self.table and self.table.rows:
                self.update_error_counter()
                for r in self.table.rows:
                    if str(r.get('id')) == row_id:
                        r[field_name] = new_value
                        break
                self.update_group_table()
                self.update_error_counter()
                self.display_table()

            ui.notify(f"{label} actualizado (ID={row_id})", type='positive', timeout=1.5)

        except Exception as ex:
            import traceback
            logger.error(f"❌ Error en handle_field_change({field_name}):\n" + traceback.format_exc())
            ui.notify(f"Error actualizando {label or field_name}: {ex}", type='negative')

    def add_new_row(self):
        """Agrega una nueva fila al inicio de la tabla, la muestra inmediatamente y la clasifica si aplica."""
        try:
            import pandas as pd

            # Crear DataFrame vacío si no existe
            if self.processed_data is None or self.processed_data.empty:
                self.processed_data = pd.DataFrame(columns=[
                    'id', 'register', 'name', 'description', 'read', 'write', 'sampling',
                    'minvalue', 'maxvalue', 'unit', 'view', 'system_category',
                ])

            # Generar un nuevo ID único
            existing_ids = self.processed_data['id'].astype(str).tolist()
            next_id = max([int(x) for x in existing_ids if x.isdigit()] + [0]) + 1

            # Crear nueva fila con valores por defecto
            new_row = {
                'id': next_id,
                'register': 0,
                'name': f'Nuevo Parámetro {next_id}',
                'description': 'Descripción...',
                'read': 0,
                'write': 0,
                'sampling': 0,
                'minvalue': 0,
                'maxvalue': 0,
                'unit': '',
                'view': 'basic',
                'system_category': self.group_selector.value or 'DEFAULT',
            }

            # --- Insertar la fila al inicio del DataFrame principal ---
            new_df = pd.DataFrame([new_row])
            self.processed_data = pd.concat([new_df, self.processed_data], ignore_index=True)

            # --- Insertar también en la tabla visual (al inicio) ---
            current_rows = self.table.rows or []
            updated_rows = [new_row] + current_rows
            self.table.rows = updated_rows

            # --- Mostrar la primera página para asegurar visibilidad inmediata ---
            self.pagination_main['page'] = 1
            self.table.update()

            ui.notify(f"✅ Fila '{new_row['name']}' agregada en la parte superior.", color='positive', position='top')

            # --- Si pertenece a un grupo válido, agregarla también a la tabla de grupos ---
            valid_groups = [
                'ALARM', 'SET_POINT', 'CONFIG_PARAMETER', 'COMMAND',
                'ANALOG_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT',
                'STATUS', 'SYSTEM'
            ]

            if new_row['system_category'] in valid_groups:
                if self.grouped_data is None or self.grouped_data.empty:
                    self.grouped_data = new_df
                else:
                    all_cols = list(self.grouped_data.columns)
                    new_df = new_df.reindex(columns=all_cols, fill_value=np.nan)
                    self.grouped_data = pd.concat([new_df, self.grouped_data], ignore_index=True)

                self.update_group_table()
                ui.notify(f"🟩 Fila '{new_row['name']}' clasificada automáticamente en {new_row['system_category']}.", color='positive')
            else:
                ui.notify(f"ℹ️ Fila agregada sin grupo asignado (categoría: {new_row['system_category']}).", color='info')

            # --- Refrescar tabla principal y de grupos ---
            self.display_table()
            self.update_group_table()

        except Exception as ex:
            import traceback
            logger.error(f"❌ Error al agregar nueva fila:\n" + traceback.format_exc())
            ui.notify(f"Error al agregar nueva fila: {ex}", type='negative')

    def download_variable_map(self):
        """Genera y descarga un Excel con el mapa de variables (columnas seleccionables por el usuario)."""
        try:
            # Determinar fuente de datos
            df_source = None
            if self.grouped_data is not None and not self.grouped_data.empty:
                df_source = self.grouped_data
            elif self.processed_data is not None and not self.processed_data.empty:
                df_source = self.processed_data
            else:
                ui.notify("⚠️ No hay datos para generar el mapa de variables.", type='warning')
                return

            # Columnas disponibles
            available_cols = list(df_source.columns)

            # Selector de columnas
            selected_columns = ui.select(
                options=available_cols,
                value=[
                ],  
                multiple=True,
                label="Selecciona las columnas a exportar",
                with_input=True,
                clearable=True
            ).props('outlined dense options-dense behavior="menu"').classes('w-64 bg-white')

            async def confirmar_exportacion():
                cols = selected_columns.value
                if not cols:
                    ui.notify("⚠️ Debes seleccionar al menos una columna para exportar.", type='warning')
                    return

                missing = [c for c in cols if c not in df_source.columns]
                if missing:
                    ui.notify(f"⚠️ Columnas no encontradas en los datos: {', '.join(missing)}", type='warning')
                    return

                df_export = df_source[cols].copy().replace({None: '', pd.NA: ''})

                # Crear archivo temporal Excel
                with NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                    with pd.ExcelWriter(tmp.name, engine="openpyxl") as writer:
                        df_export.to_excel(writer, sheet_name="Mapa de Variables", index=False)
                    tmp.flush()
                    file_path = tmp.name

                ui.download(file_path, filename="mapa_de_variables.xlsx")
                ui.notify(f"📗 Descarga iniciada con {len(cols)} columnas seleccionadas.", type='info')

                # Limpieza del archivo temporal
                async def cleanup_file(path):
                    await asyncio.sleep(60)
                    if os.path.exists(path):
                        os.remove(path)

                ui.timer(1.0, lambda: asyncio.create_task(cleanup_file(file_path)), once=True)

            ui.button("Descargar Excel", on_click=confirmar_exportacion, color="green").props('unelevated color=positive icon=download size=md').classes('px-6 shadow-md')

        except Exception as ex:
            import traceback
            logger.error(f"❌ Error al generar mapa de variables:\n{traceback.format_exc()}")
            ui.notify(f"Error al generar mapa de variables: {ex}", type='negative')
