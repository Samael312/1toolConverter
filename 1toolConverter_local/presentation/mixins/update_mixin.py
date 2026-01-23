import pandas as pd
import numpy as np
import re
import os
from tempfile import NamedTemporaryFile
import logging
import asyncio

from presentation import ui

logger = logging.getLogger(__name__)

class UpdateMixin:

    def update_error_counter(self):
            """
            Actualiza el botón de contador calculando directamente desde el DataFrame.
            """
            # 1. Protección: Si no hay datos, es 0
            if self.processed_data is None or self.processed_data.empty:
                error_count = 0
            else:
                # 2. Contar directo en Pandas (Más rápido y seguro)
                
                if 'error_flag' in self.processed_data.columns:
                
                    error_count = len(self.processed_data[self.processed_data['error_flag'] == 1])
                    
                else:
                    error_count = 0

            # 3. Actualizar Botón de Descarga
            if error_count > 0:
                if hasattr(self, 'download_button'):
                    self.download_button.disable()
                    self.download_button.tooltip('Corrige los errores antes de descargar')
            else:
                if hasattr(self, 'download_button'):
                    self.download_button.enable()
                    self.download_button.tooltip('Descargar archivo procesado')
            
            # 4. Actualizar Texto del Botón de Errores
            if hasattr(self, "error_button"):
                self.error_button.text = f"Errores: {error_count}"

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