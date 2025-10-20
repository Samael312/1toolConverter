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

        # Estado de la aplicación
        self.uploaded_file_content: Optional[bytes] = None
        self.processed_data: Optional[pd.DataFrame] = None
        self.grouped_data: Optional[pd.DataFrame] = pd.DataFrame()  # nueva tabla para clasificados

        # Componentes de UI
        self.process_button = None
        self.show_table_button = None
        self.table = None
        self.table_card = None
        self.group_selector = None
        self.assign_button = None
        self.selected_rows = []

        # Componentes de segunda tabla
        self.group_table = None
        self.group_table_card = None
        self.delete_rows_button = None
        self.clear_table_button = None
        self.download_button = None
        self.selected_group_rows = []

    async def handle_upload(self, e):
        """Maneja el evento de carga de archivo."""
        try:
            logger.info(f"Iniciando carga de archivo: {e.file.name}")

            self.uploaded_file_content = await e.file.read()
            logger.info(f"Archivo leído correctamente: {len(self.uploaded_file_content)} bytes")

            if self.process_button is not None:
                self.process_button.enable()
            if self.show_table_button is not None:
                self.show_table_button.disable()
            if self.download_button is not None:
                self.download_button.disable()
            if self.table_card is not None:
                self.table_card.visible = False
            if self.group_table_card is not None:
                self.group_table_card.visible = False

            ui.notify(
                f"Archivo '{e.file.name}' cargado correctamente ({len(self.uploaded_file_content)} bytes).",
                type='positive'
            )

        except Exception as ex:
            logger.error(f"Error al cargar archivo: {ex}", exc_info=True)
            ui.notify(f"Error al cargar archivo: {ex}", type='negative')

    def process_file(self):
        """Procesa el archivo HTML cargado utilizando la lógica de negocio."""
        if self.uploaded_file_content is None:
            ui.notify("No hay archivo para procesar.", type='negative')
            return

        df = self.process_html_callback(self.uploaded_file_content)

        if df is not None and not df.empty:
            self.processed_data = df

            if self.show_table_button is not None:
                self.show_table_button.enable()
            if self.download_button is not None:
                self.download_button.enable()

            ui.notify(f"{len(df)} parámetros procesados.", type='positive')
        else:
            self.processed_data = None
            ui.notify("No se obtuvieron datos del procesamiento.", type='warning')

            if self.show_table_button is not None:
                self.show_table_button.disable()
            if self.download_button is not None:
                self.download_button.disable()

    def display_table(self):
        """Muestra la tabla de datos procesados en la interfaz."""
        if self.processed_data is None:
            ui.notify("No hay datos procesados.", type='warning')
            return

        cols = ["id", "register", "name", "description", "system_category",
                "read", "write", "offset", "unit", "length"]

        if self.table is not None:
            self.table.columns = [
                {
                    'name': c,
                    'label': c.replace('_', ' ').title(),
                    'field': c,
                    'sortable': True
                }
                for c in cols
            ]
            self.table.rows = self.processed_data.replace({np.nan: ''}).to_dict('records')

        if self.table_card is not None:
            self.table_card.visible = True

        if self.group_table_card is not None:
            self.group_table_card.visible = True

    def download_excel(self):
        """Genera, descarga y limpia el archivo Excel temporal."""
        if self.processed_data is None or self.processed_data.empty:
            ui.notify("No hay datos para exportar.", type='warning')
            return
        try:
            # Elegir qué tabla descargar
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
                try:
                    if os.path.exists(path):
                        os.remove(path)
                        logger.debug(f"Archivo temporal eliminado: {path}")
                except Exception as cleanup_error:
                    logger.warning(f"No se pudo eliminar el archivo temporal: {cleanup_error}")

            ui.timer(1.0, lambda: asyncio.create_task(cleanup_file(file_path)), once=True)

        except Exception as ex:
            logger.error(f"Error al generar Excel: {ex}", exc_info=True)
            ui.notify(f"Error al generar Excel: {ex}", type='negative')

    def create_ui(self):
        """Crea y configura la interfaz de usuario completa."""
        ui.dark_mode().set_value(True)

        with ui.header().classes('items-center justify-between'):
            ui.label('Conversor HTML a Parámetros').classes('text-xl font-bold')

        with ui.column().classes('w-full p-4 md:p-8 items-center gap-8'):
            self._create_upload_section()
            self._create_process_section()
            self._create_table_section()
            self._create_group_table_section()

    def _create_upload_section(self):
        """Sección de carga de archivo."""
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
        """Sección de procesamiento."""
        with ui.card().classes('w-full max-w-2xl'):
            ui.label('2. Procesar el Archivo y Mostrar Tabla').classes('text-lg font-bold')
            with ui.row():
                self.process_button = ui.button(
                    'Procesar Archivo',
                    on_click=self.process_file,
                    icon='play_for_work'
                )
                self.process_button.disable()
            
                self.show_table_button = ui.button(
                    'Mostrar en Tabla',
                    on_click=self.display_table,
                    icon='visibility'
                )
                self.show_table_button.disable()
                
    def _create_table_section(self):
        """Sección de la tabla principal."""
        with ui.card().classes('w-full max-w-6xl') as table_card:
            ui.label("3. Tabla de Parámetros").classes('text-lg font-bold')
            ui.separator()

            self.table = ui.table(
                columns=[],
                rows=[],
                row_key='name',
                selection='multiple',
            ).classes('w-full h-96').props('flat bordered dense')

            self.table.on('selection', self.handle_selection)

            with ui.row().classes('mt-4 items-center gap-4'):
                self.group_selector = ui.select(
                    options=[
                        'ALARM',
                        'SET_POINT',
                        'CONFIG_PARAMETER',
                        'COMMAND',
                        'ANALOG_INPUT',
                        'ANALOG_OUTPUT',
                        'DIGITAL_INPUT',
                        'DIGITAL_OUTPUT',
                    ],
                    label='Asignar a grupo',
                ).props('dense')

                self.assign_button = ui.button(
                    'Asignar grupo',
                    on_click=self.assign_group_to_selection
                )

            self.table_card = table_card
            self.table_card.visible = False

    def _create_group_table_section(self):
        """Sección de la tabla con las variables clasificadas."""
        with ui.card().classes('w-full max-w-6xl') as group_card:
            ui.label("4. Tabla de Variables Clasificadas").classes('text-lg font-bold')
            ui.separator()

            self.group_table = ui.table(
                columns=[],
                rows=[],
                row_key='name',
                selection='multiple',
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
                if 'value' in payload:
                    selected_now = payload['value']
                elif 'rows' in payload:
                    selected_now = payload['rows']
                elif 'selected' in payload:
                    selected_now = payload['selected']
            elif isinstance(payload, (list, tuple)):
                selected_now = list(payload)
            elif payload is not None:
                selected_now = [payload]

            # Extraer claves de fila (row_key = 'name')
            new_selection = []
            for item in selected_now:
                if isinstance(item, dict):
                    if 'name' in item:
                        new_selection.append(item['name'])
                    elif 'row_key' in item:
                        new_selection.append(item['row_key'])
                elif isinstance(item, str):
                    new_selection.append(item)

            # Reemplazar lista completa con la que el componente tiene actualmente
            if hasattr(self.table, 'selected'):
                # NiceGUI almacena la selección real aquí
                current_selection = [
                    row['name'] if isinstance(row, dict) and 'name' in row else row
                    for row in getattr(self.table, 'selected', [])
                ]
                self.selected_rows = current_selection
            else:
                self.selected_rows = new_selection

            # Eliminar duplicados
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
                if 'value' in payload:
                    selected_now = payload['value']
                elif 'rows' in payload:
                    selected_now = payload['rows']
                elif 'selected' in payload:
                    selected_now = payload['selected']
            elif isinstance(payload, (list, tuple)):
                selected_now = list(payload)
            elif payload is not None:
                selected_now = [payload]

            # Extraer claves de fila (row_key = 'name')
            new_selection = []
            for item in selected_now:
                if isinstance(item, dict):
                    if 'name' in item:
                        new_selection.append(item['name'])
                    elif 'row_key' in item:
                        new_selection.append(item['row_key'])
                elif isinstance(item, str):
                    new_selection.append(item)

            # Leer la selección real actual del componente
            if hasattr(self.group_table, 'selected'):
                current_selection = [
                    row['name'] if isinstance(row, dict) and 'name' in row else row
                    for row in getattr(self.group_table, 'selected', [])
                ]
                self.selected_group_rows = current_selection
            else:
                self.selected_group_rows = new_selection

            # Quitar duplicados
            self.selected_group_rows = list(dict.fromkeys(self.selected_group_rows))

            logger.debug(f"Selección actualizada en tabla de grupos: {self.selected_group_rows}")

        except Exception as ex:
            logger.exception(f"Error procesando selección en tabla de grupos: {ex}")
            self.selected_group_rows = []


    def assign_group_to_selection(self):
        """Asigna el grupo seleccionado a las filas marcadas y las agrega a la tabla clasificada."""
        if not self.selected_rows:
            ui.notify('Selecciona una o más filas primero.', type='warning')
            return

        group = self.group_selector.value
        if not group:
            ui.notify('Selecciona un grupo.', type='warning')
            return

        try:
            selected_as_str = [str(x) for x in self.selected_rows]
            mask = self.processed_data['name'].astype(str).isin(selected_as_str)
            selected_rows_df = self.processed_data.loc[mask].copy()
            selected_rows_df['system_category'] = group

            # Agregar a la tabla de grupos
            if self.grouped_data is None or self.grouped_data.empty:
                self.grouped_data = selected_rows_df
            else:
                self.grouped_data = pd.concat([self.grouped_data, selected_rows_df], ignore_index=True).drop_duplicates(subset=['name'])

            self.update_group_table()
            ui.notify(f'Se asignó "{group}" a {len(selected_rows_df)} fila(s).', type='positive')

        except Exception as ex:
            logger.exception(f"Error al asignar grupo: {ex}")
            ui.notify(f"Error al asignar grupo: {ex}", type='negative')

    def delete_selected_group_rows(self):
        """Elimina las filas seleccionadas de la tabla clasificada."""
        if not self.selected_group_rows:
            ui.notify('Selecciona una o más filas para eliminar.', type='warning')
            return

        try:
            before_count = len(self.grouped_data)
            self.grouped_data = self.grouped_data[~self.grouped_data['name'].astype(str).isin(self.selected_group_rows)]
            self.update_group_table()
            after_count = len(self.grouped_data)
            deleted = before_count - after_count
            ui.notify(f'Se eliminaron {deleted} fila(s).', type='positive')
        except Exception as ex:
            logger.exception(f"Error al eliminar filas: {ex}")
            ui.notify(f"Error al eliminar filas: {ex}", type='negative')

    def clear_group_table(self):
        """Limpia completamente la tabla clasificada."""
        try:
            count = len(self.grouped_data)
            self.grouped_data = pd.DataFrame()
            self.update_group_table()
            ui.notify(f'Tabla vaciada ({count} filas eliminadas).', type='info')
        except Exception as ex:
            logger.exception(f"Error al limpiar tabla: {ex}")
            ui.notify(f"Error al limpiar tabla: {ex}", type='negative')

    def update_group_table(self):
        """Actualiza la tabla de variables clasificadas."""
        if self.group_table is None:
            return

        if self.grouped_data is not None and not self.grouped_data.empty:
            cols = ["id", "register", "name", "description", "system_category",
                    "read", "write", "offset", "unit", "length"]

            self.group_table.columns = [
                {'name': c, 'label': c.replace('_', ' ').title(), 'field': c, 'sortable': True}
                for c in cols
            ]
            self.group_table.rows = self.grouped_data.replace({np.nan: ''}).to_dict('records')
            self.group_table_card.visible = True
        else:
            self.group_table.rows = []
            self.group_table_card.visible = True
