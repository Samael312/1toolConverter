# -*- coding: utf-8 -*-
# Author Kiconex - Samuel Ali 
# Description  Conversion of data table format of variables from Excel to processed Excel using pandas.
# Version  3.1
# Name  1tools - Convert Data Table Format (Excel Version)
# Type  Application

import sys
from pathlib import Path
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
    'Attribute': 'attribute',  # Columna para determinar read/write
    'Groups': 'groups'          # Columna para determinar system_category
}

def extract_min_max_from_dimension(value: str):
    """
    Extrae valores mínimo y máximo de un texto como '[1...23]', '[1-23]', '1...23', '1-23'
    Retorna (min, max) o (NaN, NaN) si no se puede extraer.
    """
    if not isinstance(value, str):
        return np.nan, np.nan

    value = value.strip()
    match = re.search(r'\[?\s*(\-?\d+)\s*(?:\.\.\.|\.{2,}|-|–)\s*(\-?\d+)\s*\]?', value)
    if match:
        try:
            return float(match.group(1)), float(match.group(2))
        except ValueError:
            return np.nan, np.nan
    return np.nan, np.nan

def expand_dimension_to_rows_name_bits(df, default_bits=1):
    """
    Expande variables con dimension [min..max] en varias filas hijas.
    - Variable padre mantiene length total (n * bits_por_elemento)
    - Hijas tienen length individual (bits_por_elemento)
    - Las hijas incluyen en description el nombre de la variable padre y posición
    """
    new_rows = []
    for _, row in df.iterrows():
        if 'dimension' in row and pd.notna(row['dimension']):
            min_val, max_val = extract_min_max_from_dimension(row['dimension'])
            if not np.isnan(min_val) and not np.isnan(max_val):
                n = int(max_val - min_val + 1)
                total_bits = n * default_bits
                row['length'] = total_bits  # padre
                new_rows.append(row)        # agregamos variable padre
                # filas hijas
                for offset in range(n):
                    new_row = row.copy()
                    pos = int(min_val + offset)
                    new_row['name'] = f"{row['name']}_{pos}"
                    new_row['length'] = default_bits
                    new_row['description'] = f"{row['name']} - Posición {pos}"
                    new_rows.append(new_row)
                continue
        # fila normal si no hay dimension
        row['length'] = default_bits
        new_rows.append(row)
    return pd.DataFrame(new_rows)

def convert_excel_to_excel(input_path: str, output_path: str = "parametros_procesados.xlsx"):
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
        df = pd.read_excel(input_file, sheet_name=sheet_name, header=0)

        if len(df) > 0:
            df = df.drop(df.index[0]).reset_index(drop=True)

        df.columns = df.columns.astype(str).str.strip()
        df.rename(columns=COLUMN_MAPPING, inplace=True, errors='ignore')
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

        for col in ['category', 'name', 'description', 'attribute', 'groups']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        # Convertir register a decimal
        if 'register' in df.columns:
            def register_to_decimal(val):
                val_str = str(val).strip()
                if re.fullmatch(r'[0-9a-fA-F]+', val_str):
                    return int(val_str, 16)
                try:
                    return int(val_str)
                except:
                    return np.nan
            df['register'] = df['register'].apply(register_to_decimal)

        # Expandir variables con dimension en filas hijas
        if 'dimension' in df.columns:
            df = expand_dimension_to_rows_name_bits(df, default_bits=1)
            df.drop(columns=['dimension'], inplace=True, errors='ignore')

        # system_category basado en groups
        df['system_category'] = np.nan
        if 'groups' in df.columns:
            df['groups'] = df['groups'].str.upper()
            df.loc[df['groups'].str.contains('PARAMETROS_CONFIGURACION', na=False), 'system_category'] = 'CONFIG_PARAMETERS'
            df.loc[df['groups'].str.contains('ALARMAS|WARNINGS', na=False), 'system_category'] = 'ALARM'
            df.loc[df['groups'].str.contains('COMANDOS', na=False), 'system_category'] = 'COMMANDS'
            df.loc[df['groups'].str.contains('ESTADOS', na=False), 'system_category'] = 'STATUS'
            df.loc[df['groups'].str.contains('ENTRADAS_SALIDAS', na=False), 'system_category'] = 'INPUT_OUTPUT'
            df.loc[df['groups'].str.contains('INSTANCIA|REGISTRO', na=False), 'system_category'] = 'DEFAULT'

        # Filtrar solo categorías válidas
        valid_categories = ['CONFIG_PARAMETERS', 'ALARM', 'COMMANDS', 'STATUS', 'INPUT_OUTPUT', 'DEFAULT']
        df = df[df['system_category'].isin(valid_categories)].reset_index(drop=True)
        if df.empty:
            print(f"⚠️  La hoja '{sheet_name}' no contiene grupos válidos, se omitirá.")
            continue

        # Lectura/escritura
        df['read'] = 0
        df['write'] = 0
        if 'attribute' in df.columns:
            attr = df['attribute'].str.upper().str.strip()
            df.loc[attr == 'READ', ['read', 'write']] = [3, 0]
            df.loc[attr == 'READWRITE', ['read', 'write']] = [3, 6]
            df.loc[attr == 'WRITE', ['read', 'write']] = [0, 6]

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

    # Columnas faltantes
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
    final_df['category'] = np.nan

    final_df = final_df.reindex(columns=LIBRARY_COLUMNS, fill_value=np.nan)

    try:
        with pd.ExcelWriter(output_path, engine='openpyxl', mode='w') as writer:
            final_df.to_excel(writer, sheet_name="Parametros_Procesados", index=False)
        print(f"✅ Archivo exportado correctamente con {len(final_df)} filas: {Path(output_path).resolve()}")
    except Exception as e:
        print(f"Error al escribir el archivo Excel: {e}")
        sys.exit(1)

def main():
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
