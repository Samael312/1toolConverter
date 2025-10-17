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

        # Componentes de UI
        self.process_button = None
        self.show_table_button = None
        self.download_button = None
        self.table = None
        self.table_card = None
        self.group_selector = None
        self.assign_button = None
        self.selected_rows = []

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

    def download_excel(self):
        """Genera, descarga y limpia el archivo Excel temporal."""
        if self.processed_data is None or self.processed_data.empty:
            ui.notify("No hay datos para exportar.", type='warning')
            return

        try:
            with NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                with pd.ExcelWriter(tmp.name, engine='openpyxl') as writer:
                    self.processed_data.to_excel(writer, sheet_name="Parametros_Unificados", index=False)
                tmp.flush()
                file_path = tmp.name

            ui.download(file_path, filename='parametros_convertidos.xlsx')
            ui.notify("Descarga iniciada.", type='info')

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
            self._create_results_section()
            self._create_table_section()

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
            ui.label('2. Procesar el Archivo').classes('text-lg font-bold')
            ui.separator()
            self.process_button = ui.button(
                'Procesar Archivo',
                on_click=self.process_file,
                icon='play_for_work'
            )
            self.process_button.disable()

    def _create_results_section(self):
        """Sección de resultados."""
        with ui.card().classes('w-full max-w-2xl'):
            ui.label('3. Visualizar y Descargar Resultados').classes('text-lg font-bold')
            ui.separator()
            with ui.row():
                self.show_table_button = ui.button(
                    'Mostrar en Tabla',
                    on_click=self.display_table,
                    icon='visibility'
                )
                self.show_table_button.disable()

                self.download_button = ui.button(
                    'Descargar Excel',
                    on_click=self.download_excel,
                    icon='download'
                ).props('color=primary')
                self.download_button.disable()

    def _create_table_section(self):
        """Sección de la tabla de datos sin organización."""
        with ui.card().classes('w-full max-w-6xl') as table_card:
            ui.label("4. Tabla de Parámetros").classes('text-lg font-bold')
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
                        'ANALOG_INPUT',
                        'COMMAND',
                        'DIGITAL_INPUT'
                    ],
                    label='Asignar a grupo',
                ).props('dense')

                self.assign_button = ui.button(
                    'Asignar grupo',
                    on_click=self.assign_group_to_selection
                )

            self.table_card = table_card
            self.table_card.visible = False

    def handle_selection(self, e):
        """
        Normaliza el payload de selección del evento de NiceGUI y guarda
        una lista de 'row_key' (en tu caso 'name') en self.selected_rows.
        Maneja varios formatos posibles que puede traer e.args.
        """
        try:
            args = getattr(e, 'args', e)

            # Normalizar el contenido a un "posible" objeto
            payload = None
            if isinstance(args, (list, tuple)):
                # si viene una lista con un único elemento que a su vez es la lista real:
                if len(args) == 1:
                    payload = args[0]
                else:
                    payload = args
            else:
                payload = args

            # Extraer lista de seleccionados según estructura
            selected = []
            if isinstance(payload, dict):
                # casos comunes: {'value': [...]}, {'rows': [...]}, {'selected': [...]}
                if 'value' in payload:
                    selected = payload['value']
                elif 'rows' in payload:
                    selected = payload['rows']
                elif 'selected' in payload:
                    selected = payload['selected']
                else:
                    # intentar tomar cualquier value que sea lista
                    for v in payload.values():
                        if isinstance(v, (list, tuple)):
                            selected = v
                            break
                    if not selected:
                        # fallback: convertir dict a lista de items
                        selected = [payload]
            elif isinstance(payload, (list, tuple, set)):
                selected = list(payload)
            elif payload is None:
                selected = []
            else:
                selected = [payload]

            # Normalizar cada elemento: si es dict, intentar extraer el row_key 'name'
            normalized = []
            for item in selected:
                if isinstance(item, dict):
                    # Prioriza 'name' (tu row_key), si no pruebo con otras claves string
                    if 'name' in item:
                        normalized.append(item['name'])
                    elif 'row_key' in item:
                        normalized.append(item['row_key'])
                    else:
                        # busca la primera cadena en los valores
                        found = False
                        for v in item.values():
                            if isinstance(v, str):
                                normalized.append(v)
                                found = True
                                break
                        if not found:
                            # si no hay string, guarda el dict entero (como fallback)
                            normalized.append(item)
                else:
                    # puede ser ya un string (row_key) o un índice numérico
                    normalized.append(item)

            # Guardar lista limpia (sin duplicados manteniendo orden)
            seen = set()
            final = []
            for x in normalized:
                # convertir a str para homogeneizar claves no-hashables
                key = x if isinstance(x, (int, str)) else str(x)
                if key not in seen:
                    seen.add(key)
                    final.append(x)

            self.selected_rows = final
            logger.debug(f"Selección normalizada: {self.selected_rows}")

        except Exception as ex:
            logger.exception(f"Error procesando selección: {ex}")
            self.selected_rows = []

    def assign_group_to_selection(self):
        """
        Asigna el grupo seleccionado a las filas marcadas.
        Usa una máscara segura para contar y aplicar los cambios sobre el DataFrame.
        """
        if not self.selected_rows:
            ui.notify('Selecciona una o más filas primero.', type='warning')
            return

        group = self.group_selector.value
        if not group:
            ui.notify('Selecciona un grupo.', type='warning')
            return

        try:
            # Asegurarse de que la columna 'name' existe
            if self.processed_data is None or 'name' not in self.processed_data.columns:
                ui.notify('No hay datos cargados o no existe la columna "name".', type='warning')
                return

            # Crear máscara con los elementos seleccionados (convierte todo a str para evitar problemas)
            selected_as_str = [str(x) for x in self.selected_rows]
            mask = self.processed_data['name'].astype(str).isin(selected_as_str)

            n_affected = int(mask.sum())
            if n_affected == 0:
                ui.notify('No se encontraron filas coincidentes para asignar.', type='warning')
                return

            # Aplicar la asignación
            self.processed_data.loc[mask, 'system_category'] = group
            self.update_table_rows()

            ui.notify(f'Se asignó "{group}" a {n_affected} fila(s).', type='positive')
            logger.info(f'Se asignó "{group}" a {n_affected} filas.')

        except Exception as ex:
            logger.exception(f"Error al asignar grupo: {ex}")
            ui.notify(f"Error al asignar grupo: {ex}", type='negative')

    def update_table_rows(self):
        """Actualiza las filas visibles de la tabla."""
        if self.table is None or self.processed_data is None:
            return
        rows = self.processed_data.replace({np.nan: ''}).to_dict('records')
        self.table.rows = rows