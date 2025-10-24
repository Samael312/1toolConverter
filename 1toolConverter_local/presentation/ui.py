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

        self.pagination_main = {'rowsPerPage': 10, 'page': 1, 'sortBy': 'id', 'descending': False}
        self.pagination_group = {'rowsPerPage': 10, 'page': 1, 'sortBy': 'id', 'descending': False}


        # Estado
        self.uploaded_file_content: Optional[bytes] = None
        self.processed_data: Optional[pd.DataFrame] = None
        self.grouped_data: Optional[pd.DataFrame] = pd.DataFrame()
        self.backend_selected: Optional[str] = None  

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
        try:
            logger.info(f"Iniciando carga de archivo: {e.file.name}")
            self.uploaded_file_content = await e.file.read()
            logger.info(f"Archivo leído correctamente: {len(self.uploaded_file_content)} bytes")

            if self.process_button:
                self.process_button.enable()
            if self.download_button:
                self.download_button.disable()
            if self.table_card:
                self.table_card.visible = False
            if self.group_table_card:
                self.group_table_card.visible = False

            ui.notify(f"Archivo '{e.file.name}' cargado correctamente.", type='positive')

        except Exception as ex:
            logger.error(f"Error al cargar archivo: {ex}", exc_info=True)
            ui.notify(f"Error al cargar archivo: {ex}", type='negative')

    def process_file(self):
        if self.uploaded_file_content is None:
            ui.notify("No hay archivo para procesar.", type='negative')
            return

        # --- 🔄 Reiniciar tablas y datos previos ---
        self.processed_data = None
        self.grouped_data = pd.DataFrame()
        self.selected_rows = []
        self.selected_group_rows = []
        
        # Limpiar contenido visual de tablas
        if self.table:
            self.table.rows = []
            self.table.update()
        if self.group_table:
            self.group_table.rows = []
            self.group_table.update()

        # Ocultar las tarjetas mientras no haya datos
        if self.table_card:
            self.table_card.visible = False
        if self.group_table_card:
            self.group_table_card.visible = False

        # Deshabilitar botones dependientes
        if self.download_button:
            self.download_button.disable()

        # --- Procesar archivo normalmente ---
        df = self.process_html_callback(self.uploaded_file_content)

        if df is not None and not df.empty:
            self.processed_data = df

            # --- Detectar filas ya clasificadas ---
            valid_groups1 = [
                'ALARM', 'SET_POINT', 'CONFIG_PARAMETER', 'COMMAND',
                'ANALOG_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT', 'STATUS'
            ]

            valid_groups2 = [
                'basic', 'primary'
            ]

            auto_grouped1 = df[df['system_category'].isin(valid_groups1)]
            auto_grouped2 = df[df['view'].isin(valid_groups2)]

            # Combinar ambos sin duplicados
            combined_grouped = pd.concat([auto_grouped1, auto_grouped2]).drop_duplicates()

            if not combined_grouped.empty:
                self.grouped_data = combined_grouped.reset_index(drop=True)
                ui.notify(
                    f"{len(combined_grouped)} variables clasificadas detectadas automáticamente.",
                    type='positive',
                    timeout=2.5
                )
                
            if self.download_button:
                self.download_button.enable()

            ui.notify(f"{len(df)} parámetros procesados.", type='positive')
            self.display_table()  
            self.update_group_table()  

        else:
            self.processed_data = None
            ui.notify("No se obtuvieron datos del procesamiento.", type='warning')

            if self.download_button:
                self.download_button.disable()


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
                "read", "write", "sampling", "minvalue", "maxvalue", "unit", "view"]

        rows = df_display.replace({np.nan: ''}).to_dict('records')

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
        ui.dark_mode().set_value(False)
        ui.add_head_html("""
        <style>
        .q-table td, .q-table th {
            white-space: normal !important;
            word-wrap: break-word !important;
            line-height: 1.3em;
            vertical-align: top;
            padding: 6px 8px !important;
        }
        .q-table__container {
            max-height: 600px;
        }
        </style>
        """)

        with ui.header().classes('items-center justify-between'):
            ui.label('Conversor HTML / Excel a Parámetros').classes('text-xl font-bold')

        with ui.column().classes('w-full p-4 md:p-8 items-center gap-8'):
            # 🆕 NUEVO: Selector de backend al inicio
            with ui.card().classes('w-full max-w-2xl'):
                ui.label('0. Seleccionar Backend').classes('text-lg font-bold')
                ui.separator()
                self.backend_selector = ui.select(
                    options=['Keyter', 'iPro'],
                    label='Selecciona el backend',
                    on_change=self.handle_backend_selection
                ).props('outlined dense clearable').classes('w-64')

            self._create_upload_section()
            self._create_process_section()
            self._create_table_section()
            self._create_group_table_section()

            # 🆕 Desactivar todo hasta elegir backend
            if self.process_button:
                self.process_button.disable()
            if self.upload_component:
                self.upload_component.disable()
            if self.table_card:
                self.table_card.visible = False
            if self.group_table_card:
                self.group_table_card.visible = False

    def handle_backend_selection(self, e):
        """🆕 Activa o desactiva la UI según el backend seleccionado."""
        backend = e.value
        self.backend_selected = backend

        # 🔹 Reiniciar interfaz al cambiar de backend
        self._reset_ui_state()

        if not backend:
            ui.notify("Selecciona un backend para continuar.", type='warning')
            if self.upload_component:
                self.upload_component.disable()
            if self.process_button:
                self.process_button.disable()
            return

        # Configurar tipo de archivo permitido
        if backend == 'Keyter':
            file_accept = '.html'
        elif backend == 'iPro':
            file_accept = '.xlsx'
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
        self.uploaded_file_content = None

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

            self.upload_component = ui.upload(
                label="Seleccionar o arrastrar archivo aquí",
                auto_upload=True,
                max_files=1,
            ).props('flat bordered square no-wrap').classes(
                'w-96 h-32 justify-left items-left text-center bg-gray-50 hover:bg-gray-100 rounded-2xl border border-gray-300'
            )

            self.upload_component.on_upload(self.handle_upload)

            if self.backend_selected == "Keyter":
                self.upload_component.props('accept=".html"')
            elif self.backend_selected == "iPro":
                self.upload_component.props('accept=".xlsx"')
            else:
                self.upload_component.disable()



    def _create_upload_section(self):
        with ui.card().classes('w-full max-w-2xl mx-auto p-4'):
            ui.label('1. Cargar Archivo').classes('text-lg font-bold mb-2')
            ui.separator()

            # 🔹 Contenedor dinámico del upload
            self.upload_container = ui.column().classes('w-full items-left justify-left')
            self._recreate_upload_component()



    def _create_process_section(self):
        with ui.card().classes('w-full max-w-2xl'):
            ui.label('2. Procesar el Archivo y Mostrar Tabla').classes('text-lg font-bold')
            with ui.row():
                self.process_button = ui.button(
                    'Procesar Archivo',
                    on_click=self.process_file,
                    icon='play_for_work'
                )
                self.process_button.disable()


    def _create_table_section(self):
        with ui.card().classes('w-full max-w-6xl') as table_card:
            ui.label("3. Tabla de Parámetros").classes('text-lg font-bold')
            ui.separator()

            self.table_card = table_card
            self.table_card.visible = False

            cols = ["id", "register", "name", "description", "system_category",
                    "read", "write", "sampling", "minvalue", "maxvalue", "unit", "view" ]

            # Selector de columna + campo de búsqueda
            with ui.row().classes('mt-2 mb-2 items-center gap-2'):
                ui.label('Buscar en:').classes('text-sm')

                self.search_column_selector = ui.select(
                    options=['register', 'name', 'description', 'system_category'],
                    value='name',
                    label='Columna',
                    on_change= self.reset_search_input
                ).props('dense outlined').classes('w-48')

                self.search_input = ui.input(
                    placeholder='Buscador...',
                    on_change=self.apply_search_filter
                ).props('dense clearable outlined').classes('flex-1')

            # --- Filtro por system_category ---
            with ui.row().classes('mt-2 mb-2 items-center gap-2'):
                ui.label('Filtrar por grupo:').classes('text-sm')

                self.category_filter = ui.select(
                    options=[
                        'ALARM', 'SET_POINT', 'CONFIG_PARAMETER', 'COMMAND',
                        'ANALOG_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT', 'DEFAULT', 'STATUS'
                    ],
                    multiple=True,
                    label='Selecciona grupos',
                    clearable=True,
                    on_change=self.apply_category_filter
                ).props('dense outlined use-chips clearable').classes('w-96')

            # Tabla con paginación
            self.table = ui.table(
                columns=[{'name': c, 'label': c.replace('_', ' ').title(), 'field': c, 'sortable': True} for c in cols],
                rows=[],
                row_key='id',
                selection='multiple',
                pagination=self.pagination_main,
                on_pagination_change=self.handle_main_pagination,
            ).classes('w-full h-96').props('flat bordered dense')

            self.table.on('selection', self.handle_selection)

            # --- Selector desplegable (drop-down) en la columna "estado" ---
            # Usamos un slot de la tabla para renderizar un QSelect por fila.
            # Al actualizar el valor emitimos un evento 'estado-change' que manejamos en Python
            self.table.add_slot('body-cell-estado', '''
    <q-td key="estado" :props="props">
        <q-select
            v-model="props.row.system_category"
            :options="[
                'ALARM', 'SET_POINT', 'CONFIG_PARAMETER', 'COMMAND',
                'ANALOG_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT', 'STATUS'
            ]"
            dense filled outlined emit-value map-options
            @update:model-value="$parent.$emit('estado-change', props.row)"
            popup-content-class="bg-white text-black"
        >
            <template v-slot:selected-item="scope">
                <div style="display:flex; align-items:center; gap:6px;">
                    <div :style="{
                        width: '20px',
                        height: '20px',
                        borderRadius: '50%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'white',
                        fontSize: '12px',
                        backgroundColor: ({
                            'ALARM': 'red',
                            'SET_POINT': '#0E57E8',
                            'CONFIG_PARAMETER': '#1CCDD6',
                            'COMMAND': 'purple',
                            'ANALOG_INPUT': '#00E343',
                            'ANALOG_OUTPUT': '#13662C',
                            'DIGITAL_INPUT': 'blue',
                            'DIGITAL_OUTPUT': 'black',
                            'STATUS': '#B8B302'
                        }[props.row.system_category] || 'grey')
                    }">
                        {{ props.row.system_category.charAt(0) }}
                    </div>
                    <span>{{ props.row.system_category }}</span>
                </div>
            </template>
        </q-select>
    </q-td>
''')

            # Registrar el manejador del evento emitido desde el slot
            self.table.on('estado-change', self.handle_estado_change)

            self.table.add_slot('body-cell-view', '''
    <q-td key="estado" :props="props">
        <q-select
            v-model="props.row.view"
            :options="[
                'basic', 'simple', 'primary'
            ]"
            dense filled outlined emit-value map-options
            @update:model-value="$parent.$emit('view-change', props.row)"
            popup-content-class="bg-white text-black"
        >
            <template v-slot:selected-item="scope">
                <div style="display:flex; align-items:center; gap:6px;">
                    <div :style="{
                        width: '20px',
                        height: '20px',
                        borderRadius: '50%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'white',
                        fontSize: '12px',
                        backgroundColor: ({
                            'basic': 'black',
                            'primary': 'blue',
                                 'simple':  'teal'
                        }[props.row.view] || 'grey')
                    }">
                        {{ props.row.view.charAt(0) }}
                    </div>
                    <span>{{ props.row.view }}</span>
                </div>
            </template>
        </q-select>
    </q-td>
''')
            # Registrar el manejador del evento emitido desde el slot
            self.table.on('view-change', self.handle_view_change)

            # --- Controles debajo de la tabla ---
            with ui.row().classes('mt-4 items-center gap-4'):
                self.group_selector = ui.select(
                    options=[
                        'ALARM', 'SET_POINT', 'CONFIG_PARAMETER', 'COMMAND',
                        'ANALOG_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT', 'STATUS'
                    ],
                    label='Asignar a grupo',
                ).props('dense')

                self.assign_button = ui.button(
                    'Asignar grupo',
                    on_click=self.assign_group_to_selection
                )

            

    def _create_group_table_section(self):
        with ui.card().classes('w-full max-w-6xl') as group_card:
            ui.label("4. Tabla de Variables Clasificadas").classes('text-lg font-bold')
            ui.separator()

            # --- Filtros superiores (idénticos a la primera tabla) ---
            with ui.row().classes('mt-2 mb-2 items-center gap-2'):
                ui.label('Buscar en:').classes('text-sm')

                self.group_search_column_selector = ui.select(
                    options=['register', 'name', 'description', 'system_category'],
                    value='name',
                    label='Columna',
                    on_change= self.reset_group_search_input
                ).props('dense outlined').classes('w-48')

                self.group_search_input = ui.input(
                    placeholder='Buscador...',
                    on_change=self.apply_group_search_filter
                ).props('dense clearable outlined').classes('flex-1')

            with ui.row().classes('mt-2 mb-2 items-center gap-2'):
                ui.label('Filtrar por grupo:').classes('text-sm')

                self.group_category_filter = ui.select(
                    options=[
                        'ALARM', 'SET_POINT', 'CONFIG_PARAMETER', 'COMMAND',
                        'ANALOG_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT', 'DEFAULT', 'STATUS'
                    ],
                    multiple=True,
                    label='Selecciona grupos',
                    clearable=True,
                    on_change=self.apply_group_category_filter
                ).props('dense outlined use-chips clearable').classes('w-96')

            # --- Tabla con paginación ---
            self.group_table = ui.table(
                columns=[],
                rows=[],
                row_key='id',
                selection='multiple',
                pagination=self.pagination_group,
                on_pagination_change=self.handle_group_pagination,
            ).classes('w-full h-96').props('flat bordered dense')

            self.group_table.on('selection', self.handle_group_selection)

            with ui.row().classes('mt-4 items-center gap-4'):
                self.delete_rows_button = ui.button(
                    'Eliminar filas seleccionadas', 
                    on_click=self.delete_selected_group_rows, 
                    icon='delete'
                ).props('color=negative')

                self.clear_table_button = ui.button(
                    'Borrar toda la tabla', 
                    on_click=self.clear_group_table, 
                    icon='delete_forever'
                ).props('color=warning')

                self.download_button = ui.button(
                    'Descargar Excel', 
                    on_click=self.download_excel, 
                    icon='download'
                ).props('color=primary')

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
            # En NiceGUI 2.x, los datos de paginación vienen en e.value
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
        """Maneja el evento emitido desde el slot 'estado' cuando se cambia el dropdown.
        El payload esperado contiene la fila completa (props.row)."""
        try:
            args = getattr(e, 'args', e)
            # args puede ser el dict de la fila o una lista con la fila
            row = None
            if isinstance(args, dict):
                # en muchos casos args será la fila directamente
                row = args
            elif isinstance(args, (list, tuple)) and len(args) > 0 and isinstance(args[0], dict):
                row = args[0]
            else:
                # intentar extraer 'args' del dict
                if isinstance(args, dict) and 'args' in args:
                    row = args['args']

            if not row or 'id' not in row:
                logger.debug('Evento estado-change sin payload válido')
                return

            row_id = str(row.get('id'))
            new_group = row.get('system_category')

            if self.processed_data is None:
                logger.debug('No hay datos procesados al cambiar estado')
                return

            # Actualizar processed_data para reflejar el cambio
            self.processed_data.loc[self.processed_data['id'].astype(str) == row_id, 'system_category'] = new_group

            # Construir dataframe de la fila actualizada
            selected_row_df = self.processed_data.loc[self.processed_data['id'].astype(str) == row_id].copy()

            # Si es STATUS, modificar view a basic
            if new_group == 'STATUS':
                selected_row_df['view'] = 'basic'
                self.processed_data.loc[self.processed_data['id'].astype(str) == row_id, 'view'] = 'basic'

            if new_group == 'ALARM':
                selected_row_df['view'] = np.nan
                self.processed_data.loc[self.processed_data['id'].astype(str) == row_id, 'view'] = np.nan

            if selected_row_df.empty:
                logger.debug(f'No se encontró fila con id {row_id} en processed_data')
                return

            # Agregar o actualizar en grouped_data (mismo comportamiento que assign_group_to_selection pero para una fila)
            if self.grouped_data is None or self.grouped_data.empty:
                self.grouped_data = selected_row_df
            else:
                all_cols = list(self.grouped_data.columns)
                # Si las columnas no coinciden, reindexamos selected_row_df para que coincida
                selected_row_df = selected_row_df.reindex(columns=all_cols, fill_value=np.nan)

                # Forzar ids a string
                self.grouped_data['id'] = self.grouped_data['id'].astype(str)
                selected_row_df['id'] = selected_row_df['id'].astype(str)

                # Eliminar fila existente con ese id (para sobrescribir)
                self.grouped_data = self.grouped_data[~self.grouped_data['id'].isin(selected_row_df['id'])]

                # Concatenar
                self.grouped_data = pd.concat([selected_row_df, self.grouped_data], ignore_index=True)

            # Actualizamos la interfaz
            self.update_group_table()
            self.display_table()

            ui.notify(f'Fila {row_id} clasificada como {new_group}.', type='positive')

        except Exception as ex:
            logger.exception(f"Error manejando cambio de estado: {ex}")
            ui.notify(f"Error manejando cambio de estado: {ex}", type='negative')
    
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
        if self.search_input:
            self.search_input.value = ''
        if self.processed_data is not None and not self.processed_data.empty:
            self.table.rows = self.processed_data.to_dict('records')
            self.table.update()
        ui.notify("Filtro de búsqueda reiniciado.", type='info', timeout=1.5)

    def reset_group_search_input(self, e):
        """Limpia el cuadro de búsqueda y restaura la tabla de grupos al cambiar de columna."""
        if self.group_search_input:
            self.group_search_input.value = ''
        if self.grouped_data is not None and not self.grouped_data.empty:
            self.group_table.rows = self.grouped_data.to_dict('records')
            self.group_table.update()
        ui.notify("Filtro de búsqueda reiniciado.", type='info', timeout=1.5)
