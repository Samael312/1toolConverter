"""
Aplicación Conversor HTML a Excel
Punto de entrada principal y lógica de negocio.
"""
from io import BytesIO
from typing import List, Optional
import pandas as pd
import numpy as np
from nicegui import ui
import logging

# Importar la capa de presentación
from presentation.ui import HTMLConverterUI

# =====================================================
# CONFIGURACIÓN
# =====================================================

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =====================================================
# CONSTANTES DE NEGOCIO
# =====================================================

LIBRARY_COLUMNS = [
    "id", "register", "name", "description", "system_category", "category", "view",
    "sampling", "read", "write", "minvalue", "maxvalue", "unit", "offset",
    "addition", "mask", "value", "length", "general_icon", "alarm", "metadata",
    "l10n", "tags", "type", "parameter_write_byte_position", "mqtt", "json",
    "current_value", "current_error_status", "notes"
]

COLUMN_MAPPING = {
    'BMS Address': 'register',
    'Variable name': 'name',
    'Description': 'description',
    'Min': 'minvalue',
    'Max': 'maxvalue',
    'Category': 'category',
    'UOM': 'unit',
    'Bms_Ofs': 'offset',
    'Bms_Type': 'system_category',
}


# =====================================================
# LÓGICA DE NEGOCIO
# =====================================================

def process_html(html_content: bytes) -> Optional[pd.DataFrame]:
    """
    Procesa un archivo HTML y extrae tablas de parámetros.
    
    Args:
        html_content: Contenido del archivo HTML en bytes
        
    Returns:
        DataFrame con los parámetros procesados o None si hay error
    """
    logger.info("Iniciando análisis HTML")
    html_io = BytesIO(html_content)
    
    # Parsear HTML y extraer tablas
    try:
        list_of_dataframes: List[pd.DataFrame] = pd.read_html(
            html_io,
            header=0,
            flavor='bs4'
        )
        logger.info(f"Se encontraron {len(list_of_dataframes)} tablas en el HTML")
    except Exception as e:
        logger.error(f"Error al parsear HTML: {e}", exc_info=True)
        ui.notify(f"Error al procesar el archivo HTML: {e}", type='negative')
        return None
    
    # Validar número de tablas
    if not list_of_dataframes or len(list_of_dataframes) < 2:
        logger.warning(
            f"Número insuficiente de tablas: "
            f"{len(list_of_dataframes) if list_of_dataframes else 0}"
        )
        ui.notify("No se encontraron tablas válidas para exportar.", type='warning')
        return None
    
    # Procesar cada tabla
    processed_dfs = []
    try:
        for df in list_of_dataframes[1:]:
            processed_df = _process_dataframe(df)
            processed_dfs.append(processed_df)
        
        # Combinar todas las tablas procesadas
        final_df = pd.concat(processed_dfs, ignore_index=True)
        final_df["id"] = range(1, len(final_df) + 1)
        final_df["view"] = "simple"
        
        # Agregar columnas con valores por defecto
        final_df = _add_default_columns(final_df)
        
        # Reordenar columnas según la estructura de la librería
        result_df = final_df.reindex(columns=LIBRARY_COLUMNS)
        
        logger.info(
            f"Procesamiento HTML completado: "
            f"{len(result_df)} filas, {len(result_df.columns)} columnas"
        )
        return result_df
        
    except Exception as e:
        logger.error(f"Error durante el procesamiento de tablas: {e}", exc_info=True)
        ui.notify(f"Error durante el procesamiento: {e}", type='negative')
        return None


def _process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Procesa un DataFrame individual aplicando transformaciones y mapeos.
    
    Args:
        df: DataFrame a procesar
        
    Returns:
        DataFrame procesado
    """
    # Limpiar nombres de columnas
    df.columns = df.columns.astype(str).str.strip()
    
    # Eliminar fila de encabezado duplicada si existe
    if not df.empty and not str(df.iloc[0, 0]).strip().isdigit():
        df = df.iloc[1:].copy()
    
    # Eliminar columnas sin nombre
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    
    # Mapear nombres de columnas
    df = _apply_column_mapping(df)
    
    # Procesar permisos de lectura/escritura
    df = _process_access_permissions(df)
    
    # Procesar columnas específicas
    df = _process_specific_columns(df)
    
    # Determinar longitud de datos
    df = _determine_data_length(df)
    
    return df


def _apply_column_mapping(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica el mapeo de nombres de columnas."""
    access_col_name = next(
        (n for n in ['Read/Write', 'Direction'] if n in df.columns),
        None
    )
    
    current_mapping = COLUMN_MAPPING.copy()
    if access_col_name:
        current_mapping[access_col_name] = 'access_type'
    
    df.rename(columns=current_mapping, inplace=True, errors='ignore')
    return df


