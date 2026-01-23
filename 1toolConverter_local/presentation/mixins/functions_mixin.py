import pandas as pd
import numpy as np
import re
import os
import asyncio
from tempfile import NamedTemporaryFile
import logging
from backend import validate_description_text 

from presentation import ui

logger = logging.getLogger(__name__)

class FunctionMixin:
    
    def validate_description_e(self, texto):
            if texto is None:
                return "El texto está vacío"
            
            # 1. Limpiar caracteres no válidos y comparar
            cleaned = re.sub(r"[^a-zA-Z0-9\s\.,;:_\-/=%°CñÑáéíóúÁÉÍÓÚ()]", "", texto)
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
            ROW_KEY = 'name' # ⚠️ Asegúrate que este sea tu identificador único (ej. 'name', 'register')
            
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
                # Capturamos IDs seleccionados explícitamente en el grupo
                ids_from_group = {row.get(ROW_KEY) for row in self.group_table.selected if row.get(ROW_KEY)}

            # --- 3. SINCRONIZACIÓN FINAL ---
            # Unimos: (IDs borrados en Main porque deben borrarse abajo) + (IDs borrados manualmente en Grupo)
            all_ids_to_remove_from_group = ids_from_main.union(ids_from_group)

            if all_ids_to_remove_from_group:
                # A. Borrar de Group Data
                if self.grouped_data is not None and not self.grouped_data.empty:
                    initial_len = len(self.grouped_data)
                    self.grouped_data = self.grouped_data[~self.grouped_data[ROW_KEY].isin(all_ids_to_remove_from_group)]
                    
                    # Log para verificar que solo se borró en grupo lo que debía
                    logger.info(f"Group: Se eliminaron {initial_len - len(self.grouped_data)} filas.")

                # B. Borrar de Group UI
                if hasattr(self, 'group_table'):
                    self.group_table.rows = [r for r in self.group_table.rows if r.get(ROW_KEY) not in all_ids_to_remove_from_group]
                    self.group_table.selected = []
                    self.group_table.update()
                
                rows_deleted += len(ids_from_group)

            # Feedback
            if rows_deleted > 0:
                ui.notify(f"🗑️ Proceso completado. Filas gestionadas.", type='info')
            else:
                ui.notify("⚠️ No hay filas seleccionadas.", type='warning')


    def clear_main_table(self):
            """Limpia SOLO la tabla principal con logs."""
            logger.info("🧹 Solicitud de limpieza: Tabla Principal")
            
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
            ui.notify("🧹 Tabla Principal limpiada.", type='positive')


    def clear_group_table(self):
            """Limpia SOLO la tabla de grupos con logs."""
            logger.info("🧹 Solicitud de limpieza: Tabla de Grupos")
            
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
            ui.notify("🧹 Tabla de Grupos limpiada.", type='positive')

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
            """Genera y descarga un Excel con el mapa de variables usando un Diálogo Modal."""
            try:
                # 1. Determinar fuente de datos
                df_source = None
                if self.grouped_data is not None and not self.grouped_data.empty:
                    df_source = self.grouped_data
                elif self.processed_data is not None and not self.processed_data.empty:
                    df_source = self.processed_data
                else:
                    ui.notify("⚠️ No hay datos para generar el mapa de variables.", type='warning')
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
                            ui.notify("⚠️ Selecciona al menos una columna.", type='warning')
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
                            ui.notify(f"🚀 Descargando {len(cols)} columnas...", type='positive')

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
                logger.error(f"❌ Error al abrir diálogo de mapa:\n{traceback.format_exc()}")
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