# Author Kiconex - Samuel Ali 
# Description  Conversion of data table format of variables from Excel to processed Excel using pandas.
# Version  2.3
# Name  1tools - Convert Data Table Format (Excel Version)
# Type  Application

import sys
from pathlib import Path
from typing import List
import pandas as pd
import numpy as np
import re

LIBRARY_COLUMNS = [
    "id", "register", "name", "description", "system_category", "category", "view",
    "sampling", "read", "write", "minvalue", "maxvalue", "unit", "offset",
    "addition", "mask", "value", "length", "general_icon", "alarm", "metadata",
    "l10n", "tags", "type", "parameter_write_byte_position", "mqtt", "json",
    "current_value", "current_error_status", "notes"
]

COLUMN_MAPPING = {
    'Name': 'name',
    'Address': 'register',
    'Dimension': 'dimension',
    'Comment': 'description',
    'Wiring': 'category',
    'String Size': 'length',
    'Attribute': 'attribute'  # Columna para determinar read/write
}


def extract_min_max_from_dimension(value: str):
    """
    Extrae valores mínimo y máximo de un texto como '[1...23]', '[1-23]', '1...23', '1-23'
    Retorna (min, max) o (NaN, NaN) si no se puede extraer.
    """
    if not isinstance(value, str):
        return np.nan, np.nan

    value = value.strip()

    # Buscar formatos comunes: [1...23], [1..23], [1-23], 1...23, 1-23
    match = re.search(r'\[?\s*(\-?\d+)\s*(?:\.\.\.|\.{2,}|-|–)\s*(\-?\d+)\s*\]?', value)
    if match:
        try:
            return float(match.group(1)), float(match.group(2))
        except ValueError:
            return np.nan, np.nan
    return np.nan, np.nan


def convert_excel_to_excel(input_path: str, output_path: str = "parametros_procesados.xlsx"):
    """
    Lee un archivo Excel, procesa las columnas según COLUMN_MAPPING,
    aplica transformaciones y exporta el resultado unificado a un nuevo Excel.
    """
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: Archivo no encontrado en la ruta: {input_path}")
        sys.exit(1)

    print(f"Leyendo tablas del archivo Excel: {input_path}")

    try:
        xls = pd.ExcelFile(input_file)
        sheet_names = xls.sheet_names
    except Exception as e:
        print(f"Error al abrir el archivo Excel: {e}")
        sys.exit(1)

    processed_dfs = []

    for i, sheet_name in enumerate(sheet_names, start=1):
        print(f"Procesando hoja {i}: {sheet_name}")

        # Leemos todo el contenido con encabezado en la primera fila
        df = pd.read_excel(input_file, sheet_name=sheet_name, header=0)

        # --- Eliminar la segunda fila (índice 1) ---
        if len(df) > 0:
            df = df.drop(df.index[0]).reset_index(drop=True)

        # --- Normalización de columnas ---
        df.columns = df.columns.astype(str).str.strip()
        df.rename(columns=COLUMN_MAPPING, inplace=True, errors='ignore')
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

        # --- Extraer min y max de Dimension ---
        if 'dimension' in df.columns:
            df['dimension'] = df['dimension'].astype(str)
            df[['minvalue', 'maxvalue']] = df['dimension'].apply(
                lambda x: pd.Series(extract_min_max_from_dimension(x))
            )
            df.drop(columns=['dimension'], inplace=True, errors='ignore')

        # --- Limpieza de texto ---
        for col in ['category', 'name', 'description', 'attribute']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        # --- system_category basado en category ---
        df['system_category'] = ' '
        if 'category' in df.columns:
            df.loc[df['category'].str.upper().str.contains('%ID'), 'system_category'] = 'DIGITAL_INPUT'
            df.loc[df['category'].str.upper().str.contains('%QD'), 'system_category'] = 'DIGITAL_OUTPUT'
            df.loc[df['category'].str.upper().str.contains('%IX'), 'system_category'] = 'BITDIGITAL_INPUT'
            df.loc[df['category'].str.upper().str.contains('%QX'), 'system_category'] = 'BITDIGITAL_OUTPUT'
            df.loc[df['category'].str.upper().str.contains('nan'), 'system_category'] = " "
            df.loc[df['category'].str.upper().str.contains(' '), 'system_category'] = " "

        # --- Reglas de lectura/escritura basadas en attribute ---
        df['read'] = 0
        df['write'] = 0

    if 'access_type' in df.columns and 'system_category' in df.columns:
        access = df['access_type'].astype(str).str.upper().str.strip()
        system_type = df['system_category'].astype(str).str.upper().str.strip()

        # Solo "R"
        only_read_mask = access == 'R'
        df.loc[only_read_mask & system_type.isin(['ANALOG', 'INTEGER']), 'read'] = 4
        df.loc[only_read_mask & system_type.isin(['DIGITAL']), 'read'] = 1
        df.loc[only_read_mask & system_type.isin(['ANALOG', 'INTEGER', 'DIGITAL']), 'write'] = 0

        # "R/W"
        read_write_mask = access == 'R/W'
        df.loc[read_write_mask & (system_type == 'ANALOG'), ['read', 'write']] = [3, 6]
        df.loc[read_write_mask & (system_type == 'INTEGER'), ['read', 'write']] = [3, 6]
        df.loc[read_write_mask & (system_type == 'DIGITAL'), ['read', 'write']] = [1, 5]

        # --- Valores por defecto ---
        df['sampling'] = 60
        df['unit'] = 0
        df['offset'] = 0.0

        processed_dfs.append(df)

    if not processed_dfs:
        print("No se encontraron hojas válidas para procesar.")
        return

    final_df = pd.concat(processed_dfs, ignore_index=True)

    num_rows = len(final_df)
    final_df["id"] = range(1, num_rows + 1)
    final_df["view"] = "simple"

    # --- Completar columnas faltantes ---
    final_df["addition"] = 0
    final_df["mask"] = 0
    final_df["value"] = 0
    final_df["general_icon"] = np.nan
    final_df["alarm"] = """ {"severity":"none"} """
    final_df["metadata"] = "[]"
    final_df["l10n"] = '{"_type":"l10n","default_lang":"en_US","translations":{"en_US":{"name":null,"_type":"languages","description":null}}}'
    final_df["tags"] = "[]"
    final_df["type"] = "modbus"
    final_df["parameter_write_byte_position"] = np.nan
    final_df["mqtt"] = np.nan
    final_df["json"] = np.nan
    final_df["current_value"] = np.nan
    final_df["current_error_status"] = np.nan
    final_df["notes"] = np.nan

    final_df = final_df.reindex(columns=LIBRARY_COLUMNS, fill_value=np.nan)

    final_df['category'] = final_df['category'].replace(np.nan, "")

    # --- Exportar ---
    try:
        with pd.ExcelWriter(output_path, engine='openpyxl', mode='w') as writer:
            final_df.to_excel(writer, sheet_name="Parametros_Procesados", index=False)
        print(f"✅ Archivo exportado correctamente con {len(final_df)} filas: {Path(output_path).resolve()}")
    except Exception as e:
        print(f"Error al escribir el archivo Excel: {e}")
        sys.exit(1)


def main():
    """Función principal para manejar la ruta de entrada."""
    if len(sys.argv) >= 2:
        path = sys.argv[1]
    else:
        default_path = "input.xlsx"
        path = input(f"Ruta al archivo Excel (deja vacío para '{default_path}'): ").strip()
        if not path:
            path = default_path

    convert_excel_to_excel(path)


if __name__ == "__main__":
    main()
