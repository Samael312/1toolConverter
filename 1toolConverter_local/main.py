# Author Kiconex - Samuel Ali 
# Description    Conversion of data table format of variables from HTML to Excel using pandas.
# Version    3.0 
# Name   1tools - Convert Data Table Format
# Type   Application

import sys
from pathlib import Path
from typing import List
import pandas as pd
from openpyxl import Workbook 
import numpy as np

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

def convert_html_to_excel(input_path: str, output_path: str = "parametros_convertidos.xlsx"):
    
    #Lee un archivo HTML, extrae las tablas, mapea sus columnas al formato 
    #de la Librería LIBRARY y las guarda como hojas separadas en un archivo Excel.
    
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: Archivo no encontrado en la ruta: {input_path}")
        sys.exit(1)

    print(f"Leyendo tablas del archivo HTML: {input_path}")

    try:

        list_of_dataframes: List[pd.DataFrame] = pd.read_html(
            str(input_file),
            header=0,  # Usa la primera fila como encabezado
            flavor='bs4'
        )
    except ValueError:
        print("Error: No se encontraron tablas válidas en el archivo HTML.")
        sys.exit(0)
    except Exception as e:
        print(f"Error al procesar el archivo HTML con pandas: {e}")
        sys.exit(1)

    if not list_of_dataframes:
        print("No se encontraron tablas para exportar.")
        sys.exit(0)

    dataframes_to_export = list_of_dataframes[1:]

    if not dataframes_to_export: 
        print("Solo se encontró una tabla (la cual fue omitida). No hay nada que exportar.")
        sys.exit(0)

    output_file = Path(output_path)
    print(f"Escribiendo {len(dataframes_to_export)} tablas en '{output_file.resolve()}'...")

    # Usar ExcelWriter para escribir múltiples DataFrames en un solo archivo .xlsx
    try:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            for i, df in enumerate(dataframes_to_export, start=1):
                sheet_name = f"Tabla_{i}"
                
                
                # 1. Limpieza inicial: eliminar posibles filas de encabezado repetidas y columnas sin nombre.
                df.columns = df.columns.astype(str).str.strip()
                if not str(df.iloc[0, 0]).strip().isdigit():
                    df = df.iloc[1:].copy() 
                df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
                
                # 2. Identificar la columna de acceso ('Read/Write' o 'Direction')
                access_col_name = None
                for name in ['Read/Write', 'Direction']:
                    if name in df.columns:
                        access_col_name = name
                        break
                
                # 3. Aplicar mapeo de nombres
                current_mapping = COLUMN_MAPPING.copy()
                if access_col_name:
                    current_mapping[access_col_name] = 'access_type'
                
                df.rename(columns=current_mapping, inplace=True, errors='ignore')

                # 4. Crear columnas 'read' y 'write' a partir de 'access_type'
                if 'access_type' in df.columns:
                    # R (Read) o RW (Read/Write) -> read = 4
                    df['read'] = df['access_type'].astype(str).str.upper().apply(
                        lambda x: 4 if 'R' in x else 0
                    )
                    # W (Write) o RW (Read/Write) -> write = 4
                    df['write'] = df['access_type'].astype(str).str.upper().apply(
                        lambda x: 4 if 'W' in x else 0
                    )
                    df.drop(columns=['access_type'], inplace=True, errors='ignore')
                else:
                    df['read'] = 0
                    df['write'] = 0

                if 'offset' in df.columns:
                    df['offset'] = df['offset'].astype(str).str.strip().replace(['', '---', 'nan'], np.nan)
                    df['offset'] = pd.to_numeric(df['offset'], errors='coerce') 
                    df['offset'] = df['offset'].fillna(0.0)
                
                if 'unit' in df.columns:
                    df['unit']= df['unit'].astype(str).str.strip().replace(['0','---', None], np.nan).fillna(' ')

                if 'category' in df.columns:

                    df['category'] = df['category'].astype(str).str.upper().str.strip()

                    df.loc[df['category'] == 'ALARMS', 'system_category'] = 'ALARM'
                
                if 'system_category' in df.columns:
                  
                    df['system_category'] = df['system_category'].astype(str).str.upper().str.strip()

                    df.loc[df['system_category'] == 'ANALOG', 'read'] = 3
                    df.loc[df['system_category'] == 'ANALOG', 'write'] = 16
                    df.loc[df['system_category'] == 'ANALOG', 'sampling'] = 60

                    df.loc[df['system_category'] == 'INTEGER', 'read'] = 3
                    df.loc[df['system_category'] == 'INTEGER', 'write'] = 16
                    df.loc[df['system_category'] == 'INTEGER', 'sampling'] = 60

                    df.loc[df['system_category'] == 'DIGITAL', 'read'] = 1
                    df.loc[df['system_category'] == 'DIGITAL', 'write'] = 5
                    df.loc[df['system_category'] == 'DIGITAL', 'sampling'] = 60

                    df.loc[df['system_category'] == 'ALARM', 'read'] = 4
                    df.loc[df['system_category'] == 'ALARM', 'write'] = 0
                    df.loc[df['system_category'] == 'ALARM', 'sampling'] = 30
                
        
                if 'minvalue' in df.columns:
                    df['minvalue'] = df['minvalue'].astype(str).str.strip().replace(['', '---', 'nan'], np.nan)
                    df['minvalue'] = pd.to_numeric(df['minvalue'], errors='coerce') 
                
                if 'maxvalue' in df.columns:
                    df['maxvalue'] = df['maxvalue'].astype(str).str.strip().replace(['', '---', 'nan'], np.nan)
                    df['maxvalue'] = pd.to_numeric(df['maxvalue'], errors='coerce')
                
                df['length'] = '16bit' 

                if 'minvalue' in df.columns:
                    negative_min_condition = df['minvalue'].notna() & (df['minvalue'] < 0)
                    df.loc[negative_min_condition, 'length'] = 's16'
                
                elif 'maxvalue' in df.columns:
                    negative_max_condition = df['maxvalue'].notna() & (df['maxvalue'] < 0)
                    df.loc[negative_max_condition, 'length'] = 's16'


                # 5. Añadir columnas de metadatos 
                num_rows = len(df)
                df["id"] = range(1, num_rows + 1)
                df["view"] = "simple"
                df["addition"] = 0
                df["mask"] = 0
                df["value"] = 0
                df["general_icon"] = np.nan
                df["alarm"] = """ {"severity":"none"} """
                df["metadata"] = "[]"
                df["l10n"] = '{"_type":"l10n","default_lang":"en_US","translations":{"en_US":{"name":null,"_type":"languages","description":null}}}'
                df["tags"] = "[]"
                df["type"] = "modbus"
                df["parameter_write_byte_position"] = np.nan
                df["mqtt"] = np.nan
                df["json"] = np.nan
                df["current_value"] = np.nan
                df["current_error_status"] = np.nan
                df["notes"] = np.nan
                
                # 6. Reordenar las columnas para coincidir exactamente con el orden de Panasonic
                df = df.reindex(columns=LIBRARY_COLUMNS, fill_value=np.nan)
                


                df.to_excel(writer, sheet_name=sheet_name, index=False)

        print(f"Las tablas se han exportado y convertido al formato comun en '{output_file.resolve()}'")

    except Exception as e:
        print(f"Error al escribir el archivo Excel: {e}")
        sys.exit(1)


def main():
    if len(sys.argv) >= 2:
        path = sys.argv[1]
    else:

        default_path = "input.html"
        path = input(f"Ruta al archivo HTML (deja vacío para '{default_path}'): ").strip()
        if not path:
             path = default_path

    convert_html_to_excel(path, output_path="parametros_convertidos.xlsx")


if __name__ == "__main__":
    main()