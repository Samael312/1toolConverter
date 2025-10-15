# Author Kiconex - Samuel Ali 
# Description    Conversion of data table format of variables from HTML to Excel using pandas.
# Version    2.0
# Name   1tools - Convert Data Table Format
# Type   Application

import sys
from pathlib import Path
from typing import List
import pandas as pd
from openpyxl import Workbook 

def convert_html_to_excel(input_path: str, output_path: str = "parametros.xlsx"):
    
    #Lee un archivo HTML, extrae todas las tablas y las guarda como
    #hojas separadas en un archivo Excel.
    
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: Archivo no encontrado en la ruta: {input_path}")
        sys.exit(1)

    print(f"Leyendo tablas del archivo HTML: {input_path}")

    try:
        list_of_dataframes: List[pd.DataFrame] = pd.read_html(
            str(input_file),
            header=0,  # Usa la primera fila como encabezado (lo que hace <th>)
            flavor='bs4' # Usa BeautifulSoup4 para el análisis
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
                # Generar nombre de hoja seguro
                sheet_name = f"Tabla_{i}"

                if not str(df.iloc[0, 0]).strip().isdigit():
                    df = df.iloc[1:]
                    # Opcional: Eliminar la columna 'Unnamed: 0' que a veces se crea
                    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
                
                df["addition"]= " "
                df["mask"]= " "
                df["value"]= " "
                df["length"]= "16bit"
                df["addition"]= " "
                df["general_icon"]= " "
                df["alarm"]= """ {"severity":"none"} """
                df["metadata"]= "[]"
                df["l10n"]= """ "{"_type":"l10n","default_lang":"en_US","translations":{"de_DE":{"name":null,"_type":"languages","category":null,"description":null},"en_US":{"name":null,"_type":"languages","category":"Alert Code 1","description":"Alert Code1"},"es_ES":{"name":null,"_type":"languages","category":null,"description":null},"fr_FR":{"name":null,"_type":"languages","category":null,"description":null},"it_IT":{"name":null,"_type":"languages","category":null,"description":null},"pt_PT":{"name":null,"_type":"languages","category":null,"description":null}}}" """
                df["tags"]= "[]"
                df["type"]= "modbus"
                df["parameter_write_byte_position"]= " "
                df["mqtt"]= " " 
                df["json"]= " "
                df["current_value"]= " " 
                df["current_error_status"]= " "  
                df["notes"]= " "  

                COLUMN_TO_DELETE = "Category"

                if COLUMN_TO_DELETE in df.columns:
                    df = df.drop(columns=[COLUMN_TO_DELETE]) 
                else:
                    print(f"Advertencia: La columna '{COLUMN_TO_DELETE}' no se encontró en la tabla {i} y fue omitida.")

                df.to_excel(writer, sheet_name=sheet_name, index=False)

        print(f"Las tablas se han exportado a '{output_file.resolve()}'")

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

    convert_html_to_excel(path)


if __name__ == "__main__":
    main()