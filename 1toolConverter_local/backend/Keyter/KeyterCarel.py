#!/usr/bin/env python3
"""
Backend Keyter (Adaptado): procesamiento de archivos Excel (Formato MV-BV) -> DataFrame -> Excel procesado.
Procesa hojas Analogicas, Enteras y Digitales aplicando lógica contextual avanzada.
"""

from typing import List, Optional, Dict, Any
import sys
import os
import logging
import pandas as pd
import numpy as np
from openpyxl import load_workbook
import json
from io import BytesIO

# =====================================================
# CONFIGURACIÓN DE LOGGING
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =====================================================
# CONSTANTES Y MAPEADO
# =====================================================

LIBRARY_COLUMNS = [
    "id", "register", "name", "description", "system_category", "category", "view",
    "sampling", "read", "write", "minvalue", "maxvalue", "unit", "offset",
    "addition", "mask", "value", "length", "general_icon", "alarm", "metadata",
    "l10n", "tags", "type", "parameter_write_byte_position", "mqtt", "json",
    "current_value", "current_error_status", "notes"
]

COLUMN_MAPPING = {
    "MODBUS Address": "register",
    "Variable name": "name",
    "Descripción ES": "description",
    "Description EN": "description_en",
    "UOM": "unit",
    "Min": "minvalue",
    "Max": "maxvalue",
    "Category": "system_category",
    "Read/Write": "access_type",
    "R/W": "access_type",
    "Direction": "access_type"
}
# --- NUEVAS CONSTANTES PARA LA LÓGICA CONTEXTUAL ---

SHEET_SPECIFIC_MAPPING = {
    "ANALOGICAS": {'DEFAULT': 'SET_POINT'},
    "ENTERAS": {'DEFAULT': 'STATUS'},
    "DIGITAL": {'DEFAULT': 'ESTADO'}
}
GENERAL_FALLBACK = {
    "INPUT-OUTPUT": "HOLIS", "DEFAULT": "CONFIG_PARAMETER", "SERVICES": "SYSTEM",
    "ALARMS": "ALARM", "CLOCK / TIMEDATE": "SYSTEM", "COMMUNICATION": "SYSTEM",
    "CONSIGNA": "SET_POINT", "COMANDO": "COMMAND"
}

SAMPLING_MAP = {
    "ALARM": 30, "SET_POINT": 300, "STATUS": 60, 
    "ANALOG_INPUT": 60, "DIGITAL_INPUT": 60
}
# 2. Lógica de permisos para una sola fila
def get_row_permissions(category: str, original_access: str = 'R/W'):
    """
    Traduce la categoría y el acceso original (R, W, R/W) 
    a los códigos numéricos de este backend.
    """
    category = category.upper()
    access = str(original_access).upper().strip()
    
    # Valores por defecto
    r, w = 0, 0
    
    # Lógica base según el tipo de acceso de Excel
    if access == 'R': r, w = 480, 0
    elif access == 'W': r, w = 0, 5216
    else: r, w = 3232, 621 # R/W por defecto
    
    # Ajustes específicos según tu lógica de Keyter
    if category in ['ANALOG_INPUT', 'ANALOG_OUTPUT', 'SYSTEM', 'STATUS', 'ALARM', 'DIGITAL_INPUT']:
        r = 52
    
    if category == 'COMMAND':
        w = 32
        
    if category in ['SET_POINT', 'CONFIG_PARAMETER', 'DIGITAL_OUTPUT']:
        if access != 'R': # Si no era estrictamente lectura
            r, w = 10, 25
            
    return r, w



# =====================================================
# FUNCIONES AUXILIARES
# =====================================================

def _add_default_columns(df: pd.DataFrame) -> pd.DataFrame:
    defaults = {
        "addition": 0,
        "mask": 0,
        "value": 0,
        "alarm": '{"severity":"none"}',
        "metadata": "[]",
        "tags": "[]",
        "type": "modbus"
    }
    for c, v in defaults.items():
        if c not in df.columns:
            df[c] = v
    return df

