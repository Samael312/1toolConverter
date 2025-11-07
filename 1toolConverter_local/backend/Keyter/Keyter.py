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

COLUMN_MAPPING1 = {
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

"""
COLUMN_MAPPING2 = {
    "MODBUS ADRESS CAREL": "register",
    "Name of the variable CAREL": "name",
    "Unit": "Unit",

}
"""

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
    df = _apply_column_mapping1(df)
    df = _process_access_permissions(df)
    df = _process_specific_columns(df)
    df = _determine_data_length(df)
    df = _apply_deep_classification(df)
    df = _apply_sampling_rules(df)
    df = _apply_view_rules(df)
    df = _apply_specific_rules(df)
    return df


def _apply_column_mapping1(df: pd.DataFrame) -> pd.DataFrame:
    access_col_name = next((n for n in ['Read/Write', 'Direction'] if n in df.columns), None)
    mapping = COLUMN_MAPPING1.copy()
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
    
    if 'description' in df.columns:
        df['description'] = df['description'].astype(str).str.slice(0, 60)
    
    if "system_category" in df.columns:
        system_type = df['system_category'].astype(str).str.upper().str.strip()
        df["tags"] = np.where(system_type.isin(["SYSTEM"]), '["library_identifier"]', "[]")
    
    if "name" in df.columns:
        # Eliminar espacios y asegurar tipo string
        df["name"] = df["name"].astype(str).str.strip()
        
        # Contar repeticiones
        duplicates = df.groupby("name").cumcount()
        
        # Agregar sufijo solo a duplicados (primer valor tiene índice 0)
        df["name"] = np.where(
            duplicates == 0,
            df["name"],
            df["name"] + "_" + (duplicates + 1).astype(str)
        )

    return df

def _apply_deep_classification(df: pd.DataFrame) -> pd.DataFrame:
    if 'system_category' not in df.columns:
        df['system_category'] = 'STATUS'

    df['system_category'] = df['system_category'].astype(str).str.upper().str.strip()

    # 1. Definir las máscaras de estado de acceso y tipo
    is_writeable = df['write'] > 0
    is_readable = df['read'] > 0
    is_read_only = (df['read'] > 0) & (df['write'] == 0)
    
    # Nota: is_alarm ya tiene el valor 'ALARM' de la detección por 'name' o 'category'
    is_alarm = df['system_category'] == 'ALARM'

        # Se redefinen is_analog/is_integer/is_digital para excluir ALARM, 
        # ya que ya se manejará en la primera condición.
    is_analog = df['system_category'].isin(['ANALOG', 'ANALOG_INPUT', 'ANALOG_OUTPUT'])
    is_integer = df['system_category'].isin(['INTEGER'])
    is_digital = df['system_category'].isin(['DIGITAL', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT'])

    # 2. Construir la lista de condiciones con la nueva distinción
    conditions = [
        # 0. ALARM (MÁXIMA PRIORIDAD)
        (is_alarm), 
        
        # 1. SET_POINT: Analog y R/W
        (is_analog) & (is_writeable) & (is_readable), 
        
        # 2. CONFIG_PARAMETER: Integer y R/W
        (is_integer) & (is_writeable) & (is_readable),
        
        # 3. DEFAULT: Analog/Integer/Digital R-Only
        (is_analog | is_integer | is_analog) & (is_read_only),
        
        # 4. COMMAND: Digital y R/W
        (is_digital) & (is_writeable) & (is_readable),
        
    ]
            
            # 3. Construir la lista de opciones (debe coincidir con la cantidad de condiciones)
    choices = [
                'ALARM',              # 0. ALARM
                'SET_POINT',          # 1. Analog R/W
                'CONFIG_PARAMETER',   # 2. Integer R/W
                'DEFAULT',            # 3. Analog/Integer R-Only
                'COMMAND',            # 4. Digital R/W (Commands)
            ]


    df['system_category'] = np.select(conditions, choices, default='STATUS')
    
    return df

def _apply_view_rules(df: pd.DataFrame) -> pd.DataFrame:
    # Forzar coherencia si viene de una edición externa
    df.loc[df['system_category'] == 'STATUS', 'view'] = 'basic'
    df.loc[df['system_category'] == 'ALARM', 'view'] = 'simple'

    view ={
        'ALARM': 'simple',
        'SET_POINT': "simple",
        'DEFAULT': "simple",
        'COMMAND': "simple",
        'STATUS': "basic",
        'CONFIG_PARAMETER' : "simple"
    }
    df['view'] = df['system_category'].map(view).fillna('simple')
    return df

def _determine_data_length(df: pd.DataFrame) -> pd.DataFrame:
    # 🔹 Mapeo base por system_category
    category_mapping = {
        'SET_POINT': '16bit/s16',
        'ALARM': '1bit',
        'COMMAND': '1bit',
        'STATUS': '1bit',
        'CONFIG_PARAMETER': '16bit/s16',
        'SYSTEM': '1bit',
        'DEFAULT': '16bit/s16',
    }

    # Inicializamos con None
    df["length"] = None

    if "system_category" in df.columns:
        # Aplicar mapeo base
        df.loc[df["system_category"].isin(category_mapping.keys()), "length"] = df["system_category"].map(category_mapping)

    # 🔧 Ajuste automático para categorías con 16bit/s16 según min/max
    mask_16bit_s16 = df["length"] == "16bit/s16"
    if "minvalue" in df.columns and "maxvalue" in df.columns:
        df.loc[mask_16bit_s16 & ((df["minvalue"] < 0) | (df["maxvalue"] < 0)), "length"] = "s16"
        df.loc[mask_16bit_s16 & ~((df["minvalue"] < 0) | (df["maxvalue"] < 0)), "length"] = "16bit"

    # 🔹 Para las filas que quedaron sin mapeo, aplicar lógica anterior
    mask_none = df["length"].isna()
    if "minvalue" in df.columns and "maxvalue" in df.columns:
        df.loc[mask_none, "length"] = "16bit"
        df.loc[mask_none & ((df["minvalue"] < 0) | (df["maxvalue"] < 0)), "length"] = "s16"

    return df


def _apply_sampling_rules(df: pd.DataFrame) -> pd.DataFrame:
    sampling = {
        'ALARM': 30,
        'SET_POINT': 300,
        'DEFAULT': 0,
        'COMMAND': 0,
        'STATUS': 60,
        'CONFIG_PARAMETER': 0
    }
    df['sampling'] = df['system_category'].map(sampling).fillna(0)
    return df

def _apply_specific_rules(df: pd.DataFrame) -> pd.DataFrame:
    is_readable = df['read'] > 0
    rw = (df['read'] > 0) & (df['write'] > 0)

    if 'system_category' in df.columns:
        system_type = df['system_category'].astype(str).str.upper().str.strip()
        df.loc[is_readable & system_type.isin(['ANALOG_INPUT', 'ANALOG_OUTPUT', 'SYSTEM']), 'read'] = 3
        df.loc[is_readable & system_type.isin(['ALARM']), 'read'] = 1
        df.loc[is_readable & system_type.isin(['STATUS']), 'read'] = 4
        df.loc[is_readable & system_type.isin(['COMMAND']), ['read', 'write']] = [0, 6]
        df.loc[rw & system_type.isin(['SET_POINT']), ['read', 'write']] = [3, 6]
        df.loc[rw & system_type.isin(['CONFIG_PARAMETER', 'DIGITAL_OUTPUT']), ['read', 'write']] = [1, 5]
        df.loc[rw & system_type.isin(['DIGITAL_INPUT']), 'read'] = 1
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

if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Procesa un archivo HTML con tablas de variables y genera un DataFrame formateado para Keyter."
    )
    parser.add_argument(
        "--input", "-i", required=True, help="Ruta al archivo HTML de entrada"
    )
    parser.add_argument(
        "--output", "-o", default="procesado_final.xlsx",
        help="Ruta del archivo Excel de salida"
    )
    parser.add_argument(
        "--preview", "-p", action="store_true",
        help="Muestra las primeras filas del DataFrame final antes de exportar"
    )

    args = parser.parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        logger.error(f"El archivo de entrada no existe: {input_path}")
        sys.exit(1)

    logger.info(f"📘 Leyendo archivo HTML: {input_path}")

    try:
        with open(input_path, "rb") as f:
            html_bytes = f.read()

        df_final = process_html(html_bytes)

        if df_final is None or df_final.empty:
            logger.warning("⚠️ El DataFrame resultante está vacío. No se generará archivo.")
            sys.exit(0)

        if args.preview:
            logger.info("Vista previa del DataFrame final:")
            print(df_final.head(20).to_string(index=False))

        df_final.to_excel(output_path, index=False)
        logger.info(f"✅ Archivo final exportado exitosamente: {output_path.resolve()}")

    except Exception as e:
        logger.error(f"Error general al procesar el archivo: {e}", exc_info=True)
        sys.exit(1)
