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

logger = logging.getLogger(__name__)

class HandleMixin:

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
                # Para otros backends, sobrescribimos el archivo
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

    def handle_backend_selection(self, e):
            """ Activa o desactiva la UI según el backend seleccionado."""
            backend = e.value
            self.backend_selected = backend

            # Reiniciar interfaz al cambiar de backend
            self._reset_ui_state()

            # Reiniciar también los filtros de búsqueda
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

                # Si se selecciona "primary", removerlo de otras filas.
                if new_view == 'primary':
                    # Encontrar cualquier fila que tenga "primary" excepto la actual
                    mask_primary = (
                        (self.processed_data['view'] == 'primary') &
                        (self.processed_data['id'].astype(str) != row_id)
                    )

                    # Cambiar esas vistas a "simple"
                    self.processed_data.loc[mask_primary, 'view'] = 'simple'

                # Ahora aplicar el nuevo valor a la fila actual
                self.processed_data.loc[self.processed_data['id'].astype(str) == row_id, 'view'] = new_view

                # Reconstruir dataframe de la fila actualizada
                selected_row_df = self.processed_data.loc[self.processed_data['id'].astype(str) == row_id].copy()

                if selected_row_df.empty:
                    return

            # Sincronizar grouped_data con los cambios en processed_data (especialmente para el caso "primary")
                if self.grouped_data is not None and not self.grouped_data.empty:
                    # Actualizamos todas las vistas desde processed_data
                    self.grouped_data['view'] = self.grouped_data['id'].astype(str).map(
                        dict(zip(self.processed_data['id'].astype(str), self.processed_data['view']))
                    )

                # Agregar o reemplazar solo la fila actualizada
                if self.grouped_data is None or self.grouped_data.empty:
                    self.grouped_data = selected_row_df
                else:
                    all_cols = list(self.grouped_data.columns)
                    selected_row_df = selected_row_df.reindex(columns=all_cols, fill_value=np.nan)

                    self.grouped_data['id'] = self.grouped_data['id'].astype(str)
                    selected_row_df['id'] = selected_row_df['id'].astype(str)

                    self.grouped_data = self.grouped_data[~self.grouped_data['id'].isin(selected_row_df['id'])]
                    self.grouped_data = pd.concat([selected_row_df, self.grouped_data], ignore_index=True)


                # Refrescar tablas
                self.update_group_table()
                self.display_table()

                ui.notify(f'Fila {row_id} ahora tiene vista "{new_view}".', type='positive')

            except Exception as ex:
                logger.exception(f"Error manejando cambio de vista: {ex}")
                ui.notify(f"Error manejando cambio de vista: {ex}", type='negative')

    def handle_field_change(self, e, field_name: str, label: str = None):
        """Manejador genérico para cambios en un campo editable de la tabla."""
        try:
            # --- 1. Extraer fila del evento ---
            args = getattr(e, 'args', e)
            if isinstance(args, dict):
                row = args
            elif isinstance(args, (list, tuple)) and args and isinstance(args[0], dict):
                row = args[0]
            else:
                ui.notify('Evento sin datos válidos', type='warning')
                return

            row_id = str(row.get('id'))
            
            # Obtener y limpiar el nuevo valor
            raw_value = row.get(field_name, '')
            new_value = raw_value.strip() if isinstance(raw_value, str) else raw_value

            logger.info(f"🧾 Actualizando {label} (ID={row_id}) -> '{new_value}'")

            # --- 2. Actualizar processed_data ---
            if self.processed_data is not None and not self.processed_data.empty:
                # Creamos la máscara para encontrar la fila por ID
                mask = self.processed_data['id'].astype(str) == row_id
                
                if mask.any():
                    # A. Guardamos el nuevo valor
                    self.processed_data.loc[mask, field_name] = new_value
                    
                    # B. Reseteamos el error_flag a 0 
                    self.processed_data.loc[mask, 'error_flag'] = 0 
                    
                    logger.info(f"processed_data: {field_name} actualizado y error_flag limpiado.")

            # --- 3. Actualizar grouped_data (si existe) ---
            if self.grouped_data is not None and not self.grouped_data.empty:
                mask_g = self.grouped_data['id'].astype(str) == row_id
                if mask_g.any():
                    self.grouped_data.loc[mask_g, field_name] = new_value
                    # Si grouped_data también tiene error_flag, actualízalo:
                    if 'error_flag' in self.grouped_data.columns:
                        self.grouped_data.loc[mask_g, 'error_flag'] = 0

            # --- 4. Actualizar contadores ---
            self.update_error_counter()

            # --- 5. Actualizar visualmente la tabla ---
            if hasattr(self, 'error_filter_active') and self.error_filter_active:
                # Si el filtro de errores está activo, recargamos toda la tabla filtrada:
                df_display = self.processed_data.copy()
                df_filtered = df_display[df_display['error_flag'] == 1]
                self.table.rows = df_filtered.replace({np.nan: ''}).to_dict('records')
                self.table.update()
                ui.notify(f"Corrección aplicada. Error resuelto.", type='positive')
            else:
                # Actualizamos solo la fila modificada en la tabla visible
                if self.table and self.table.rows:
                    for r in self.table.rows:
                        if str(r.get('id')) == row_id:
                            r[field_name] = new_value
                            r['error_flag'] = 0 # Visualmente quitamos el flag también
                            break
                    self.table.update()
                    ui.notify(f"{label} actualizado", type='positive')

            # Actualizar tablas auxiliares si es necesario
            if hasattr(self, 'update_group_table'):
                self.update_group_table()

        except Exception as ex:
            import traceback
            logger.error(f" Error en handle_field_change({field_name}):\n" + traceback.format_exc())
            ui.notify(f"Error actualizando {label or field_name}: {ex}", type='negative')