"""
Aplicación Conversor Universal (Keyter / iPro)
Punto de entrada principal y lógica de negocio.
"""
from nicegui import ui, run, app
import os
import logging
import asyncio
from backend.Keyter.KeyterNew import process_excel as keyter_new_process
from backend.Keyter.Keyter import process_html as keyter_html_process
from backend.iPro.ipro import convert_excel_to_dataframe as ipro_convert_excel
from backend.Cefa.cefa import process_pdf as cefa_process_pdf
from backend.Dixell.dixell2 import process_multiple_pdfs as dixell_process_pdf
from presentation.ui import HTMLConverterUI

# =====================================================
# CONFIGURACIÓN
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

icon_dir = os.path.join(BASE_DIR, 'presentation', 'components', 'icon')

# =====================================================
# FUNCIÓN UNIFICADA DE PROCESAMIENTO
# =====================================================

# 2. Convertimos esta función a ASYNC
async def unified_process_file(mode: str, filename, file_bytes):
    """
    Ejecuta el backend correspondiente en un hilo separado para no congelar la UI.
    """
    try:
        if mode == "Dixell":
            logger.info(f"Procesando {len(file_bytes)} archivos PDF con backend Dixell")
            # 3. Usamos await run.io_bound para ejecutar en segundo plano
            return await run.io_bound(dixell_process_pdf, file_bytes)

        # Para otros backends
        ext = os.path.splitext(filename)[1].lower()
        if mode == "Keyter":
            logger.info("Procesando archivo HTML/Excel con backend Keyter")
            if ext in [".html", ".htm"]:
                return await run.io_bound(keyter_html_process, file_bytes)
            elif ext in [".xls", ".xlsx", ".xlsm"]:
                return await run.io_bound(keyter_new_process, file_bytes)

        elif mode == "iPro":
            logger.info("Procesando archivo Excel con backend iPro")
            return await run.io_bound(ipro_convert_excel, file_bytes)
        
        elif mode == "Cefa":
            logger.info("Procesando archivo PDF con backend Cefa")
            return await run.io_bound(cefa_process_pdf, file_bytes)
        
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

    if os.path.exists(icon_dir):
        app.add_static_files('/logo', icon_dir)
        logger.info(f"Icon montado en: {icon_dir}")
    else:
        logger.warning(f"NO se encontró icon: {icon_dir}")
        pass

    async def process_with_backend(file_bytes):
        backend = ui_controller.backend_selected
        
        if not backend:
            ui.notify("Selecciona un backend antes de procesar el archivo.", type="warning")
            return None

        # 1. CREAMOS EL DIÁLOGO DE CARGA
        # Esto crea una ventana modal que no se cierra haciendo clic fuera
        with ui.dialog() as loading_dialog, ui.card().classes('items-center'):
            ui.spinner(size='lg', type='dots') # Puedes usar 'dots', 'box', 'audio', etc.
            ui.label(f'Procesando con {backend}...').classes('text-lg mt-2')
            ui.label('Por favor no cierres la ventana').classes('text-sm text-gray-500')
        
        # Abrimos el diálogo
        loading_dialog.open()
        
        await asyncio.sleep(0.2)  

        result = None
        
        try:
            # 2. PROCESAMIENTO (Dentro de un try para capturar errores)
            
            # Para backends de un solo archivo
            if backend in ["Keyter", "iPro", "Cefa"]:
                filename = ui_controller.uploaded_file_names[-1] if ui_controller.uploaded_file_names else "desconocido"
                result = await unified_process_file(backend, filename, file_bytes)

            # Para Dixell (múltiples archivos)
            elif backend == "Dixell":
                filenames = ui_controller.uploaded_file_names
                result = await unified_process_file(backend, filenames, file_bytes)

            else:
                ui.notify("Backend no reconocido", type="warning")

        except Exception as e:
            logger.error(f"Error crítico en la UI: {e}")
            ui.notify("Ocurrió un error inesperado.", type='negative')
            
        finally:
            # 3. CERRAR EL LOADING (Siempre se ejecuta, haya error o no)
            loading_dialog.close()
            
            if result is not None:
                ui.notify('¡Proceso terminado con éxito!', type='positive')
        
        return result

    # Crear interfaz con el callback adaptado
    ui_controller = HTMLConverterUI(process_html_callback=process_with_backend)
    ui_controller.create_ui()

    logger.info("Interfaz creada correctamente.")


# =====================================================
# EJECUCIÓN DE LA APLICACIÓN
# =====================================================

main()  # Crea la interfaz

if __name__ in {'__main__', '__mp_main__'}:
    favicon_path = os.path.join(icon_dir, 'ki_fav.png')
    ui.run(
        title="kiCreator - Creador de librerias", 
        reload=True,
        favicon=favicon_path,
        port=8080)