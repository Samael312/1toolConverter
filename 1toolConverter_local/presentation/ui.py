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

        # Estado
        self.uploaded_file_content: Optional[bytes] = None
        self.processed_data: Optional[pd.DataFrame] = None
        self.grouped_data: Optional[pd.DataFrame] = pd.DataFrame()

        # Componentes UI
        self.process_button = None
        self.table = None
        self.table_card = None
        self.group_selector = None
        self.assign_button = None
        self.selected_rows = []

        # Segunda tabla
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
            if self.download_button:
                self.download_button.enable()
            ui.notify(f"{len(df)} parámetros procesados.", type='positive')
            self.display_table()  # ✅ Mostrar tabla automáticamente
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
                "read", "write", "sampling", "minvalue", "maxvalue", "unit"]

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
            ui.label('Conversor HTML a Parámetros').classes('text-xl font-bold')

        with ui.column().classes('w-full p-4 md:p-8 items-center gap-8'):
            self._create_upload_section()
            self._create_process_section()
            self._create_table_section()
            self._create_group_table_section()

    def _create_upload_section(self):
        with ui.card().classes('w-full max-w-2xl'):
            ui.label('1. Cargar Archivo HTML').classes('text-lg font-bold')
            ui.separator()
            upload = ui.upload(
                label='Seleccionar o arrastrar archivo HTML',
                auto_upload=True,
                max_files=1
            ).props('accept=".html"').classes('w-full')
            upload.on_upload(self.handle_upload)

    def _create_process_section(self):
        with ui.card().classes('w-full max-w-2xl'):
            ui.label('2. Procesar el Archivo y Mostrar Tabla').classes('text-lg font-bold')
            with ui.row():
                self.process_button = ui.button(
                    'Procesar Archivo',
                    on_click=self.process_file,
                    icon='play_for_work'
                )
                self.process_button.disable()  # se habilita al subir archivo

    def _create_table_section(self):
        with ui.card().classes('w-full max-w-6xl') as table_card:
            ui.label("3. Tabla de Parámetros").classes('text-lg font-bold')
            ui.separator()

            self.table_card = table_card
            self.table_card.visible = False

            cols = ["id", "register", "name", "description", "system_category",
                    "read", "write", "sampling", "minvalue", "maxvalue", "unit"]

            self.table = ui.table(
                columns=[{'name': c, 'label': c.replace('_', ' ').title(), 'field': c, 'sortable': True} for c in cols],
                rows=[],
                row_key='id',
                selection='multiple',
            ).classes('w-full h-96').props('flat bordered dense')

            self.table.on('selection', self.handle_selection)

            self.table.add_slot('body-cell-estado', '''
                <q-td key="estado" :props="props">
                    <template v-if="props.row.system_category">
                        <div style="font-size: 12px; display: flex; align-items: center;">
                            <q-icon
                                name="check_circle"
                                :color="{
                                    'ALARM': 'red',
                                    'SET_POINT': 'blue',
                                    'CONFIG_PARAMETER': 'orange',
                                    'COMMAND': 'purple',
                                    'ANALOG_INPUT': 'teal',
                                    'ANALOG_OUTPUT': 'cyan',
                                    'DIGITAL_INPUT': 'amber',
                                    'DIGITAL_OUTPUT': 'green'
                                }[props.row.system_category] || 'grey'"
                                size="xs"
                                class="q-mr-xs"
                            />
                            <span>{{ props.row.system_category }}</span>
                        </div>
                    </template>
                    <span v-else style="font-size: 12px;">—</span>
                </q-td>
            ''')

            with ui.row().classes('mt-4 items-center gap-4'):
                self.group_selector = ui.select(
                    options=[
                        'ALARM', 'SET_POINT', 'CONFIG_PARAMETER', 'COMMAND',
                        'ANALOG_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT'
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

            self.group_table = ui.table(
                columns=[],
                rows=[],
                row_key='id',
                selection='multiple',
            ).classes('w-full h-96').props('flat bordered dense')

            self.group_table.on('selection', self.handle_group_selection)

            with ui.row().classes('mt-4 items-center gap-4'):
                self.delete_rows_button = ui.button('Eliminar filas seleccionadas', on_click=self.delete_selected_group_rows, icon='delete').props('color=negative')
                self.clear_table_button = ui.button('Borrar toda la tabla', on_click=self.clear_group_table, icon='delete_forever').props('color=warning')
                self.download_button = ui.button('Descargar Excel', on_click=self.download_excel, icon='download').props('color=primary')
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
                    [self.grouped_data, selected_rows_df],
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
                "read", "write", "sampling", "minvalue", "maxvalue", "unit"]

            self.group_table.columns = [
                {'name': c, 'label': c.replace('_', ' ').title(), 'field': c, 'sortable': True}
                for c in cols
            ]
            self.group_table.rows = self.grouped_data.replace({np.nan: ''}).to_dict('records')
            self.group_table_card.visible = True
        else:
            self.group_table.rows = []
            self.group_table_card.visible = True
