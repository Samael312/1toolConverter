import sys
from pathlib import Path
from typing import List
import pandas as pd
import numpy as np

# Se eliminó la importación de 'from openpyxl import Workbook'

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
    
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: Archivo no encontrado en la ruta: {input_path}")
        sys.exit(1)

    print(f"Leyendo tablas del archivo HTML: {input_path}")

    try:
        list_of_dataframes: List[pd.DataFrame] = pd.read_html(
            str(input_file),
            header=0,
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

    # El script original omite la primera tabla (índice 0), que suele ser el resumen.
    dataframes_to_export = list_of_dataframes[1:]

    if not dataframes_to_export: 
        print("Solo se encontró una tabla (la cual fue omitida). No hay nada que exportar.")
        sys.exit(0)

    output_file = Path(output_path)
    print(f"Combinando {len(dataframes_to_export)} tablas en una sola hoja...")
    
    processed_dfs = []

    try:
        for i, df in enumerate(dataframes_to_export, start=1):
            
            # --- Limpieza Inicial y Mapeo ---
            df.columns = df.columns.astype(str).str.strip()
            # Eliminar la primera fila si no es un índice numérico (a veces el header se repite)
            if not str(df.iloc[0, 0]).strip().isdigit():
                df = df.iloc[1:].copy() 
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
            
            # Identificar la columna de acceso ('Read/Write' o 'Direction')
            access_col_name = None
            for name in ['Read/Write', 'Direction']:
                if name in df.columns:
                    access_col_name = name
                    break
            
            # Aplicar mapeo de nombres
            current_mapping = COLUMN_MAPPING.copy()
            if access_col_name:
                current_mapping[access_col_name] = 'access_type'
            
            df.rename(columns=current_mapping, inplace=True, errors='ignore')

            # --- Inicializar sampling, read y write a valores por defecto ---
            df['sampling'] = np.nan
            df['read'] = 0
            df['write'] = 0


            if 'access_type' in df.columns:
                access = df['access_type'].astype(str).str.upper().str.strip()
                
                # Regla: Si contiene 'R' (o es solo 'R'), read = 4
                df.loc[access.str.contains('R'), 'read'] = 4
                
                # Regla: Si contiene 'W' (o es solo 'W'), write = 4
                df.loc[access.str.contains('W'), 'write'] = 4
                
                df.drop(columns=['access_type'], inplace=True, errors='ignore')
            
            # --- Conversiones y Limpieza de Columnas Numéricas/Texto ---

            if 'offset' in df.columns:
                df['offset'] = df['offset'].astype(str).str.strip().replace(['', '---', 'nan'], np.nan)
                df['offset'] = pd.to_numeric(df['offset'], errors='coerce') 
                df['offset'] = df['offset'].fillna(0.0)
            
            if 'unit' in df.columns:
                df['unit']= df['unit'].astype(str).str.strip().replace(['0','---', None], np.nan).fillna(' ')

            if 'category' in df.columns:
                df['category'] = df['category'].astype(str).str.upper().str.strip()
                df.loc[df['category'] == 'ALARMS', 'system_category'] = 'ALARM'
            
            # --- Lógica de Asignación Específica por 'system_category' (Sobrescritura) ---
            if 'system_category' in df.columns:
                df['system_category'] = df['system_category'].astype(str).str.upper().str.strip().replace(['', '---', 'nan'], np.nan)
                
                # Para registros con read > 0 (lectura permitida)
                is_readable = df['read'] > 0
                
                # Máscaras de Tipo de Dato
                analog_integer_mask = df['system_category'].isin(['ANALOG', 'INTEGER']) & is_readable
                digital_mask = df['system_category'].isin(['DIGITAL']) & is_readable
                alarm_mask = df['system_category'] == 'ALARM'
                
                # 1. ANALOG / INTEGER
                
                # Caso A: R/W (write > 0) -> Aplicar 3/16. ESTO NO AFECTA a R-Only.
                analog_integer_rw_mask = analog_integer_mask & (df['write'] > 0)
                df.loc[analog_integer_rw_mask, 'read'] = 3
                df.loc[analog_integer_rw_mask, 'write'] = 16
                df.loc[analog_integer_mask, 'sampling'] = 60 
                

                analog_integer_r_only_mask = analog_integer_mask & (df['write'] == 0)
                df.loc[analog_integer_r_only_mask, 'read'] = 4
                df.loc[analog_integer_r_only_mask, 'write'] = 0
                
                # 2. DIGITAL
                
                digital_rw_mask = digital_mask & (df['write'] > 0)
                df.loc[digital_rw_mask, 'read'] = 1
                df.loc[digital_rw_mask, 'write'] = 5
                df.loc[digital_mask, 'sampling'] = 60 
                

                digital_r_only_mask = digital_mask & (df['write'] == 0)
                df.loc[digital_r_only_mask, 'read'] = 4
                df.loc[digital_r_only_mask, 'write'] = 0

                # 3. ALARM (Siempre 4/0)
                df.loc[alarm_mask, 'read'] = 4
                df.loc[alarm_mask, 'write'] = 0
                df.loc[alarm_mask, 'sampling'] = 30
                
                is_r_only_after_processing = (df['read'] > 0) & (df['write'] == 0) & ~(analog_integer_mask | digital_mask | alarm_mask)
                df.loc[is_r_only_after_processing, 'read'] = 4
                df.loc[is_r_only_after_processing, 'write'] = 0


            # --- Lógica de min/max y length ---
            
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
            
            
            if 'system_category' in df.columns:
                
                # 1. Definir las máscaras de estado de acceso y tipo
                is_writeable = df['write'] > 0
                is_readable = df['read'] > 0
                is_read_only = (df['read'] > 0) & (df['write'] == 0)
                
                is_analog = df['system_category'].isin(['ANALOG', 'ANALOG_INPUT', 'ANALOG_OUTPUT'])
                is_integer = df['system_category'].isin(['INTEGER'])
                is_digital = df['system_category'].isin(['DIGITAL', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT'])
                is_alarm = df['system_category'] == 'ALARM'

                # 2. Construir la lista de condiciones con la nueva distinción
                conditions_new_cat = [
                    # 1. SET_POINT: 
                    (is_analog) & (is_writeable) & (is_readable), 
                    
                    # 2. CONFIG_PARAMETER: 
                    (is_integer) & (is_writeable) & (is_readable),
                    
                    # 3. ANALOG_INPUT: 
                    (is_analog | is_integer) & (is_read_only),
                    
                    # 4. COMMAND: 
                    (is_digital) & (is_writeable) & (is_readable),
                    
                    # 5. DIGITAL_INPUT: 
                    (is_digital) & (is_read_only),
                    
                    # 6. ALARM
                    (is_alarm) & (is_readable),
                ]
                
                # 3. Construir la lista de opciones (debe coincidir con la cantidad de condiciones)
                choices_new_cat = [
                    'SET_POINT',          # 1. Analog R/W
                    'CONFIG_PARAMETER',   # 2. Integer R/W
                    'ANALOG_INPUT',       # 3. Analog/Integer R-Only
                    'COMMAND',     # 4. Digital R/W (Commands)
                    'DIGITAL_INPUT',      # 5. Digital R-Only
                    'ALARM',              # 6. Alarm
                ]
                df['system_category'] = np.select(conditions_new_cat, choices_new_cat, default='STATUS') 

            processed_dfs.append(df)
            
        if not processed_dfs:
            print("No se encontraron DataFrames válidos para concatenar.")
            return

        # --- Concatenación y Finalización ---
        final_df = pd.concat(processed_dfs, ignore_index=True)
        
        num_rows = len(final_df)
        final_df["id"] = range(1, num_rows + 1)
        
        # Rellenar valores de 'sampling' que aún sean NaN (no entraron en ninguna condición)
        final_df["sampling"] = final_df["sampling"].fillna(60)
        
        # Asignación de valores por defecto
        final_df["view"] = "simple"
        final_df["addition"] = 0 
        final_df["mask"] = 0
        final_df["value"] = 0
        
        # Columnas de metadatos/status
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
        final_df["category"]=np.nan
    
        
        final_df = final_df.reindex(columns=LIBRARY_COLUMNS, fill_value=np.nan)
        
        # BLOQUE DE EXPORTACIÓN FINAL SIMPLIFICADO:
        with pd.ExcelWriter(output_file, engine='openpyxl', mode='w') as writer:
            final_df.to_excel(writer, sheet_name="Parametros_Unificados", index=False)

        print(f" Las {len(dataframes_to_export)} tablas se han unido y exportado a una única hoja llamada 'Parametros_Unificados' en '{output_file.resolve()}'")

    except Exception as e:
        print(f"Error al escribir o procesar el archivo Excel: {e}")
        print("Asegúrate de tener instaladas las librerías: pandas, numpy, openpyxl, lxml, y beautifulsoup4 (bs4).")
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