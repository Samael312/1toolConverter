"""
Backend iPro: Procesamiento de archivos Excel (variables de sistema) y conversión a DataFrame.
Este módulo no genera interfaz ni escribe archivos. 
Solo devuelve un DataFrame procesado para uso en la UI de main.py.
"""

import pandas as pd
import numpy as np
import re
import logging
from io import BytesIO
from typing import Optional, List

# =====================================================
# CONFIGURACIÓN DE LOGGING
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =====================================================
# CONSTANTES
# =====================================================

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

# =====================================================
# FUNCIONES AUXILIARES
# =====================================================

def extract_min_max_from_dimension(value: str):
    """Extrae valores mínimo y máximo de un texto como '[1...23]' o '1-23'."""
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
    Expande variables con dimension [min..max] en filas hijas (sin tocar IDs).
    Las hijas tendrán registers consecutivos al del padre.
    """
    new_rows = []
    for _, row in df.iterrows():
        if 'dimension' in row and pd.notna(row['dimension']):
            min_val, max_val = extract_min_max_from_dimension(row['dimension'])
            if not np.isnan(min_val) and not np.isnan(max_val):
                n = int(max_val - min_val + 1)
                total_bits = n * default_bits

                # Fila padre
                row['length'] = total_bits
                new_rows.append(row)

                # Base register
                base_register = np.nan
                if 'register' in row and pd.notna(row['register']):
                    try:
                        base_register = int(row['register'])
                    except:
                        base_register = np.nan

                # Hijas (register consecutivo)
                for offset in range(n):
                    pos = int(min_val + offset)
                    new_row = row.copy()
                    new_row['name'] = f"{row['name']}_{pos}"
                    new_row['length'] = f"{default_bits}bit"
                    new_row['description'] = f"{row['name']} - Posición {pos}"

                    # Si el padre tiene register válido → consecutivo
                    if not np.isnan(base_register):
                        new_row['register'] = base_register + offset + 1

                    new_rows.append(new_row)
                continue

        # Sin dimensión → fila normal
        row['length'] = f"{default_bits}bit"
        new_rows.append(row)

    return pd.DataFrame(new_rows)


# =====================================================
# FUNCIÓN PRINCIPAL DE PROCESAMIENTO
# =====================================================

def convert_excel_to_dataframe(file_bytes: bytes) -> Optional[pd.DataFrame]:
    """
    Procesa un archivo Excel (bytes) y devuelve un DataFrame procesado.
    No escribe archivos ni muestra UI.
    """
    try:
        excel_io = BytesIO(file_bytes)
        xls = pd.ExcelFile(excel_io)
        sheet_names = xls.sheet_names
        logger.info(f"Archivo Excel leído con {len(sheet_names)} hojas.")
    except Exception as e:
        logger.error(f"Error al abrir el archivo Excel: {e}", exc_info=True)
        return None

    processed_dfs: List[pd.DataFrame] = []

    for sheet_name in sheet_names:
        try:
            logger.info(f"Procesando hoja: {sheet_name}")
            df = pd.read_excel(xls, sheet_name=sheet_name, header=0)
            if len(df) > 0:
                df = df.drop(df.index[0]).reset_index(drop=True)

            df.columns = df.columns.astype(str).str.strip()
            df.rename(columns=COLUMN_MAPPING, inplace=True, errors='ignore')
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

            for col in ['category', 'name', 'description', 'attribute', 'groups']:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip()

            # ------------------------------------------------
            # Conversión de Address a decimal (si es hex)
            # ------------------------------------------------
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

            # ------------------------------------------------
            # Expansión de dimensiones (sin IDs aún)
            # ------------------------------------------------
            if 'dimension' in df.columns:
                df = expand_dimension_to_rows_name_bits(df, default_bits=1)
                df.drop(columns=['dimension'], inplace=True, errors='ignore')
            
            if 'description' in df.columns:
                df['description'] = df['description'].astype(str).str.slice(0, 60)

            # ------------------------------------------------
            # Categorización del sistema
            # ------------------------------------------------
            df['system_category'] = np.nan
            if 'groups' in df.columns:
                df['groups'] = df['groups'].str.upper()
                df.loc[df['groups'].str.contains('PARAMETROS_CONFIGURACION', na=False), 'system_category'] = 'CONFIG_PARAMETER'
                df.loc[df['groups'].str.contains('ALARMAS|WARNINGS', na=False), 'system_category'] = 'ALARM'
                df.loc[df['groups'].str.contains('COMANDOS', na=False), 'system_category'] = 'COMMAND'
                df.loc[df['groups'].str.contains('ESTADOS', na=False), 'system_category'] = 'STATUS'
                df.loc[df['groups'].str.contains('ENTRADAS_SALIDAS', na=False), 'system_category'] = 'INPUT_OUTPUT'
                df.loc[df['groups'].str.contains('INSTANCIA|REGISTRO', na=False), 'system_category'] = 'DEFAULT'

            valid_categories = ['CONFIG_PARAMETER', 'ALARM', 'COMMAND', 'STATUS', 'INPUT_OUTPUT', 'DEFAULT']
            df = df[df['system_category'].isin(valid_categories)].reset_index(drop=True)

            if df.empty:
                logger.warning(f"La hoja '{sheet_name}' no contiene categorías válidas, se omitirá.")
                continue

            # ------------------------------------------------
            # Valores min y max según system_category
            # ------------------------------------------------
            df["minvalue"] = 0
            df["maxvalue"] = 0

            df.loc[df["system_category"] == "COMMAND", ["minvalue", "maxvalue"]] = [0, 1]
            df.loc[df["system_category"] == "CONFIG_PARAMETER", ["minvalue", "maxvalue"]] = [0, 1]
            df.loc[df["system_category"] == "ALARM", ["minvalue", "maxvalue"]] = [0, 1]

            # ------------------------------------------------
            # Permisos de lectura/escritura
            # ------------------------------------------------
            df['read'] = 0
            df['write'] = 0

            if 'attribute' in df.columns:
                attr = df['attribute'].str.upper().str.strip()
                df.loc[attr == 'READ', ['read', 'write']] = [3, 0]
                df.loc[attr == 'READWRITE', ['read', 'write']] = [3, 6]
                df.loc[attr == 'WRITE', ['read', 'write']] = [0, 6]

            if 'system_category' in df.columns:
                system_type = df['system_category'].astype(str).str.upper().str.strip()
                only_read = (df['read'] > 0) & (df['write'] == 0)
                rw = (df['read'] > 0) & (df['write'] > 0)
                df.loc[only_read & system_type.isin(['ALARM']), 'read'] = 1
                df.loc[only_read & system_type.isin(['STATUS']), 'read'] = 4
                df.loc[rw & system_type.isin(['COMMAND']), ['read', 'write']] = [0, 6]
                df.loc[rw & system_type.isin(['CONFIG_PARAMETER']), ['read', 'write']] = [1, 5]
            
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

            # ------------------------------------------------
            # Normalización de longitud según potencias de 2 válidas (1, 2, 4, 8, 16bit)
            # ------------------------------------------------
            if 'length' in df.columns:
                def normalize_length(val):
                    try:
                        if isinstance(val, str):
                            num = re.findall(r'\d+', val)
                            length = int(num[0]) if num else 1
                        else:
                            length = int(val)
                    except Exception:
                        length = 1

                    valid_sizes = [1, 2, 4, 8, 16]
                    valid_match = max([v for v in valid_sizes if v <= length], default=1)
                    return f"{valid_match}bit"

                df['length'] = df['length'].apply(normalize_length)

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
            # ------------------------------------------------
            # Valores y columnas básicas
            # ------------------------------------------------
            df['sampling'] = 60
            df['unit'] = df.get('unit', np.nan)
            df['unit'] = df['unit'].replace({np.nan: "", "nan": ""})
            df['offset'] = 0.0

            processed_dfs.append(df)

        except Exception as e:
            logger.error(f"Error procesando hoja {sheet_name}: {e}", exc_info=True)
            continue

    if not processed_dfs:
        logger.warning("No se procesaron hojas válidas en el Excel.")
        return None

    # =====================================================
    # UNIFICACIÓN Y LIMPIEZA FINAL
    # =====================================================
    final_df = pd.concat(processed_dfs, ignore_index=True)
    final_df = final_df[pd.to_numeric(final_df["register"], errors="coerce").notna()].copy()
    final_df["register"] = final_df["register"].astype(int)
    final_df["id"] = range(1, len(final_df) + 1)
    final_df["view"] = "simple"

    # =====================================================
    # Columnas por defecto y orden final
    # =====================================================
    defaults = {
        "addition": 0,
        "mask": 0,
        "value": 0,
        "general_icon": np.nan,
        "alarm": """ {"severity":"none"} """,
        "metadata": "[]",
        "l10n": '{"_type":"l10n","default_lang":"en_US","translations":{"en_US":{"name":null,"_type":"languages","description":null}}}',
        "tags": "[]",
        "type": "modbus",
        "parameter_write_byte_position": np.nan,
        "mqtt": np.nan,
        "json": np.nan,
        "current_value": np.nan,
        "current_error_status": np.nan,
        "notes": np.nan,
        "category": np.nan,
    }
    for col, val in defaults.items():
        if col not in final_df.columns:
            final_df[col] = val

    final_df = final_df.reindex(columns=LIBRARY_COLUMNS, fill_value=np.nan)

    logger.info(f"Procesamiento finalizado correctamente ({len(final_df)} filas).")
    return final_df