def _apply_column_mapping(df: pd.DataFrame) -> pd.DataFrame:
    col_map = {}
    for src, dst in COLUMN_MAPPING.items():
        if src in df.columns:
            col_map[src] = dst
    
    df.rename(columns=col_map, inplace=True)
    return df

#def _apply_contextual_mapping(row):
    """ Lógica fila por fila para tener contexto de la hoja (Fallback inicial) """
    sheet = str(row.get('sheet_name', '')).upper()
    logger.info(f"[LOG:CONTEXT] Procesando fila en hoja '{sheet}' con categoría original: '{row.get('system_category', '')}'")
    category = str(row.get('system_category', '')).upper().strip()
    
    
    if category in ['NAN', 'NONE', '', 'NULL']: category = ''

    rules = {}
    if any(k in sheet for k in ["ANALOGICAS"]):
        rules = SHEET_SPECIFIC_MAPPING.get("ANALOGICAS", {})
    elif any(k in sheet for k in ["ENTERAS"]):
        rules = SHEET_SPECIFIC_MAPPING.get("ENTERAS", {})
    elif any(k in sheet for k in ["DIGITAL"]):
        rules = SHEET_SPECIFIC_MAPPING.get("DIGITAL", {})

    result = rules.get(category)
    

    return result if result else (category if category else "hOLA")

# =====================================================
# LÓGICA DE REFINAMIENTO (Tu nueva función)
# =====================================================

def _process_specific_columns(df: pd.DataFrame) -> pd.DataFrame:
    if 'offset' in df.columns:
        df['offset'] = pd.to_numeric(
            df['offset'].astype(str).replace(['', '---', 'nan', 'None'], None),
            errors='coerce'
        ).fillna(0.0)

    if 'unit' in df.columns:
        df['unit'] = df['unit'].astype(str).replace(['0', '---', 'None', 'nan'], ' ').str.strip()

    if 'system_category' in df.columns:
        # Pre-limpieza para asegurar que strings nulos sean manejables
        df['system_category'] = df['system_category'].astype(str).replace(['nan', 'None', 'NaN'], '')
        
        # Log de valores únicos antes de procesar
        raw_values = df['system_category'].unique().tolist()
        #logger.info(f"[LOG:SYSTEM_CATEGORY] Valores originales: {raw_values}")

        # --- APLICACIÓN DE LA LÓGICA CONTEXTUAL (FILA POR FILA) ---
        #df['system_category'] = df.apply(_apply_contextual_mapping, axis=1)
        df['system_category'] = df['system_category'].str.upper().str.strip()  
        
        # LOG de resultados agrupados por hoja
        if 'sheet_name' in df.columns:
            for sheet in df['sheet_name'].unique():
                counts = df[df['sheet_name'] == sheet]['system_category'].value_counts().to_dict()
                #logger.info(f"[LOG:MAPEO] Hoja '{sheet}' resumida: {counts}")

        # Filtrado de filas que quedaron inválidas (aunque la lógica devuelve STATUS por defecto)
        before_count = len(df)
        df = df[~df['system_category'].isin(['NONE', '','NAN', 'NULL'])].copy()
        
    if 'name' in df.columns:
        df['name'] = df['name'].astype(str).str.strip()
        df = df[~df['name'].isin(['NONE', '','NAN', 'None', 'nan'])].copy()

    for col in ['minvalue', 'maxvalue']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    if 'description' in df.columns:
        df['description'] = df['description'].astype(str).str.slice(0, 60)

    return df

