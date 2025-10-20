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
    """
    logger.info("Iniciando análisis HTML")
    html_io = BytesIO(html_content)

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

    if not list_of_dataframes or len(list_of_dataframes) < 2:
        ui.notify("No se encontraron tablas válidas para exportar.", type='warning')
        return None

    processed_dfs = []
    try:
        for df in list_of_dataframes[1:]:
            processed_df = _process_dataframe(df)
            processed_dfs.append(processed_df)

        final_df = pd.concat(processed_dfs, ignore_index=True)
        final_df["id"] = range(1, len(final_df) + 1)
        final_df["view"] = "simple"

        final_df = _add_default_columns(final_df)
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
    """Procesa un DataFrame individual aplicando transformaciones y mapeos."""
    df.columns = df.columns.astype(str).str.strip()
    if not df.empty and not str(df.iloc[0, 0]).strip().isdigit():
        df = df.iloc[1:].copy()

    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    df = _apply_column_mapping(df)
    df = _process_access_permissions(df)
    df = _process_specific_columns(df)
    df = _determine_data_length(df)
    df = _apply_deep_classification(df)  # <<--- CLASIFICACIÓN PROFUNDA AÑADIDA
    return df


def _apply_column_mapping(df: pd.DataFrame) -> pd.DataFrame:
    access_col_name = next((n for n in ['Read/Write', 'Direction'] if n in df.columns), None)
    current_mapping = COLUMN_MAPPING.copy()
    if access_col_name:
        current_mapping[access_col_name] = 'access_type'
    df.rename(columns=current_mapping, inplace=True, errors='ignore')
    return df


def _process_access_permissions(df: pd.DataFrame) -> pd.DataFrame:
    if 'access_type' in df.columns:
        df['read'] = np.where(df['access_type'].astype(str).str.contains('R', case=False), 4, 0)
        df['write'] = np.where(df['access_type'].astype(str).str.contains('W', case=False), 4, 0)
        df.drop(columns=['access_type'], inplace=True, errors='ignore')
    else:
        df['read'], df['write'] = 0, 0
    return df


def _process_specific_columns(df: pd.DataFrame) -> pd.DataFrame:
    if 'offset' in df.columns:
        df['offset'] = pd.to_numeric(
            df['offset'].astype(str).str.strip().replace(['', '---', 'nan'], np.nan),
            errors='coerce'
        ).fillna(0.0)

    if 'unit' in df.columns:
        df['unit'] = df['unit'].astype(str).str.strip().replace(['0', '---', None], np.nan).fillna(' ')

    if 'category' in df.columns:
        df['category'] = df['category'].astype(str).str.upper().str.strip()
        df.loc[df['category'] == 'ALARMS', 'system_category'] = 'ALARM'

    if 'system_category' in df.columns:
        df['system_category'] = df['system_category'].astype(str).str.upper().str.strip()
        df.loc[df['system_category'] == '', 'system_category'] = np.nan

    for col in ['minvalue', 'maxvalue']:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.strip().replace(['', '---', 'nan'], np.nan),
                errors='coerce'
            )

    return df


def _determine_data_length(df: pd.DataFrame) -> pd.DataFrame:
    df['length'] = '16bit'
    if 'minvalue' in df.columns and 'maxvalue' in df.columns:
        df.loc[(df['minvalue'] < 0) | (df['maxvalue'] < 0), 'length'] = 's16'
    return df


def _apply_deep_classification(df: pd.DataFrame) -> pd.DataFrame:
    """Clasificación profunda de categorías de sistema."""
    if 'system_category' not in df.columns:
        df['system_category'] = 'STATUS'

    df['system_category'] = df['system_category'].astype(str).str.upper().str.strip()

    is_writeable = df['write'] > 0
    is_readable = df['read'] > 0
    is_read_only = (df['read'] > 0) & (df['write'] == 0)
    is_alarm = df['system_category'] == 'ALARM'

    is_analog = df['system_category'].isin(['ANALOG', 'ANALOG_INPUT', 'ANALOG_OUTPUT'])
    is_integer = df['system_category'].isin(['INTEGER'])
    is_digital = df['system_category'].isin(['DIGITAL', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT'])

    conditions_new_cat = [
        (is_alarm),
        (is_analog) & (is_writeable) & (is_readable),
        (is_integer) & (is_writeable) & (is_readable),
        (is_analog | is_integer | is_digital) & (is_read_only),
        (is_digital) & (is_writeable) & (is_readable),
    ]

    choices_new_cat = [
        'ALARM',
        'SET_POINT',
        'CONFIG_PARAMETER',
        'DEFAULT',
        'COMMAND',
    ]

    df['system_category'] = np.select(conditions_new_cat, choices_new_cat, default='STATUS')
    return df


def _add_default_columns(df: pd.DataFrame) -> pd.DataFrame:
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
    logger.info("Inicializando aplicación")
    ui_controller = HTMLConverterUI(process_html_callback=process_html)
    ui_controller.create_ui()
    logger.info("Aplicación iniciada correctamente")


main()

if __name__ in {'__main__', '__mp_main__'}:
    ui.run(title="Conversor HTML a Excel", reload=True)
