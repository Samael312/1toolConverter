"""
Aplicación Conversor Universal (Keyter / iPro)
Punto de entrada principal y lógica de negocio.
"""
from nicegui import ui
import os
import logging
from backend.Keyter.KeyterNew import process_excel as keyter_new_process
from backend.Keyter.Keyter import process_html as keyter_html_process
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

def unified_process_file(mode: str, filename: str, file_bytes: bytes):
    """
    Ejecuta el backend correspondiente según el modo seleccionado (Keyter o iPro).
    Retorna un DataFrame procesado o None.
    """
    ext = os.path.splitext(filename)[1].lower()
    try:
        if mode == "Keyter":
            logger.info("Procesando archivo HTML/Excel con backend Keyter")
            if ext in [".html", ".htm"]:
                return keyter_html_process(file_bytes)
            elif ext in [".xls", ".xlsx", ".xlsm"]:
                return keyter_new_process(file_bytes)

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

    def process_with_backend(file_bytes):
        backend = ui_controller.backend_selected
        filename = ui_controller.uploaded_file_name or "desconocido"   # ✅ nombre del archivo
        if not backend:
            ui.notify("Selecciona un backend antes de procesar el archivo.", type="warning")
            return None
        return unified_process_file(backend, filename, file_bytes)

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