def _process_access_permissions(df: pd.DataFrame) -> pd.DataFrame:
    df['read'] = 0
    df['write'] = 0
    
    if 'access_type' in df.columns:
        access = df['access_type'].astype(str).str.upper().str.strip()
        only_read = access == 'R'
        rw = (access == 'R/W') | (access == 'W/R')
        
        df.loc[only_read, 'read'] = 4
        df.loc[access == 'W', 'write'] = 6
        df.loc[rw, ['read', 'write']] = [3, 6]
        
        if 'system_category' in df.columns:
            #logger.info("[LOG:PERMISOS] Ajustando permisos basados en categorías de sistema...")
            system_type = df['system_category'].astype(str).str.upper().str.strip()
            
            # Aplicación de lógica específica por categoría
            df.loc[only_read & system_type.isin(['ANALOG_INPUT', 'ANALOG_OUTPUT', 'SYSTEM', 'STATUS']), 'read'] = 3
            df.loc[only_read & system_type.isin(['ALARM']), 'read'] = 3
            df.loc[only_read & system_type.isin(['STATUS', 'DIGITAL_INPUT']), 'read'] = 3
            df.loc[only_read & system_type.isin(['COMMAND']), 'write'] = 6
            df.loc[rw & system_type.isin(['SET_POINT']), ['read', 'write']] = [3, 16]
            df.loc[rw & system_type.isin(['CONFIG_PARAMETER', 'DIGITAL_OUTPUT']), ['read', 'write']] = [3, 16]
            df.loc[rw & system_type.isin(['DIGITAL_INPUT']), 'read'] = 3
        
        df.drop(columns=['access_type'], inplace=True, errors='ignore')
    return df

def _determine_data_length(df: pd.DataFrame) -> pd.DataFrame:
    category_mapping = {
        'SET_POINT': '16bit/s16', 'ANALOG_INPUT': '16bit/s16', 'ALARM': '1bit',
        'COMMAND': '1bit', 'DIGITAL_INPUT': '1bit', 'STATUS': '1bit',
        'CONFIG_PARAMETER': '16bit/s16', 'ANALOG_OUTPUT': '16bit/s16',
        'DIGITAL_OUTPUT': '1bit', 'SYSTEM': '16bit'
    }
    df["length"] = None
    if "system_category" in df.columns:
        df["length"] = df["system_category"].map(category_mapping)
    
    mask_16bit = df["length"].fillna("").str.contains("16bit")
    if "minvalue" in df.columns and "maxvalue" in df.columns:
        is_signed = (df["minvalue"] < 0) | (df["maxvalue"] < 0)
        df.loc[mask_16bit & is_signed, "length"] = "s16"
        df.loc[mask_16bit & ~is_signed, "length"] = "16bit"
        df.loc[df["length"].isna(), "length"] = "16bit"
    return df

def _apply_deep_classification(df: pd.DataFrame) -> pd.DataFrame:
    if "system_category" not in df.columns or df["system_category"].isnull().all():
        #logger.warning("[LOG:SYSTEM_CATEGORY] No se encontró columna de categoría. Asignando 'STATUS' por defecto.")
        df["system_category"] = "HOLA"
    return df

def _apply_system_configuratiom(df: pd.DataFrame) -> pd.DataFrame:
    if "system_category" in df.columns:
        system_type = df['system_category'].astype(str).str.upper().str.strip()
        # Tags especiales para registros de sistema
        #system_count = (system_type == "SYSTEM").sum()
        #if system_count > 0:
            #logger.info(f"[LOG:TAGS] Marcando {system_count} registros con tag 'library_identifier'.")
        df["tags"] = np.where(system_type.isin(["SYSTEM"]), '["library_identifier"]', "[]")
        
    if "name" in df.columns:
        df["name"] = df["name"].astype(str).str.strip()
        duplicates = df.groupby("name").cumcount()
        df["name"] = np.where(duplicates == 0, df["name"], df["name"] + "_" + (duplicates + 1).astype(str))
    return df

