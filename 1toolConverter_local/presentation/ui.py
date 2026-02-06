from io import BytesIO
from typing import Optional
import pandas as pd
import numpy as np
from nicegui import ui
import logging
from tempfile import NamedTemporaryFile
import re
import os
import asyncio


from presentation.components.header import create_header
from presentation.mixins.process_mixin import ProcessMixin
from presentation.mixins.handle_mixin import HandleMixin  
from presentation.mixins.update_mixin import UpdateMixin     
from presentation.mixins.filters_mixin import FilterMixin
from presentation.mixins.functions_mixin import FunctionMixin
from presentation.mixins.table_mixin import TableMixin
from presentation.mixins.openAIMixin import OpenAIMixin 

logger = logging.getLogger(__name__)



# 2. Heredamos de todos ellos
class HTMLConverterUI(ProcessMixin, HandleMixin, UpdateMixin, FilterMixin, FunctionMixin, TableMixin, OpenAIMixin):
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
        self.error_label = None   
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

        # Marcar errores automáticamente al cargar
        rows = self.processed_data.replace({np.nan: ''}).to_dict('records')
        self.table.rows = rows
        self.table.update()
        
        # Actualizamos contadores visuales
        if hasattr(self, 'update_error_counter'):
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
        create_header()

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

   

    def _recreate_upload_component(self):
        """Recrea el componente de subida para limpiar archivos cargados y mantener el estilo."""
        if hasattr(self, "upload_container"):
            self.upload_container.clear()  # Limpia el contenedor anterior

        with self.upload_container:
            # Configuración base del componente
            max_files = 1
            accept_types = ""

            # Configurar según backend seleccionado
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

            # Crear componente de subida
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

            #  Deshabilitar si el backend no tiene formatos válidos
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

    def _create_table_section(self):
        with ui.card().classes('w-full p-0 rounded-xl shadow-md border border-slate-200 overflow-hidden bg-white') as table_card:
            # Header de la tarjeta
            with ui.row().classes('p-4 bg-slate-50 border-b border-slate-200 items-center justify-between'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('table_chart', size='sm').classes('text-slate-600')
                    ui.label("3. Parámetros Detectados").classes('text-lg font-semibold text-slate-800')
                
                # Botón de errores destacado
                self.error_button = ui.button("Errores: 0", on_click=self.toggle_error_filter).props("icon=warning color=negative outline rounded")
                ui.button('Guardar Cambios', on_click=self.save_all_changes).props('outline color=positive icon=save rounded')
                ui.button('IA: Corregir Errores o Rellenar', on_click=self.ai_fix_errors, icon='auto_fix_high').props('outline color=purple rounded').tooltip('Usa GPT para corregir formato y longitud automáticamente')
                #ui.button('IA: Rellenar Vacíos', on_click=self.ai_fill_empty, icon='settings').props('outline color=teal rounded').tooltip('Genera descripciones para celdas vacías basándose en otras columnas')

            self.table_card = table_card
            self.table_card.visible = False

            # Filtros en barra gris claro
            with ui.row().classes('w-full p-4 gap-4 items-start flex-wrap bg-white'):
                # 1. Selector de Columna 
                self.search_column_selector = ui.select(
                    options=['register', 'name', 'description', 'system_category', 'unit', 'view', 'error_flag', 'id'], 
                    value='name', 
                    label='Buscar columna',
                    on_change=self.reset_search_input
                ).props('outlined dense options-dense').classes('w-48')

                # 2. Input de Búsqueda (Flexible)
                self.search_input = ui.input(
                    placeholder='Escribe para buscar...', 
                    on_change=self.apply_search_filter
                ).props('outlined dense clearable').classes('flex-grow min-w-[200px]')

                # 3. Filtro por Grupo (Flexible y ajustado)
                self.category_filter = ui.select(
                    options=['ALARM', 'SET_POINT', 'CONFIG_PARAMETER', 'COMMAND', 'ANALOG_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT', 'DEFAULT', 'STATUS', 'SYSTEM', 'COUNTERS'],
                    multiple=True, 
                    label='Filtrar por grupo', 
                    clearable=True, 
                    on_change=self.apply_category_filter
                ).props('outlined dense use-chips clearable').classes('flex-grow min-w-[300px] max-w-md')
            # Tabla
            cols = ["id", "register", "name", "description", "read", "write", "sampling", "minvalue", "maxvalue", "unit", "view", "error_flag"]
            
            self.table = ui.table(
                columns=[{'name': c, 'label': c.replace('_', ' ').title(), 'field': c, 'sortable': True} for c in cols],
                rows=[],
                row_key='id',
                selection='multiple',
                pagination=self.pagination_main,
                on_pagination_change=self.handle_main_pagination,
            ).classes('w-full').props('flat dense') 

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
            with ui.row().classes('w-full p-4 border-t gap-4 items-center justify-between'):

                # --- IZQUIERDA: Acciones sobre la Selección ---
                with ui.row().classes('items-center gap-3'):
                    self.group_selector = ui.select(
                        options=['ALARM', 'SET_POINT', 'CONFIG_PARAMETER', 'COMMAND', 'ANALOG_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT', 'STATUS', 'SYSTEM'],
                        label='Asignar Grupo a Selección'
                    ).props('outlined dense options-dense behavior="menu"').classes('w-64')
                    
                    self.assign_button = ui.button('Asignar', on_click=self.assign_group_to_selection).props('unelevated color=primary icon=low_priority')
                    
                    

                # --- DERECHA: Acciones Globales (Agregar, Mapa, Limpiar Todo) ---
                with ui.row().classes('items-center gap-3'):

                    # He movido "Limpiar Todo" aquí porque es una acción global, no de selección
                    self.clear_table_button = ui.button('Limpiar Todo', on_click=self.clear_main_table).props('outline color=warning icon=delete_forever')
                    
                    self.delete_rows_button = ui.button('Eliminar Selección', on_click=self.deleted_selected_rows).props('outline color=negative icon=delete')
                    #ui.button('Descargar Errores', on_click=self.download_errors_excel).props('outline color=negative icon=bug_report')
                    ui.button('Agregar Fila Manual', on_click=self.add_new_row).props('outline color=secondary icon=add')
                    ui.button('Generar Mapa', on_click=self.download_variable_map).props('outline color=info icon=map')
                    
                    
        self.table.on('click', lambda e: logger.info("Evento click detectado en tabla"))

    
    def _create_group_table_section(self):
        with ui.card().classes('w-full p-0 rounded-xl shadow-md border border-slate-200 overflow-hidden bg-white mt-6') as group_card:
            # Header
            with ui.row().classes('p-4 bg-slate-50 border-b border-slate-200 items-center gap-2'):
                ui.icon('category', size='sm').classes('text-slate-600')
                ui.label("4. Clasificación Final").classes('text-lg font-semibold text-slate-800')

            self.group_table_card = group_card
            self.group_table_card.visible = False

            # Filtros
            with ui.row().classes('w-full p-4 gap-4 items-start flex-wrap bg-white'):

                self.group_search_column_selector = ui.select(
                    options=['register', 'name', 'description', 'system_category', 'unit', 'view', 'error_flag', 'id'], 
                    value='name', 
                    label='Buscar columna',
                    on_change=self.reset_group_search_input
                ).props('outlined dense options-dense').classes('w-48')

                self.group_search_input = ui.input(
                    placeholder='Buscar...', 
                    on_change=self.apply_group_search_filter).props('outlined dense clearable').classes('flex-grow min-w-[200px]')
                
                self.group_category_filter = ui.select(
                    options=['ALARM', 'SET_POINT', 'CONFIG_PARAMETER', 'COMMAND', 'ANALOG_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT', 'DEFAULT', 'STATUS', 'SYSTEM'],
                    multiple=True, label='Filtrar por grupos', clearable=True, on_change=self.apply_group_category_filter
                ).props('outlined dense use-chips clearable').classes('flex-grow min-w-[300px] max-w-md')

            self.group_table = ui.table(
                columns=[], rows=[], row_key='id', selection='multiple',
                pagination=self.pagination_group, on_pagination_change=self.handle_group_pagination,
            ).classes('w-full').props('flat dense')
            self.group_table.on('selection', self.handle_group_selection)

            # Footer con acciones
            with ui.row().classes('p-4 bg-slate-50 border-t border-slate-200 justify-between items-center'):
                with ui.row().classes('gap-2'):
                    self.delete_rows_button = ui.button('Eliminar Selección', on_click=self.deleted_selected_rows).props('outline color=negative icon=delete')
                    self.clear_table_button = ui.button('Limpiar Todo', on_click=self.clear_group_table).props('outline color=warning icon=delete_forever')
                
                self.download_button = ui.button('Descargar Excel Final', on_click=self.download_excel).props('unelevated color=positive icon=download size=md').classes('px-6 shadow-md')
                self.download_button.disable()

            self.group_table_card = group_card
            self.group_table_card.visible = False

   

    
    
    
    
    

    

    
    
   
  