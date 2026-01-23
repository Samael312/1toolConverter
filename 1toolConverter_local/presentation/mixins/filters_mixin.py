import pandas as pd
import numpy as np
import logging
from nicegui import ui

logger = logging.getLogger(__name__)

class FilterMixin:
    """
    Maneja exclusivamente el filtrado visual de las tablas.
    No realiza cálculos lógicos pesados sobre los datos.
    """

    def toggle_error_filter(self, e=None):
        """Activa/desactiva el filtro visual de errores."""
        # 1. Protección inicial
        if self.processed_data is None or self.processed_data.empty:
            ui.notify("No hay datos para filtrar", type='warning')
            return

        self.error_filter_active = not self.error_filter_active

        # 2. Obtener datos base (Fuente de la verdad)
        # Asumimos que 'error_flag' YA FUE CALCULADO en process_file (backend/logic.py)
        df_display = self.processed_data.copy()

        # Validación de seguridad: si por alguna razón no existe la columna
        if 'error_flag' not in df_display.columns:
             ui.notify("Los errores no han sido calculados aún.", type='warning')
             self.error_filter_active = False
             return

        if self.error_filter_active:
            # 🔥 CASO ACTIVO: Filtramos usando Pandas (es más rápido que iterar listas)
            df_filtered = df_display[df_display['error_flag'] == 1]
            rows_to_show = df_filtered.replace({np.nan: ''}).to_dict('records')
            
            # Estética UI
            if hasattr(self, 'error_button'):
                self.error_button.props("color=positive icon=filter_alt_off")
                self.error_button.text = 'Ver Todo'
            
            ui.notify(f"🔴 Filtro activado: {len(rows_to_show)} errores visibles.", type='warning')

        else:
            # 📋 CASO INACTIVO: Mostramos todo
            rows_to_show = df_display.replace({np.nan: ''}).to_dict('records')

            # Estética UI
            if hasattr(self, 'error_button'):
                self.error_button.props("color=negative outline icon=filter_alt")
                self.error_button.text = 'Filtrar Errores'
            
            ui.notify("Mostrando todos los registros.", type='info')

        # 3. Actualizamos UI final
        self.table.rows = rows_to_show
        self.table.selected = [] # Limpiar selección para evitar errores
        self.table.update()
        
        # Actualizamos el contador (método de UpdateMixin)
        if hasattr(self, 'update_error_counter'):
            self.update_error_counter()

    def apply_search_filter(self, e):
        """Filtra la tabla principal usando 'contains' en lugar de 'startswith'."""
        try:
            if self.processed_data is None or self.processed_data.empty:
                return

            column = self.search_column_selector.value
            query = (e.value or '').strip().lower()

            if not column or column not in self.processed_data.columns:
                return # No notificamos para no molestar mientras escriben

            if not query:
                filtered = self.processed_data
            else:
                # MEJORA: Usamos 'contains' para búsqueda parcial
                filtered = self.processed_data[
                    self.processed_data[column].astype(str).str.lower().str.contains(query, na=False)
                ]

            self.table.rows = filtered.replace({np.nan: ''}).to_dict('records')
            self.table.update()

        except Exception as ex:
            logger.exception(f"Error filtro búsqueda: {ex}")

    def apply_category_filter(self, e):
        """Filtra la tabla principal por categorías."""
        try:
            if self.processed_data is None or self.processed_data.empty:
                return

            selected_categories = e.value or []

            if not selected_categories:
                filtered = self.processed_data
            else:
                filtered = self.processed_data[
                    self.processed_data['system_category'].isin(selected_categories)
                ]

            self.table.rows = filtered.replace({np.nan: ''}).to_dict('records')
            self.table.update()
            
            # Feedback visual útil pero no intrusivo
            ui.notify(f"Filtrado: {len(filtered)} filas", position='bottom-right', type='info', timeout=1000)

        except Exception as ex:
            logger.error(f"Error filtro categoría: {ex}")

    def apply_group_search_filter(self, e):
        """Filtra la tabla de grupos."""
        try:
            if self.grouped_data is None or self.grouped_data.empty:
                return

            column = self.group_search_column_selector.value
            query = (e.value or '').strip().lower()

            if not column or column not in self.grouped_data.columns:
                return

            if not query:
                filtered = self.grouped_data
            else:
                filtered = self.grouped_data[
                    self.grouped_data[column].astype(str).str.lower().str.contains(query, na=False)
                ]

            self.group_table.rows = filtered.replace({np.nan: ''}).to_dict('records')
            self.group_table.update()

        except Exception as ex:
            logger.error(f"Error grupo búsqueda: {ex}")

    def apply_group_category_filter(self, e):
        """Filtra la tabla de grupos por categorías."""
        try:
            if self.grouped_data is None or self.grouped_data.empty:
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

        except Exception as ex:
            logger.error(f"Error grupo categoría: {ex}")

    def reset_search_input(self, e):
        """Limpia input y restaura tabla principal."""
        if hasattr(self, 'search_input') and self.search_input:
            self.search_input.value = ''
            

    def reset_group_search_input(self, e):
        """Limpia input y restaura tabla grupos."""
        if hasattr(self, 'group_search_input') and self.group_search_input:
            self.group_search_input.value = ''