def _process_access_permissions(df: pd.DataFrame) -> pd.DataFrame:
    """Procesa los permisos de lectura/escritura."""
    if 'access_type' in df.columns:
        df['read'] = np.where(
            df['access_type'].astype(str).str.contains('R', case=False),
            4, 0
        )
        df['write'] = np.where(
            df['access_type'].astype(str).str.contains('W', case=False),
            4, 0
        )
        df.drop(columns=['access_type'], inplace=True, errors='ignore')
    else:
        df['read'], df['write'] = 0, 0
    
    return df


def _process_specific_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Procesa columnas específicas con transformaciones especiales."""
    # Procesar offset
    if 'offset' in df.columns:
        df['offset'] = pd.to_numeric(
            df['offset'].astype(str).str.strip()
            .replace(['', '---', 'nan'], np.nan),
            errors='coerce'
        ).fillna(0.0)
    
    # Procesar unidad
    if 'unit' in df.columns:
        df['unit'] = df['unit'].astype(str).str.strip() \
            .replace(['0', '---', None], np.nan).fillna(' ')
    
    # Procesar categoría
    if 'category' in df.columns:
        df['category'] = df['category'].astype(str).str.upper().str.strip()
        df.loc[df['category'] == 'ALARMS', 'system_category'] = 'ALARM'
    
    # Procesar system_category con condiciones específicas
    if 'system_category' in df.columns:
        df['system_category'] = df['system_category'].astype(str).str.upper().str.strip()
        
        conditions = {
            'ANALOG': {'read': 3, 'write': 16, 'sampling': 60},
            'INTEGER': {'read': 3, 'write': 16, 'sampling': 60},
            'DIGITAL': {'read': 1, 'write': 5, 'sampling': 60},
            'ALARM': {'read': 4, 'write': 0, 'sampling': 30},
        }
        
        for key, vals in conditions.items():
            for col, val in vals.items():
                df.loc[df['system_category'] == key, col] = val
    
    # Procesar valores mín/máx
    for col in ['minvalue', 'maxvalue']:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.strip()
                .replace(['', '---', 'nan'], np.nan),
                errors='coerce'
            )
    
    return df


def _determine_data_length(df: pd.DataFrame) -> pd.DataFrame:
    """Determina la longitud de datos basándose en los valores mín/máx."""
    df['length'] = '16bit'
    
    if 'minvalue' in df.columns and 'maxvalue' in df.columns:
        df.loc[
            (df['minvalue'] < 0) | (df['maxvalue'] < 0),
            'length'
        ] = 's16'
    
    return df


def _add_default_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega columnas con valores por defecto."""
    defaults = {
        "addition": 0,
        "mask": 0,
        "value": 0,
        "alarm": """ {"severity":"none"} """,
        "metadata": "[]",
        "l10n": '{"_type":"l10n","default_lang":"en_US","translations":{"en_US":{"name":null,"_type":"languages","description":null}}}',
        "tags": "[]",
        "type": "modbus",
    }
    
    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val
    
    return df


# =====================================================
# PUNTO DE ENTRADA
# =====================================================

def main():
    """
    Función principal que inicializa la aplicación.
    Separa la lógica de negocio de la presentación.
    """
    logger.info("Inicializando aplicación")
    
    # Crear el controlador de UI pasándole la lógica de negocio
    ui_controller = HTMLConverterUI(process_html_callback=process_html)
    
    # Crear la interfaz de usuario
    ui_controller.create_ui()
    
    logger.info("Aplicación iniciada correctamente")


# Inicializar la aplicación
main()


if __name__ in {'__main__', '__mp_main__'}:
    ui.run(title="Conversor HTML a Excel", reload=True)
