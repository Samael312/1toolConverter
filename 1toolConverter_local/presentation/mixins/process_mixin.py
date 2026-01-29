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
from backend.General import logic

logger = logging.getLogger(__name__)

class ProcessMixin:

    async def process_file(self, e):
            """
            Procesa el archivo cargado.
            Flujo corregido: Carga -> Calcula Errores -> Actualiza Botón -> Muestra Tabla.
            """
            if not self.uploaded_file_contents:
                ui.notify("No hay archivo para procesar.", type='negative')
                return

            # ---------------------------------------------------------
            # 1. REINICIO COMPLETO DEL ESTADO
            # ---------------------------------------------------------
            self.processed_data = None
            self.grouped_data = pd.DataFrame()
            self.selected_rows = []
            self.selected_group_rows = []
            
            # Limpiar inputs de búsqueda
            self.reset_search_input(e)
            self.reset_group_search_input(e)

            # Limpiar Tablas Visuales
            if self.table:
                self.table.rows = []
                self.table.update()
            if self.group_table:
                self.group_table.rows = []
                self.group_table.update()
                
            # Ocultar tarjetas y deshabilitar descarga
            if self.table_card:
                self.table_card.visible = False
            if self.group_table_card:
                self.group_table_card.visible = False
            if self.download_button:
                self.download_button.disable()

            try:
                # ---------------------------------------------------------
                # 2. OBTENER DATOS DEL BACKEND
                # ---------------------------------------------------------
                if self.backend_selected == "Dixell":
                    df = await self.process_html_callback(self.uploaded_file_contents)
                else:
                    df = await self.process_html_callback(self.uploaded_file_contents[-1])

                # ---------------------------------------------------------
                # 3. PROCESAMIENTO DE DATOS Y ERRORES
                # ---------------------------------------------------------
                if df is not None and not df.empty:
                    self.processed_data = df

                    
                    # Creamos la columna 'error_flag' (1 = Error, 0 = OK)
                    self.processed_data['error_flag'] = self.processed_data['description'].apply(
                        lambda desc: 1 if self.validate_description_e(desc) is not True else 0
                    )

                    
                    error_count = self.processed_data['error_flag'].sum()

                   
                    if hasattr(self, 'error_button'):
                        self.error_button.text = f"Errores: {error_count}"
                        
                        if error_count > 0:
                            # Rojo si hay errores
                            self.error_button.props('color=negative outline icon=warning')
                        else:
                            # Verde si todo está limpio
                            self.error_button.props('color=positive flat icon=check_circle')

                    # ---------------------------------------------------------
                    # 4. CLASIFICACIÓN AUTOMÁTICA (GRUPOS)
                    # ---------------------------------------------------------
                    valid_groups1 = [
                        'ALARM', 'SET_POINT', 'CONFIG_PARAMETER', 'COMMAND',
                        'ANALOG_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT', 'STATUS',
                        'SYSTEM'
                    ]
                    valid_groups2 = ['basic', 'primary']

                    # Filtrar subconjuntos
                    auto_grouped1 = df[df['system_category'].isin(valid_groups1)]
                    auto_grouped2 = df[df['view'].isin(valid_groups2)]
                    
                    # Unir y eliminar duplicados
                    combined_grouped = pd.concat([auto_grouped1, auto_grouped2]).drop_duplicates()

                    if not combined_grouped.empty:
                        self.grouped_data = combined_grouped.reset_index(drop=True)
                        ui.notify(
                            f"{len(combined_grouped)} variables clasificadas automáticamente.", 
                            type='positive', 
                            timeout=2.5
                        )

                    # ---------------------------------------------------------
                    # 5. ACTUALIZAR INTERFAZ FINAL
                    # ---------------------------------------------------------
                    # Habilitar descarga
                    if self.download_button:
                        self.download_button.enable()

                    # Mostrar las tablas 
                    self.display_table()
                    self.update_group_table()
                    
                    # Notificación final
                    ui.notify(f" Procesado: {len(df)} filas. Errores detectados: {error_count}", type='positive')

                else:
                    # Caso DataFrame vacío
                    self.processed_data = None
                    ui.notify("El archivo no contiene datos válidos.", type='warning')

            except Exception as ex:
                import traceback
                logger.error(f" Error crítico en process_file:\n{traceback.format_exc()}")
                ui.notify(f"Error procesando el archivo: {str(ex)}", type='negative')

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

    def download_excel(self):
        if self.processed_data is None or self.processed_data.empty:
            ui.notify("No hay datos para exportar.", type='warning')
            return

        try:
            # 1. RECUPERAR NOMBRE ORIGINAL
            # Definimos un nombre base por defecto por seguridad
            base_name = "exportacion"
            
            # Verificamos si existe la lista y tiene elementos
            if hasattr(self, 'uploaded_file_names') and self.uploaded_file_names:
                # Tomamos el primer archivo (asumiendo flujo de archivo único para Excel)
                original_full_name = self.uploaded_file_names[0]
                # Quitamos la extensión (.xlsx) para quedarnos solo con el nombre
                base_name = os.path.splitext(original_full_name)[0]

            # 2. DEFINIR DATOS Y NOMBRE FINAL
            if self.grouped_data is not None and not self.grouped_data.empty:
                df_to_export = self.grouped_data
                # Ejemplo: MiArchivo_clasificado.xlsx
                file_name = f"{base_name}_clasificado.xlsx"
            else:
                df_to_export = self.processed_data
                # Ejemplo: MiArchivo_procesado.xlsx
                file_name = f"{base_name}_procesado.xlsx"

            # Limpieza de columnas (ID)
            if 'id' in df_to_export.columns:
                df_to_export['id'] = np.nan

            # 3. GENERAR Y DESCARGAR
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
                self.processed_data.loc[
                    self.processed_data['id'].astype(str).isin(selected_as_str), 
                    'system_category'
                ] = group

                selected_rows_df = self.processed_data.loc[
                    self.processed_data['id'].astype(str).isin(selected_as_str)
                ].copy()

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

                    # Eliminar filas existentes con esos IDs 
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