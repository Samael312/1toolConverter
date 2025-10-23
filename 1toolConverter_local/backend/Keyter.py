"""
Backend Keyter: procesamiento de archivos HTML a DataFrame.
(No tiene interfaz gráfica; se ejecuta desde main.py)
"""
from io import BytesIO
from typing import List, Optional
import pandas as pd
import numpy as np
import logging

# =====================================================
# CONFIGURACIÓN DE LOGGING
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
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
    "BMS Address": "register",
    "Variable name": "name",
    "Description": "description",
    "Min": "minvalue",
    "Max": "maxvalue",
    "Category": "category",
    "UOM": "unit",
    "Bms_Ofs": "offset",
    "Bms_Type": "system_category",
}

# =====================================================
# FUNCIÓN PRINCIPAL DE PROCESAMIENTO
# =====================================================

def process_html(html_content: bytes) -> Optional[pd.DataFrame]:
    """
    Procesa un archivo HTML y devuelve un DataFrame con formato Keyter.
    No genera UI ni notificaciones.
    """
    logger.info("Procesando archivo HTML con backend Keyter...")
    html_io = BytesIO(html_content)

    try:
        tables: List[pd.DataFrame] = pd.read_html(html_io, header=0, flavor='bs4')
        logger.info(f"Se encontraron {len(tables)} tablas en el HTML.")
    except Exception as e:
        logger.error(f"Error al leer HTML: {e}", exc_info=True)
        return None

    if not tables or len(tables) < 2:
        logger.warning("No se encontraron tablas válidas en el HTML.")
        return None

    try:
        processed_dfs = [_process_dataframe(df) for df in tables[1:]]
        final_df = pd.concat(processed_dfs, ignore_index=True)
        final_df["id"] = range(1, len(final_df) + 1)
        final_df["view"] = "simple"

        final_df = _add_default_columns(final_df)
        result_df = final_df.reindex(columns=LIBRARY_COLUMNS)

        logger.info(f"Procesamiento completado: {len(result_df)} filas.")
        return result_df

    except Exception as e:
        logger.error(f"Error procesando tablas HTML: {e}", exc_info=True)
        return None


# =====================================================
# FUNCIONES AUXILIARES
# =====================================================

def _process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.astype(str).str.strip()
    if not df.empty and not str(df.iloc[0, 0]).strip().isdigit():
        df = df.iloc[1:].copy()

    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    df = _apply_column_mapping(df)
    df = _process_access_permissions(df)
    df = _process_specific_columns(df)
    df = _determine_data_length(df)
    df = _apply_deep_classification(df)
    df = _apply_sampling_rules(df)
    return df


def _apply_column_mapping(df: pd.DataFrame) -> pd.DataFrame:
    access_col_name = next((n for n in ['Read/Write', 'Direction'] if n in df.columns), None)
    mapping = COLUMN_MAPPING.copy()
    if access_col_name:
        mapping[access_col_name] = 'access_type'
    df.rename(columns=mapping, inplace=True, errors='ignore')
    return df


def _process_access_permissions(df: pd.DataFrame) -> pd.DataFrame:
    df['read'] = 0
    df['write'] = 0
    if 'access_type' in df.columns and 'system_category' in df.columns:
        access = df['access_type'].astype(str).str.upper().str.strip()
        system_type = df['system_category'].astype(str).str.upper().str.strip()

        only_read = access == 'R'
        rw = access == 'R/W'

        df.loc[only_read & system_type.isin(['ANALOG', 'INTEGER']), 'read'] = 4
        df.loc[only_read & system_type.isin(['DIGITAL']), 'read'] = 1

        df.loc[rw & system_type.isin(['ANALOG', 'INTEGER']), ['read', 'write']] = [3, 6]
        df.loc[rw & system_type.isin(['DIGITAL']), ['read', 'write']] = [1, 5]

        df.drop(columns=['access_type'], inplace=True, errors='ignore')

    return df


def _process_specific_columns(df: pd.DataFrame) -> pd.DataFrame:
    if 'offset' in df.columns:
        df['offset'] = pd.to_numeric(
            df['offset'].astype(str).replace(['', '---', 'nan'], None),
            errors='coerce'
        ).fillna(0.0)

    if 'unit' in df.columns:
        df['unit'] = df['unit'].astype(str).replace(['0', '---', None], ' ').str.strip()

    if 'category' in df.columns:
        df['category'] = df['category'].astype(str).str.upper().str.strip()
        df.loc[df['category'] == 'ALARMS', 'system_category'] = 'ALARM'

    if 'name' in df.columns:
        alarms = df['name'].astype(str).str.contains('Al', na=False)
        df.loc[alarms, 'system_category'] = "ALARM"

    for col in ['minvalue', 'maxvalue']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def _determine_data_length(df: pd.DataFrame) -> pd.DataFrame:
    df['length'] = '16bit'
    if 'minvalue' in df.columns and 'maxvalue' in df.columns:
        df.loc[(df['minvalue'] < 0) | (df['maxvalue'] < 0), 'length'] = 's16'
    return df


def _apply_deep_classification(df: pd.DataFrame) -> pd.DataFrame:
    if 'system_category' not in df.columns:
        df['system_category'] = 'STATUS'

    df['system_category'] = df['system_category'].astype(str).str.upper().str.strip()

    is_write = df['write'] > 0
    is_read = df['read'] > 0
    is_alarm = df['system_category'] == 'ALARM'
    is_analog = df['system_category'].isin(['ANALOG', 'ANALOG_INPUT', 'ANALOG_OUTPUT'])
    is_integer = df['system_category'].isin(['INTEGER'])
    is_digital = df['system_category'].isin(['DIGITAL', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT'])

    conditions = [
        is_alarm,
        (is_analog | is_integer) & is_write & is_read,
        (is_analog | is_integer | is_digital) & (is_read & ~is_write),
        is_digital & is_write & is_read,
    ]
    choices = ['ALARM', 'SET_POINT', 'DEFAULT', 'COMMAND']

    df['system_category'] = np.select(conditions, choices, default='STATUS')
    return df


def _apply_sampling_rules(df: pd.DataFrame) -> pd.DataFrame:
    sampling = {
        'ALARM': 30,
        'SET_POINT': 300,
        'DEFAULT': 60,
        'COMMAND': 0,
        'STATUS': 60,
    }
    df['sampling'] = df['system_category'].map(sampling).fillna(60)
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
