"""
Aplicación Conversor Universal (Keyter / iPro)
Punto de entrada principal y lógica de negocio.
"""
from nicegui import ui
import pandas as pd
import tempfile
import os
import logging
from backend.Keyter import process_html as keyter_process_html
from backend.ipro import convert_excel_to_dataframe as ipro_convert_excel
from presentation.ui import HTMLConverterUI

# =====================================================
# CONFIGURACIÓN
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =====================================================
# FUNCIÓN UNIFICADA DE PROCESAMIENTO
# =====================================================

def unified_process_file(mode: str, file_bytes: bytes):
    """
    Ejecuta el backend correspondiente según el modo seleccionado (Keyter o iPro).
    Retorna un DataFrame procesado o None.
    """
    try:
        if mode == "Keyter":
            logger.info("Procesando archivo HTML con backend Keyter")
            return keyter_process_html(file_bytes)

        elif mode == "iPro":
            logger.info("Procesando archivo Excel con backend iPro")
            return ipro_convert_excel(file_bytes)


        else:
            ui.notify("Modo no reconocido", type='warning')
            return None

    except Exception as e:
        logger.exception("Error en unified_process_file:")
        ui.notify(f"Error procesando el archivo: {e}", type='negative')
        return None


# =====================================================
# FUNCIÓN PRINCIPAL
# =====================================================

def main():
    """Inicializa la interfaz y conecta el procesamiento al backend elegido."""
    logger.info("Inicializando interfaz Conversor Universal...")

    # Callback que inyecta el backend seleccionado desde la UI
    def process_with_backend(file_bytes):
        backend = ui_controller.backend_selected
        if not backend:
            ui.notify("Selecciona un backend antes de procesar el archivo.", type="warning")
            return None
        return unified_process_file(backend, file_bytes)

    # Crear interfaz con el callback adaptado
    ui_controller = HTMLConverterUI(process_html_callback=process_with_backend)
    ui_controller.create_ui()

    logger.info("Interfaz creada correctamente.")


# =====================================================
# EJECUCIÓN DE LA APLICACIÓN
# =====================================================

main()  # Crea la interfaz

if __name__ in {'__main__', '__mp_main__'}:
    ui.run(title="Conversor Universal - Keyter / iPro", reload=True)