def _apply_sampling_rules(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {"ALARM": 30, "SET_POINT": 300, "DEFAULT": 0, "COMMAND": 0, "STATUS": 60, "SYSTEM": 0, "CONFIG_PARAMETER": 0}
    if "system_category" in df.columns:
        df["sampling"] = df["system_category"].map(mapping).fillna(0)
    else:
        df["sampling"] = 0
    return df

def _apply_view_rules(df: pd.DataFrame) -> pd.DataFrame:
    view_map = {'ALARM': 'simple', 'SET_POINT': "simple", 'DEFAULT': "simple", 'COMMAND': "simple", 'STATUS': "basic", 'CONFIG_PARAMETER': "simple", 'SYSTEM': 'simple'}
    if "system_category" in df.columns:
        df['view'] = df['system_category'].map(view_map).fillna('simple')
    else:
        df['view'] = 'simple'
    return df

def _apply_localization(df: pd.DataFrame) -> pd.DataFrame:
    langs = {"description_en": "en_US", "description": "es_ES"}
    def build_l10n(row):
        translations = {}
        for col, lang in langs.items():
            if col in row and pd.notna(row[col]):
                desc = str(row[col]).strip()[:60]
                if desc and desc.lower() != 'nan':
                    translations[lang] = {"name": None, "_type": "languages", "category": None, "description": desc}
        if not translations:
             translations = {"es_ES": {"_type": "languages", "description": None}}
        return json.dumps({"_type": "l10n", "default_lang": "es_ES", "translations": translations}, ensure_ascii=False, separators=(',', ':'))
    df["l10n"] = df.apply(build_l10n, axis=1)
    return df

def _apply_range_rules(df: pd.DataFrame) -> pd.DataFrame:
    if "value" in df.columns:
        df["value"] = pd.to_numeric(df["value"], errors='coerce').fillna(0)
        df["value"] = df["value"].clip(lower=-32767, upper=32767)
    return df

# =====================================================
# LÓGICA DE TRANSFORMACIÓN
# =====================================================

def _process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.astype(str).str.strip()
    df = _apply_column_mapping(df)
    # Aquí es donde se llama a la nueva lógica de mapeo
    df = _process_specific_columns(df)
    df = _process_access_permissions(df)
    df = _determine_data_length(df)
    df = _apply_deep_classification(df)
    df = _apply_sampling_rules(df)
    df = _apply_view_rules(df)
    df = _apply_localization(df)
    df = _apply_system_configuratiom(df)
    df = _apply_range_rules(df)
    df = _add_default_columns(df)
    df.dropna(how="all", inplace=True)
    
    if 'register' in df.columns:
        df = df.dropna(subset=['register'])
        
    return df

# =====================================================
# PROCESAMIENTO DESDE BYTES (Para la Web UI)
# =====================================================

def process_excel(
    excel_content: bytes, 
    header_row: int = 3
) -> Optional[pd.DataFrame]:
    logger.info("--- Procesando Excel desde memoria (Bytes) ---")

    try:
        excel_io = BytesIO(excel_content)
        wb = load_workbook(excel_io, data_only=True, read_only=False)
    except Exception as e:
        logger.error(f"Error al cargar Excel desde bytes: {e}", exc_info=True)
        return None

    logger.info(f"Hojas encontradas: {wb.sheetnames!r}")

    preferred_keywords = ["ANALOG", "ENTERAS", "DIGITAL", "ANALOGICAS", "INTEGER"]
    found = []
    
    for s in wb.sheetnames:
        if any(k in s.upper().strip() for k in preferred_keywords):
            found.append(s)

    if len(found) < 3:
        logger.warning("No se detectaron hojas estándar (Analogicas/Enteras/Digital). Usando las 3 primeras visibles.")
        found = wb.sheetnames[:3]

    logger.info(f"Hojas a procesar: {found!r}")
    processed_dfs = []

    for sheet_name in found:
        try:
            ws = wb[sheet_name]
            if getattr(ws, "max_row", 0) <= header_row:
                continue

            header_cells = list(ws[header_row])
            headers = [str(c.value).strip() if c.value else f"col_{i}" for i, c in enumerate(header_cells)]

            rows = []
            for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
                if not any(row): continue 
                row_dict = {headers[i]: row[i] for i in range(min(len(headers), len(row)))}
                # CRÍTICO: Añadimos el nombre de la hoja para el mapeo contextual
                row_dict["sheet_name"] = sheet_name
                rows.append(row_dict)

            df_raw = pd.DataFrame(rows)
            if df_raw.empty: continue

            df_proc = _process_dataframe(df_raw)
            logger.info(f"-> Hoja '{sheet_name}' procesada: {len(df_proc)} filas.")
            processed_dfs.append(df_proc)

        except Exception as e:
            logger.error(f"Error procesando hoja '{sheet_name}': {e}", exc_info=True)
            continue

    if not processed_dfs:
        return None

    df_total = pd.concat(processed_dfs, ignore_index=True)
    df_total["id"] = range(1, len(df_total) + 1)
    df_total = _add_default_columns(df_total)
    
    for col in LIBRARY_COLUMNS:
        if col not in df_total.columns:
            df_total[col] = None
    
    return df_total.reindex(columns=LIBRARY_COLUMNS)

# =====================================================
# PROCESAMIENTO DE ARCHIVO COMPLETO
# =====================================================

def process_excel_file_carel(path: str, header_row: int = 3) -> Optional[pd.DataFrame]:
    logger.info(f"--- Iniciando lectura del archivo: {path} ---")
    
    try:
        wb = load_workbook(path, data_only=True)
    except Exception as e:
        logger.error(f"No se pudo abrir el archivo Excel: {e}")
        return None

    preferred_keywords = ["ANALOG", "ENTERAS", "DIGITAL", "ANALOGICAS", "INTEGER"]
    found = [s for s in wb.sheetnames if any(k in s.upper().strip() for k in preferred_keywords)]

    if len(found) < 3:
        found = wb.sheetnames[:3]

    processed_dfs = []

    for sheet in found:
        logger.info(f"Leyendo hoja: '{sheet}'...")
        ws = wb[sheet]
        
        if getattr(ws, "max_row", 0) <= header_row:
            continue
            
        try:
            header_cells = list(ws[header_row])
            headers = [str(c.value).strip() if c.value else f"col_{i}" for i, c in enumerate(header_cells)]
            
            data_rows = []
            for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
                if not any(row): continue
                row_dict = {headers[i]: row[i] for i in range(min(len(headers), len(row)))}
                # CRÍTICO: Añadimos el nombre de la hoja para el mapeo contextual
                row_dict["sheet_name"] = sheet
                data_rows.append(row_dict)
            
            df_raw = pd.DataFrame(data_rows)
            if df_raw.empty: continue
                
            df_proc = _process_dataframe(df_raw)
            processed_dfs.append(df_proc)
            logger.info(f"-> OK: Hoja '{sheet}' procesada correctamente ({len(df_proc)} filas).")
            
        except Exception as e:
            logger.error(f"-> ERROR procesando hoja '{sheet}': {e}", exc_info=True)

    if not processed_dfs:
        return None

    final_df = pd.concat(processed_dfs, ignore_index=True)
    final_df["id"] = range(1, len(final_df) + 1)
    final_df = _add_default_columns(final_df)
    
    for col in LIBRARY_COLUMNS:
        if col not in final_df.columns:
            final_df[col] = None
            
    return final_df.reindex(columns=LIBRARY_COLUMNS)

# =====================================================
# MAIN
# =====================================================

def _output_path(path: str) -> str:
    base = os.path.basename(path)
    name, _ = os.path.splitext(base)
    return os.path.join(os.path.dirname(path), f"processed_{name}.xlsx")

def main(argv: List[str]):
    if len(argv) < 2:
        print("Uso: python main.py archivo.xlsx")
        sys.exit(1)

    input_path = argv[1]
    output_path = _output_path(input_path)

    df = process_excel_file_carel(input_path)
    if df is None:
        logger.error("CANCELADO: No se generó DataFrame final.")
        sys.exit(2)

    logger.info(f"Guardando archivo en disco: {output_path} ...")
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="processed")

    logger.info("¡ÉXITO! Archivo generado correctamente.")
    print(f" Archivo generado: {output_path}")

if __name__ == "__main__":
    main(sys.argv)