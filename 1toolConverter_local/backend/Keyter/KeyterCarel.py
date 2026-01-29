#!/usr/bin/env python3
"""
Backend Keyter (Adaptado): procesamiento de archivos Excel (Formato MV-BV) -> DataFrame -> Excel procesado.
Procesa hojas Analogicas, Enteras y Digitales para generar archivo final compatible.
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

def _process_specific_columns(df: pd.DataFrame) -> pd.DataFrame:
    if 'offset' in df.columns:
        df['offset'] = pd.to_numeric(
            df['offset'].astype(str).replace(['', '---', 'nan', 'None'], None),
            errors='coerce'
        ).fillna(0.0)

    if 'unit' in df.columns:
        df['unit'] = df['unit'].astype(str).replace(['0', '---', 'None', 'nan'], ' ').str.strip()

    if 'system_category' in df.columns:
        df['system_category'] = df['system_category'].astype(str).str.upper().str.strip()
        mapping = {
            'CONSIGNA': 'SET_POINT', 'E.ANALOGICA': 'ANALOG_INPUT', 'ALARMA': 'ALARM',
            'COMANDO': 'COMMAND', 'E.DIGITAL': 'DIGITAL_INPUT', 'ESTADO': 'STATUS',
            'PARAMETRO': 'CONFIG_PARAMETER', 'S.ANALOGICA': 'ANALOG_OUTPUT',
            'S.DIGITAL': 'DIGITAL_OUTPUT', 'SISTEMA': 'SYSTEM',
            'INPUT-OUTPUT': 'STATUS', 'DEFAULT': 'CONFIG_PARAMETER', 
            'ALARMS': 'ALARM', 'COMMUNICATION': 'SYSTEM',
            'INPUT': 'ANALOG_INPUT', 'OUTPUT': 'ANALOG_OUTPUT'
        }
        df['system_category'] = df['system_category'].replace(mapping)
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
            system_type = df['system_category'].astype(str).str.upper().str.strip()
            df.loc[only_read & system_type.isin(['ANALOG_INPUT', 'ANALOG_OUTPUT', 'SYSTEM', 'STATUS']), 'read'] = 3
            df.loc[only_read & system_type.isin(['ALARM']), 'read'] = 1
            df.loc[only_read & system_type.isin(['STATUS', 'DIGITAL_INPUT']), 'read'] = 4
            df.loc[only_read & system_type.isin(['COMMAND']), 'write'] = 6
            df.loc[rw & system_type.isin(['SET_POINT']), ['read', 'write']] = [3, 6]
            df.loc[rw & system_type.isin(['CONFIG_PARAMETER', 'DIGITAL_OUTPUT']), ['read', 'write']] = [1, 5]
            df.loc[rw & system_type.isin(['DIGITAL_INPUT']), 'read'] = 1
        
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
    if "system_category" not in df.columns:
        df["system_category"] = "STATUS"
    return df

def _apply_system_configuratiom(df: pd.DataFrame) -> pd.DataFrame:
    if "system_category" in df.columns:
        system_type = df['system_category'].astype(str).str.upper().str.strip()
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
        # Cargar el workbook desde bytes
        excel_io = BytesIO(excel_content)
        wb = load_workbook(excel_io, data_only=True, read_only=False)
    except Exception as e:
        logger.error(f"Error al cargar Excel desde bytes: {e}", exc_info=True)
        return None

    logger.info(f"Hojas encontradas: {wb.sheetnames!r}")

    # 1. Filtrar hojas relevantes (Lógica MV-BV)
    preferred_keywords = ["ANALOG", "ENTERAS", "DIGITAL", "ANALOGICAS", "INTEGER"]
    found = []
    
    for s in wb.sheetnames:
        if any(k in s.upper().strip() for k in preferred_keywords):
            found.append(s)

    # Fallback: si no encuentra las hojas por nombre, usa las 3 primeras
    if len(found) < 3:
        logger.warning("No se detectaron hojas estándar (Analogicas/Enteras/Digital). Usando las 3 primeras visibles.")
        found = wb.sheetnames[:3]

    logger.info(f"Hojas a procesar: {found!r}")
    processed_dfs = []

    # 2. Iterar sobre las hojas seleccionadas
    for sheet_name in found:
        try:
            ws = wb[sheet_name]
            
            # Verificar si la hoja tiene contenido suficiente
            if getattr(ws, "max_row", 0) <= header_row:
                logger.warning(f"Saltando hoja '{sheet_name}' (parece vacía).")
                continue

            # Extraer encabezados
            header_cells = list(ws[header_row])
            headers = [str(c.value).strip() if c.value else f"col_{i}" for i, c in enumerate(header_cells)]

            rows = []
            start_row = header_row + 1

            # Leer filas
            for row in ws.iter_rows(min_row=start_row, values_only=True):
                if not any(row): continue # Saltar filas totalmente vacías
                
                # Crear diccionario seguro
                row_dict = {headers[i]: row[i] for i in range(min(len(headers), len(row)))}
                row_dict["sheet_name"] = sheet_name
                rows.append(row_dict)

            df_raw = pd.DataFrame(rows)

            if df_raw.empty:
                continue

            # 3. Aplicar la lógica de transformación (MV-BV)
            # Nota: Asegúrate de que _process_dataframe esté definida en este archivo
            df_proc = _process_dataframe(df_raw)
            
            logger.info(f"-> Hoja '{sheet_name}' procesada: {len(df_proc)} filas.")
            processed_dfs.append(df_proc)

        except Exception as e:
            logger.error(f"Error procesando hoja '{sheet_name}': {e}", exc_info=True)
            continue

    if not processed_dfs:
        logger.warning("⚠ No se pudo procesar ninguna hoja correctamente.")
        return None

    # 4. Unir y finalizar
    logger.info("Unificando DataFrames...")
    df_total = pd.concat(processed_dfs, ignore_index=True)

    try:
        # Generar IDs y columnas finales
        df_total["id"] = range(1, len(df_total) + 1)
        df_total = _add_default_columns(df_total)
        
        # Asegurar todas las columnas de la librería
        for col in LIBRARY_COLUMNS:
            if col not in df_total.columns:
                df_total[col] = None
        
        df_final = df_total.reindex(columns=LIBRARY_COLUMNS)
        logger.info(f"DataFrame final generado con {len(df_final)} filas.")
        return df_final

    except Exception as e:
        logger.error(f"Error integrando DataFrame final: {e}", exc_info=True)
        return None
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

    logger.info(f"Hojas encontradas en el Excel: {wb.sheetnames!r}")

    # Filtrar hojas relevantes
    preferred_keywords = ["ANALOG", "ENTERAS", "DIGITAL", "ANALOGICAS", "INTEGER"]
    found = []
    
    for s in wb.sheetnames:
        if any(k in s.upper().strip() for k in preferred_keywords):
            found.append(s)

    if len(found) < 3:
        logger.warning("No se detectaron las 3 hojas estándar. Se intentarán usar las 3 primeras visibles.")
        found = wb.sheetnames[:3]

    logger.info(f"Hojas seleccionadas para procesar: {found!r}")
    processed_dfs = []

    # --- INICIO DEL BUCLE DE HOJAS ---
    for sheet in found:
        logger.info(f"Leyendo hoja: '{sheet}'...")
        ws = wb[sheet]
        
        if getattr(ws, "max_row", 0) <= header_row:
            logger.warning(f"-> Saltando hoja '{sheet}' porque parece vacía.")
            continue
            
        try:
            # Lectura de datos
            header_cells = list(ws[header_row])
            headers = [str(c.value).strip() if c.value else f"col_{i}" for i, c in enumerate(header_cells)]
            
            data_rows = []
            for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
                if not any(row): continue
                row_dict = {headers[i]: row[i] for i in range(min(len(headers), len(row)))}
                row_dict["sheet_name"] = sheet
                data_rows.append(row_dict)
            
            df_raw = pd.DataFrame(data_rows)

            if df_raw.empty:
                logger.warning(f"-> La hoja '{sheet}' no contenía datos válidos.")
                continue
                
            # Procesamiento
            df_proc = _process_dataframe(df_raw)
            processed_dfs.append(df_proc)
            
            # LOG DE PROGRESO CORRECTO
            logger.info(f"-> OK: Hoja '{sheet}' procesada correctamente ({len(df_proc)} filas).")
            
        except Exception as e:
            logger.error(f"-> ERROR procesando hoja '{sheet}': {e}", exc_info=True)
    # --- FIN DEL BUCLE ---

    if not processed_dfs:
        logger.error("No se pudo procesar ninguna hoja correctamente.")
        return None

    logger.info("--- Unificando datos de todas las hojas ---")
    final_df = pd.concat(processed_dfs, ignore_index=True)
    
    # Generar IDs y columnas finales
    final_df["id"] = range(1, len(final_df) + 1)
    final_df = _add_default_columns(final_df)
    
    # Asegurar estructura final
    logger.info("Aplicando estructura final de columnas...")
    for col in LIBRARY_COLUMNS:
        if col not in final_df.columns:
            final_df[col] = None
            
    logger.info(f"Proceso completado. Total filas generadas: {len(final_df)}")
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