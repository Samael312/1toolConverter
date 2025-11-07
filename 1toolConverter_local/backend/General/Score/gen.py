from typing import List, Optional, Dict, Any
import sys
import os
import logging
import pandas as pd
import numpy as np
from openpyxl import load_workbook
import json
from io import BytesIO
from pathlib import Path
import pdfplumber
import re

# =====================================================
# CONFIGURACIÓN DE LOGGING
# =====================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =====================================================
# COLUMNAS DE REFERENCIA
# =====================================================
LIBRARY_COLUMNS = [
    "id", "register", "name", "description", "system_category", "category", "view",
    "sampling", "read", "write", "minvalue", "maxvalue", "unit", "offset",
    "addition", "mask", "value", "length", "general_icon", "alarm", "metadata",
    "l10n", "tags", "type", "parameter_write_byte_position", "mqtt", "json",
    "current_value", "current_error_status", "notes"
]

# =====================================================
# CARGA DE REGLAS DESDE JSON
# =====================================================
def load_column_rules(path: Path) -> Dict[str, Any]:
    """Carga las reglas de detección desde un archivo JSON."""
    if not path.exists():
        logger.error(f"No se encontró el archivo de reglas: {path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        try:
            rules = json.load(f)
            logger.info(f"Se cargaron {len(rules)} reglas de detección desde {path.name}")
            return rules
        except json.JSONDecodeError as e:
            logger.error(f"Error al leer JSON de reglas: {e}")
            sys.exit(1)

# =====================================================
# SCORING DE COLUMNAS
# =====================================================
def score_column(series: pd.Series, rule: Dict[str, Any]) -> float:
    """Devuelve un score (float) de qué tan bien la serie cumple la regla."""
    sample = series.dropna().astype(str).head(200)
    if sample.empty:
        return 0.0

    score = 0.0

    # Tipo: si la mayoría son numéricos y la regla lo pide
    if "int" in rule.get("type", []) or "float" in rule.get("type", []):
        num_ratio = pd.to_numeric(sample.str.replace(",", "."), errors="coerce").notnull().mean()
        score += 2.0 * num_ratio

    if "str" in rule.get("type", []):
        str_ratio = sample.apply(lambda x: isinstance(x, str)).mean()
        score += 1.0 * str_ratio

    # Patrones
    pattern_score = 0.0
    for pat in rule.get("pattern", []):
        try:
            match_ratio = sample.str.match(pat).mean()
            pattern_score = max(pattern_score, match_ratio)
        except Exception:
            continue

    # Penalizar si la regla es 'maxvalue' y hay valores negativos
    if 'maxvalue' in rule.get('name', '').lower() or 'maxvalue' in rule.get('label', '').lower():
        neg_ratio = sample.str.startswith('-').mean()
        pattern_score -= neg_ratio * 0.5  # penaliza columnas con valores negativos

    score += pattern_score * 3.0

    # Longitud
    avg_len = sample.str.len().mean()
    if "min_length" in rule and avg_len >= rule["min_length"]:
        score += 0.3
    if "max_length" in rule and avg_len <= rule["max_length"]:
        score += 0.3

    return float(score)

# =====================================================
# DETECCIÓN DE COLUMNAS (ITERATIVA, SIN DUPLICADOS)
# =====================================================
def detect_all_columns(df: pd.DataFrame, rules: Dict[str, Any], verbose: bool = True) -> Dict[str, str]:
    """
    Asigna nombres a columnas del DataFrame siguiendo una estrategia jerárquica:
    1. Asignaciones prioritarias con alta confianza.
    2. Asignaciones generales con umbral medio.
    3. Si no hay coincidencia, usa 'description_N'.
    """
    cols = list(df.columns)
    mapping: Dict[str, str] = {}
    assigned_target = set()

    priority_order = [
    "ReadWrite", "unit", "register",
    "system_category", "maxvalue","minvalue", "name"
]

    general_rules = [r for r in rules.keys() if r not in priority_order]
    ordered_rules = priority_order + general_rules

    HIGH_THRESHOLD = 1.5
    LOW_THRESHOLD = 1.0

    # Paso 1: asignaciones de alta confianza
    for c in cols:
        best_rule, best_score = None, 0.0
        for rule_name in ordered_rules:
            if rule_name in assigned_target:
                continue
            score = score_column(df[c], rules[rule_name])
            if score > best_score:
                best_score = score
                best_rule = rule_name
        if best_rule and best_score >= HIGH_THRESHOLD:
            mapping[c] = best_rule
            assigned_target.add(best_rule)
            if verbose:
                logger.info(f"[ALTA] Columna '{c}' -> '{best_rule}' (score={best_score:.2f})")

    # Paso 2: asignaciones con umbral medio
    for c in cols:
        if c in mapping:
            continue
        best_rule, best_score = None, 0.0
        for rule_name in ordered_rules:
            score = score_column(df[c], rules[rule_name])
            if score > best_score:
                best_score = score
                best_rule = rule_name

        if best_rule and best_score >= LOW_THRESHOLD:
            target_name = best_rule
            if target_name in assigned_target:
                idx = 1
                while f"{target_name}_{idx}" in assigned_target:
                    idx += 1
                target_name = f"{target_name}_{idx}"
            mapping[c] = target_name
            assigned_target.add(target_name)
            if verbose:
                logger.info(f"[MEDIA] Columna '{c}' -> '{target_name}' (score={best_score:.2f})")
        else:
            fallback = "description"
            idx = 1
            while f"{fallback}_{idx}" in assigned_target:
                idx += 1
            fallback_name = f"{fallback}_{idx}"
            mapping[c] = fallback_name
            assigned_target.add(fallback_name)
            if verbose:
                logger.info(f"[FALLBACK] Columna '{c}' -> '{fallback_name}' (score={best_score:.2f})")

    return mapping

# =====================================================
# PROCESADORES DE ARCHIVOS
# =====================================================
def process_excel(file_content: bytes) -> Optional[pd.DataFrame]:
    """Procesa todas las hojas de un archivo Excel."""
    logger.info("Procesando archivo Excel desde contenido en memoria...")
    file_io = BytesIO(file_content)
    all_sheets = []

    try:
        xls = pd.ExcelFile(file_io)
        for sheet in xls.sheet_names:
            try:
                df = pd.read_excel(xls, sheet_name=sheet)
                if not df.empty:
                    df["sheet_name"] = sheet
                    all_sheets.append(df)
            except Exception as e:
                logger.warning(f"No se pudo leer la hoja '{sheet}': {e}")

        if not all_sheets:
            return pd.DataFrame(columns=LIBRARY_COLUMNS)

        return pd.concat(all_sheets, ignore_index=True)

    except Exception as e:
        logger.error(f"Error al cargar Excel: {e}", exc_info=True)
        return None


def process_pdf(file_content: bytes) -> Optional[pd.DataFrame]:
    """Procesa todas las tablas encontradas en un PDF."""
    logger.info("Procesando archivo PDF...")
    file_io = BytesIO(file_content)
    tablas = []

    try:
        with pdfplumber.open(file_io) as pdf:
            for i, pagina in enumerate(pdf.pages, start=1):
                tablas_pagina = pagina.extract_tables()
                if not tablas_pagina:
                    continue
                for tabla in tablas_pagina:
                    df = pd.DataFrame(tabla)
                    if not df.empty:
                        df["page"] = i
                        tablas.append(df)
        if not tablas:
            return pd.DataFrame(columns=LIBRARY_COLUMNS)
        return pd.concat(tablas, ignore_index=True)

    except Exception as e:
        logger.error(f"Error al procesar PDF: {e}", exc_info=True)
        return None


def process_data(file_content: bytes, filename: str) -> Optional[pd.DataFrame]:
    """Detecta el tipo de archivo y lo procesa."""
    logger.info("Procesando archivo...")
    ext = os.path.splitext(filename)[1].lower()

    try:
        if ext in [".xls", ".xlsx", ".xlsm"]:
            return process_excel(file_content)
        elif ext == ".pdf":
            return process_pdf(file_content)
        elif ext in [".html", ".htm"]:
            tables = pd.read_html(BytesIO(file_content), header=0)
            return tables[0] if tables else None
        else:
            logger.error(f"Formato no soportado: {ext}")
            return None
    except Exception as e:
        logger.error(f"Error al procesar el archivo: {e}", exc_info=True)
        return None

# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python gen.py <archivo.formato>")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"❌ El archivo {file_path} no existe.")
        sys.exit(1)

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    df = process_data(file_bytes, file_path.name)

    if df is None or df.empty:
        print("⚠️ No se extrajo ningún dato del archivo.")
        sys.exit(0)

    print("\n✅ Primeras filas del DataFrame combinado:")
    print(df.head())

    # Detectar columnas
    rules_path = Path(__file__).with_name("column_rules.json")
    COLUMN_RULES = load_column_rules(rules_path)

    mapping = detect_all_columns(df, COLUMN_RULES, verbose=True)
    df = df.rename(columns=mapping)

    print("\n✅ Columnas detectadas y renombradas:")
    print(df.columns.tolist())

    # Exportar
    output_name = f"{file_path.stem}_processed.xlsx"
    excel_path = file_path.with_name(output_name)
    df.to_excel(excel_path, index=False, engine="openpyxl")

    print(f"\n📘 Datos exportados a Excel: {excel_path}")
