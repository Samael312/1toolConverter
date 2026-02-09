import pandas as pd
import numpy as np
from nicegui import run
import re
import os
import asyncio
from tempfile import NamedTemporaryFile
import logging
from backend.General.logic import validate_description_text, calculate_errors

from nicegui import ui

logger = logging.getLogger(__name__)

class FunctionMixin:
    
    def validate_description_e(self, texto):
            if texto is None:
                return "El texto está vacío"
            
            # 1. Limpiar caracteres no válidos y comparar
            cleaned = re.sub(r"[^a-zA-Z0-9\s\.,;:_\-/=%°CñÑáéíóúÁÉÍÓÚ'()]", "", texto)
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
            if len(texto) == 0:
                self.download_button.disable()
                return "Debe tener descripcion"

            # 3. Límite suave
            if len(texto) > 60:
                self.download_button.disable()
                return "La descripción supera el límite recomendado de 60 caracteres"

            return True

    def calculate_errors(df: pd.DataFrame) -> pd.DataFrame:
        """Añade la columna error_flag al DataFrame."""
        if df is None or df.empty:
            return df
        
        # Aplicamos la validación
        df['error_flag'] = df['description'].apply(
            lambda desc: 1 if validate_description_text(desc) is not True else 0
        )
        return df

    def generate_excel_file(df: pd.DataFrame, file_name_prefix: str) -> str:
        """Genera el Excel temporal y devuelve la ruta."""
        # Limpieza previa para exportación
        df_export = df.copy()
        if 'id' in df_export.columns:
            df_export['id'] = np.nan

        with NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            with pd.ExcelWriter(tmp.name, engine='openpyxl') as writer:
                df_export.to_excel(writer, sheet_name="Parametros", index=False)
            return tmp.name

    async def deleted_selected_rows(self):
            """
            Lógica de borrado UNIDIRECCIONAL:
            1. Selección en Main -> Borra en Main Y en Group.
            2. Selección en Group -> Borra SOLO en Group (Main se mantiene intacto).
            """
            ROW_KEY = 'name' 
            
            logger.info("🗑️ Iniciando borrado inteligente...")
            ids_from_main = set()
            ids_from_group = set()
            rows_deleted = 0

            # --- 1. PROCESAR SELECCIÓN DE TABLA PRINCIPAL (MAIN) ---
            # Regla: Lo que se borra aquí, desaparece de AMBOS lados.
            if hasattr(self, 'table') and self.table.selected:
                # Capturamos IDs
                ids_from_main = {row.get(ROW_KEY) for row in self.table.selected if row.get(ROW_KEY)}
                
                if ids_from_main:
                    # A. Borrar de Main Data
                    if self.processed_data is not None:
                        self.processed_data = self.processed_data[~self.processed_data[ROW_KEY].isin(ids_from_main)]
                    
                    # B. Borrar de Main UI
                    self.table.rows = [r for r in self.table.rows if r.get(ROW_KEY) not in ids_from_main]
                    self.table.selected = [] # Limpiar selección
                    self.table.update()
                    
                    rows_deleted += len(ids_from_main)
                    logger.info(f"Main: Borradas {len(ids_from_main)} filas (se replicará en grupos).")

            # --- 2. PROCESAR SELECCIÓN DE TABLA GRUPOS (GROUP) ---
            # Regla: Lo que se borra aquí, SOLO desaparece de aquí.
            if hasattr(self, 'group_table') and self.group_table.selected:
                
                ids_from_group = {row.get(ROW_KEY) for row in self.group_table.selected if row.get(ROW_KEY)}

            # --- 3. SINCRONIZACIÓN FINAL ---
            
            all_ids_to_remove_from_group = ids_from_main.union(ids_from_group)

            if all_ids_to_remove_from_group:
                # A. Borrar de Group Data
                if self.grouped_data is not None and not self.grouped_data.empty:
                    initial_len = len(self.grouped_data)
                    self.grouped_data = self.grouped_data[~self.grouped_data[ROW_KEY].isin(all_ids_to_remove_from_group)]
                    
                    
                    logger.info(f"Group: Se eliminaron {initial_len - len(self.grouped_data)} filas.")

                # B. Borrar de Group UI
                if hasattr(self, 'group_table'):
                    self.group_table.rows = [r for r in self.group_table.rows if r.get(ROW_KEY) not in all_ids_to_remove_from_group]
                    self.group_table.selected = []
                    self.group_table.update()
                
                rows_deleted += len(ids_from_group)

            # Feedback
            if rows_deleted > 0:
                ui.notify(f"Proceso completado. Filas gestionadas.", type='info')
            else:
                ui.notify("No hay filas seleccionadas.", type='warning')


    def clear_main_table(self):
            """Limpia SOLO la tabla principal con logs."""
            logger.info("Solicitud de limpieza: Tabla Principal")
            
            if hasattr(self, 'table'):
                prev_count = len(self.table.rows)
                self.table.rows = []
                self.table.selected = []
                self.table.update()
                logger.info(f"UI Tabla Principal limpiada (tenía {prev_count} filas).")
            else:
                logger.error("No se encontró self.table para limpiar.")
            
            self.processed_data = pd.DataFrame()
            logger.info("DataFrame 'processed_data' reseteado a vacío.")
            ui.notify("Tabla Principal limpiada.", type='positive')


    def clear_group_table(self):
            """Limpia SOLO la tabla de grupos con logs."""
            logger.info("Solicitud de limpieza: Tabla de Grupos")
            
            if hasattr(self, 'group_table'):
                prev_count = len(self.group_table.rows)
                self.group_table.rows = []
                self.group_table.selected = []
                self.group_table.update()
                logger.info(f"UI Tabla de Grupos limpiada (tenía {prev_count} filas).")
            else:
                logger.error("No se encontró self.group_table para limpiar.")
            
            self.grouped_data = pd.DataFrame()
            logger.info("DataFrame 'grouped_data' reseteado a vacío.")
            ui.notify("Tabla de Grupos limpiada.", type='positive')

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

                ui.notify(f"Fila '{new_row['name']}' agregada en la parte superior.", color='positive', position='top')

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
                    ui.notify(f"Fila '{new_row['name']}' clasificada automáticamente en {new_row['system_category']}.", color='positive')
                else:
                    ui.notify(f"ℹFila agregada sin grupo asignado (categoría: {new_row['system_category']}).", color='info')

                # --- Refrescar tabla principal y de grupos ---
                self.display_table()
                self.update_group_table()

            except Exception as ex:
                import traceback
                logger.error(f"Error al agregar nueva fila:\n" + traceback.format_exc())
                ui.notify(f"Error al agregar nueva fila: {ex}", type='negative')

    def download_variable_map(self):
            """Genera y descarga un Excel con el mapa de variables usando un Diálogo Modal."""
            try:
                # 1. Determinar fuente de datos
                df_source = None
                if self.grouped_data is not None and not self.grouped_data.empty:
                    df_source = self.grouped_data
                elif self.processed_data is not None and not self.processed_data.empty:
                    df_source = self.processed_data
                else:
                    ui.notify(" No hay datos para generar el mapa de variables.", type='warning')
                    return

                available_cols = list(df_source.columns)

                # 2. Abrir el Diálogo
                with ui.dialog() as dialog, ui.card().classes('w-96'): # w-96 da un ancho fijo elegante
                    ui.label('Exportar Mapa de Variables').classes('text-h6 font-bold')
                    
                    # Selector dentro del diálogo
                    selected_columns = ui.select(
                        options=available_cols,
                        value=[],  # Puedes poner columnas por defecto aquí si quieres
                        multiple=True,
                        label="Selecciona columnas",
                        with_input=True,
                        clearable=True
                    ).props('outlined dense options-dense use-chips').classes('w-full')

                    # Función interna para procesar la descarga
                    async def confirmar_exportacion():
                        cols = selected_columns.value
                        if not cols:
                            ui.notify(" Selecciona al menos una columna.", type='warning')
                            return

                        # Cerrar el diálogo inmediatamente para limpiar la UI
                        dialog.close()

                        try:
                            df_export = df_source[cols].copy().replace({None: '', pd.NA: ''})
                            
                            # Crear archivo temporal
                            with NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                                with pd.ExcelWriter(tmp.name, engine="openpyxl") as writer:
                                    df_export.to_excel(writer, sheet_name="Mapa", index=False)
                                file_path = tmp.name

                            ui.download(file_path, filename="mapa_variables.xlsx")
                            ui.notify(f"Descargando {len(cols)} columnas...", type='positive')

                            # Limpieza diferida
                            await asyncio.sleep(60)
                            if os.path.exists(file_path):
                                os.remove(file_path)
                                
                        except Exception as e:
                            ui.notify(f"Error en exportación: {str(e)}", type='negative')

                    # Botones de acción del diálogo (Cancelar / Descargar)
                    with ui.row().classes('w-full justify-end mt-4'):
                        ui.button('Cancelar', on_click=dialog.close).props('flat color=grey')
                        ui.button('Descargar Excel', on_click=confirmar_exportacion).props('unelevated color=green icon=download')

                # Importante: Ejecutar la apertura del diálogo
                dialog.open()

            except Exception as ex:
                import traceback
                logger.error(f"Error al abrir diálogo de mapa:\n{traceback.format_exc()}")
                ui.notify(f"Error sistema: {ex}", type='negative')
        

    async def download_errors_excel(self):
            """Descarga un Excel conteniendo únicamente las filas con errores."""
            if self.processed_data is None or self.processed_data.empty:
                ui.notify("No hay datos para procesar", type='warning')
                return

            # Filtrar solo las filas que tienen error (1)
            # Asumiendo que 'error_flag' ya fue calculado en process_file
            if 'error_flag' not in self.processed_data.columns:
                ui.notify("No se han calculado los errores aún.", type='warning')
                return

            df_errors = self.processed_data[self.processed_data['error_flag'] == 1].copy()

            if df_errors.empty:
                ui.notify("¡Genial! No hay errores para descargar. 🎉", type='positive')
                return

            try:
                # Generar archivo temporal
                with NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                    temp_path = tmp.name
                    # Escribir Excel
                    with pd.ExcelWriter(temp_path, engine='openpyxl') as writer:
                        df_errors.to_excel(writer, index=False, sheet_name='Errores')
                
                # Descargar
                ui.download(temp_path, filename="Reporte_Errores.xlsx")
                ui.notify(f"Descargando {len(df_errors)} errores...", type='negative')

                # Limpieza del archivo temporal después de unos segundos
                await asyncio.sleep(10)
                if os.path.exists(temp_path):
                    os.remove(temp_path)

            except Exception as e:
                logger.error(f"Error descargando errores: {e}")
                ui.notify(f"Error al generar el Excel: {str(e)}", type='negative')

    
    async def save_all_changes(self):
        # 1. Crear el diálogo de carga
        with ui.dialog().props('persistent') as loading_dialog:
            with ui.card().classes('items-center'):
                ui.spinner(size='lg')
                ui.label('Guardando cambios...')

        loading_dialog.open()
        
        try:
            # 2. Preparamos los datos necesarios para no pasar objetos complejos de UI al hilo secundario
            # Solo pasamos los diccionarios de las filas y los DataFrames
            rows_data = [dict(row) for row in self.table.rows]
            processed_df = self.processed_data.copy()
            grouped_df = self.grouped_data.copy() if self.grouped_data is not None else None
            only_errors = getattr(self, 'filter_errors_active', False)

            # 3. EJECUCIÓN EN SEGUNDO PLANO (CPU BOUND)
            # Esto evita que la interfaz se congele y se pierda la conexión
            result = await run.cpu_bound(
                self._heavy_processing_logic, 
                rows_data, processed_df, grouped_df, only_errors
            )

            # 4. Recuperar los resultados
            updated_processed_df, updated_grouped_df, saved_count = result
            
            # Actualizar el estado de la clase
            self.processed_data = updated_processed_df
            if updated_grouped_df is not None:
                self.grouped_data = updated_grouped_df

            # 5. Actualizar la UI (esto ya es rápido)
            if saved_count > 0:
                self.update_error_counter()
                self.refresh_table_view()
                self.update_group_table()
                ui.notify(f"Éxito: {saved_count} filas actualizadas.", type='positive')
            else:
                ui.notify("No se detectaron cambios válidos.", type='warning')

        except Exception as e:
            logger.error(f"Error crítico: {e}")
            # Solo intentamos notificar si el cliente sigue vivo
            try:
                ui.notify(f"Error al guardar: {e}", type='negative')
            except:
                pass
        finally:
            # Cerramos el diálogo de forma segura
            try:
                loading_dialog.close()
            except:
                pass


    @staticmethod
    def _heavy_processing_logic(rows, df_main, df_group, only_errors):
        import re
        # El mismo patrón que usas en tu re.sub
        regex_pattern = re.compile(r'^[a-zA-Z0-9\s\.,;:_\-/=%°CñÑáéíóúÁÉÍÓÚ()]*$')
        saved_count = 0
        
        # 1. Preparación de índices
        df_main['id'] = df_main['id'].astype(str)
        df_main = df_main.set_index('id')
        if df_group is not None:
            df_group['id'] = df_group['id'].astype(str)
            df_group = df_group.set_index('id')

        valid_db_columns = set(df_main.columns) - {'error_flag'}

        def clean_val(v):
            if v is None or (isinstance(v, float) and pd.isna(v)): return ""
            try:
                f_val = float(v)
                if f_val.is_integer(): return str(int(f_val))
                return str(f_val)
            except: return str(v).strip()

        for row in rows:
            row_id = str(row.get('id'))
            if row_id not in df_main.index:
                continue

            row_was_changed = False
            
            # --- PROCESAMIENTO DE COLUMNAS ---
            for field in [k for k in row.keys() if k in valid_db_columns]:
                new_val = clean_val(row.get(field))
                old_val = clean_val(df_main.at[row_id, field])

                if new_val != old_val:
                    df_main.at[row_id, field] = new_val
                    row_was_changed = True
                    if df_group is not None and row_id in df_group.index:
                        if field in df_group.columns:
                            df_group.at[row_id, field] = new_val

            # --- LÓGICA DE ERROR (Específica para 'description') ---
            # Obtenemos la descripción actual (ya actualizada arriba)
            desc = df_main.at[row_id, 'description']
            
            # Replicamos exactamente tu validate_description_e:
            is_error = False
            
            if not desc: # Caso None o vacío ""
                is_error = True
            elif not regex_pattern.match(desc): # Caracteres no permitidos
                is_error = True
            elif len(desc) > 60: # Límite suave/duro (según tu código > 60 ya es error)
                is_error = True
            
            new_flag = 1 if is_error else 0
            old_flag = int(df_main.at[row_id, 'error_flag'])

            if new_flag != old_flag:
                df_main.at[row_id, 'error_flag'] = new_flag
                row_was_changed = True
                if df_group is not None and row_id in df_group.index:
                    df_group.at[row_id, 'error_flag'] = new_flag

            if row_was_changed:
                saved_count += 1

        return df_main.reset_index(), (df_group.reset_index() if df_group is not None else None), saved_count
    
    def refresh_table_view(self):
            """Recarga los datos de la tabla según el estado del filtro."""
            df_display = self.processed_data.copy()
            
            if self.error_filter_active:
                # Si el filtro está activo, mostramos solo los que SIGUEN teniendo error
                df_filtered = df_display[df_display['error_flag'] == 1]
                self.table.rows = df_filtered.replace({np.nan: ''}).to_dict('records')
                self.table.update()
                
                # Opcional: Si ya no quedan errores, podrías desactivar el filtro automáticamente
                if df_filtered.empty:
                    ui.notify("¡Felicidades! Has corregido todos los errores.", type='positive')
                    # self.toggle_error_filter() # Descomentar si quieres que vuelva a "Ver Todo" solo
            else:
                # Si no hay filtro, mostramos todo actualizado
                self.table.rows = df_display.replace({np.nan: ''}).to_dict('records')
                self.table.update()

    def refresh_filter_options(self):
        """Extrae las categorías únicas del DataFrame procesado y actualiza el select."""
        if self.processed_data is not None and not self.processed_data.empty:
            # Obtener valores únicos, eliminar nulos y ordenar alfabéticamente
            unique_cats = sorted([
                str(cat) for cat in self.processed_data['system_category'].unique() 
                if pd.notna(cat) and str(cat).strip() != ""
            ])
            
            # Actualizar el componente UI
            self.category_filter.options = unique_cats
            self.category_filter.update()
            logging.info(f"Filtros actualizados con: {unique_cats}")    
