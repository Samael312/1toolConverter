"""
Capa de Presentación - UI/UX
Maneja toda la interfaz de usuario y la interacción con el usuario.
"""
from io import BytesIO
from typing import Optional
import pandas as pd
import numpy as np
from nicegui import ui
import logging

logger = logging.getLogger(__name__)


class HTMLConverterUI:
    """
    Controlador de la interfaz de usuario para el conversor HTML a Excel.
    Maneja todos los componentes visuales y la interacción con el usuario.
    """
    
    def __init__(self, process_html_callback):
        """
        Inicializa el controlador de UI.
        
        Args:
            process_html_callback: Función de callback para procesar HTML (lógica de negocio)
        """
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
    
    async def handle_upload(self, e):
        """
        Maneja el evento de carga de archivo.
        
        Args:
            e: Evento de upload de NiceGUI
        """
        try:
            logger.info(f"Iniciando carga de archivo: {e.file.name}")
            
            # Leer el contenido del archivo
            self.uploaded_file_content = await e.file.read()
            logger.info(f"Archivo leído correctamente: {len(self.uploaded_file_content)} bytes")
            
            # Actualizar estado de los botones
            if self.process_button is not None:
                self.process_button.enable()
                logger.debug("Botón de procesamiento habilitado")
            
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
            logger.info("Carga de archivo completada exitosamente")
            
        except Exception as ex:
            logger.error(f"Error al cargar archivo: {ex}", exc_info=True)
            ui.notify(f"Error al cargar archivo: {ex}", type='negative')
    
    def process_file(self):
        """
        Procesa el archivo HTML cargado utilizando la lógica de negocio.
        """
        logger.info("Iniciando procesamiento de archivo")
        
        if self.uploaded_file_content is None:
            logger.warning("No hay contenido para procesar")
            ui.notify("No hay archivo para procesar.", type='negative')
            return
        
        logger.debug(f"Procesando {len(self.uploaded_file_content)} bytes")
        
        # Llamar a la lógica de negocio
        df = self.process_html_callback(self.uploaded_file_content)
        
        if df is not None and not df.empty:
            self.processed_data = df
            logger.info(f"Procesamiento exitoso: {len(df)} parámetros encontrados")
            
            # Actualizar estado de los botones
            if self.show_table_button is not None:
                self.show_table_button.enable()
            if self.download_button is not None:
                self.download_button.enable()
            
            ui.notify(f"{len(df)} parámetros procesados.", type='positive')
        else:
            logger.warning("No se obtuvieron datos del procesamiento")
            self.processed_data = None
            
            if self.show_table_button is not None:
                self.show_table_button.disable()
            if self.download_button is not None:
                self.download_button.disable()
    
    def display_table(self):
        """
        Muestra la tabla de datos procesados en la interfaz.
        """
        logger.info("Mostrando tabla de datos")
        
        if self.processed_data is None:
            logger.warning("No hay datos procesados para mostrar")
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
            logger.debug(f"Tabla actualizada con {len(self.table.rows)} filas")
        else:
            logger.error("table es None, no se puede mostrar")
        
        if self.table_card is not None:
            self.table_card.visible = True
            logger.debug("table_card visible")
        else:
            logger.error("table_card es None")
    
    def download_excel(self):
        """
        Genera y descarga el archivo Excel con los datos procesados.
        """
        logger.info("Iniciando descarga de Excel")
        
        if self.processed_data is None or self.processed_data.empty:
            logger.warning("No hay datos para exportar")
            ui.notify("No hay datos para exportar.", type='warning')
            return
        
        try:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                self.processed_data.to_excel(
                    writer,
                    sheet_name="Parametros_Unificados",
                    index=False
                )
            
            logger.info(f"Excel generado: {len(output.getvalue())} bytes")
            
            ui.download(
                content=output.getvalue(),
                filename='parametros_convertidos.xlsx',
                media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            ui.notify("Descarga iniciada.", type='info')
            logger.info("Descarga completada")
            
        except Exception as ex:
            logger.error(f"Error al generar Excel: {ex}", exc_info=True)
            ui.notify(f"Error al generar Excel: {ex}", type='negative')
    
    def create_ui(self):
        """
        Crea y configura la interfaz de usuario completa.
        """
        logger.info("Iniciando creación de UI")
        ui.dark_mode().set_value(True)
        
        # Header
        with ui.header().classes('items-center justify-between'):
            ui.label('Conversor HTML a Parámetros').classes('text-xl font-bold')
        
        # Contenedor principal
        with ui.column().classes('w-full p-4 md:p-8 items-center gap-8'):
            
            # Sección 1: Carga de archivo
            self._create_upload_section()
            
            # Sección 2: Procesamiento
            self._create_process_section()
            
            # Sección 3: Visualización y descarga
            self._create_results_section()
            
            # Sección 4: Tabla de datos
            self._create_table_section()
        
        logger.info("UI creada exitosamente")
        logger.debug(
            f"Componentes inicializados - "
            f"process_button: {self.process_button is not None}, "
            f"show_table_button: {self.show_table_button is not None}, "
            f"download_button: {self.download_button is not None}, "
            f"table: {self.table is not None}, "
            f"table_card: {self.table_card is not None}"
        )
    
    def _create_upload_section(self):
        """Crea la sección de carga de archivos."""
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
        """Crea la sección de procesamiento."""
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
        """Crea la sección de resultados."""
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
        """Crea la sección de la tabla de datos."""
        with ui.card().classes('w-full max-w-6xl') as table_card:
            self.table = ui.table(
                columns=[],
                rows=[],
                row_key='id'
            ).classes('w-full h-96').props('flat bordered dense')
            self.table_card = table_card
            self.table_card.visible = False

