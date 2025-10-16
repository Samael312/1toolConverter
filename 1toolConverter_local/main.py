import pandas as pd
import numpy as np
from pathlib import Path
from typing import List

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

def load_and_preprocess_html(file_path: str) -> pd.DataFrame | None:
    """Lee el HTML, combina tablas y aplica preprocesamiento."""
    input_file = Path(file_path)
    if not input_file.exists():
        print(f"Error: Archivo no encontrado en {file_path}")
        return None

    try:
        list_of_dataframes: List[pd.DataFrame] = pd.read_html(str(input_file), header=0, flavor='bs4')
    except ValueError:
        print("Error: No se encontraron tablas en el HTML")
        return None

    # Ignoramos la primera tabla si no contiene datos de variables
    dataframes_to_export = list_of_dataframes[1:]  
    if not dataframes_to_export:
        print("No hay tablas para exportar")
        return None

    processed_dfs = []
    for df in dataframes_to_export:
        df.columns = df.columns.astype(str).str.strip()
        if not str(df.iloc[0, 0]).strip().isdigit():
            df = df.iloc[1:].copy()
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

        access_col_name = None
        for name in ['Read/Write', 'Direction']:
            if name in df.columns:
                access_col_name = name
                break

        mapping = COLUMN_MAPPING.copy()
        if access_col_name:
            mapping[access_col_name] = 'access_type'
        df.rename(columns=mapping, inplace=True, errors='ignore')

        df['sampling'] = np.nan
        df['read'] = 0
        df['write'] = 0

        if 'access_type' in df.columns:
            access = df['access_type'].astype(str).str.upper().str.strip()
            df.loc[access.str.contains('R'), 'read'] = 4
            df.loc[access.str.contains('W'), 'write'] = 4
            df.drop(columns=['access_type'], inplace=True, errors='ignore')

        if 'system_category' in df.columns:
            df['system_category'] = df['system_category'].astype(str).str.upper().str.strip()

        if 'category' in df.columns:
            df['category'] = df['category'].astype(str).str.upper().str.strip()
            df.loc[df['category'] == 'ALARMS', 'system_category'] = 'ALARM'
        if 'name' in df.columns:
            df.loc[df['name'].astype(str).str.contains('Al', na=False), 'system_category'] = "ALARM"

        processed_dfs.append(df)

    if not processed_dfs:
        return None

    final_df = pd.concat(processed_dfs, ignore_index=True)

    # Post-procesamiento
    final_df["id"] = range(1, len(final_df)+1)
    final_df["view"] = "simple"
    final_df["sampling"].fillna(60, inplace=True)
    final_df.loc[final_df['system_category'] == 'ALARM', 'sampling'] = 30

    # Inicializar columnas faltantes
    for col in LIBRARY_COLUMNS:
        if col not in final_df.columns:
            final_df[col] = np.nan

    final_df["addition"] = 0
    final_df["mask"] = 0
    final_df["value"] = 0
    final_df["alarm"] = """ {"severity":"none"} """
    final_df["metadata"] = "[]"
    final_df["l10n"] = '{"_type":"l10n","default_lang":"en_US","translations":{"en_US":{"name":null,"_type":"languages","description":null}}}'
    final_df["tags"] = "[]"
    final_df["type"] = "modbus"

    # Reordenar
    final_df = final_df.reindex(columns=LIBRARY_COLUMNS, fill_value=np.nan)

    # Solo columnas clave para la UI
    return final_df.loc[:, ['id', 'register', 'name', 'description', 'system_category', 'read', 'write', 'sampling', 'minvalue', 'maxvalue', 'offset', 'unit']]

def export_to_excel(df: pd.DataFrame, output_path: str):
    """Exporta el DataFrame a Excel."""
    output_file = Path(output_path)
    try:
        df_full = df.reindex(columns=LIBRARY_COLUMNS, fill_value=np.nan)
        with pd.ExcelWriter(output_file, engine='openpyxl', mode='w') as writer:
            df_full.to_excel(writer, sheet_name="Parametros_Unificados", index=False)
        return output_file
    except Exception as e:
        print(f"Error al escribir Excel: {e}")
        return None
