from typing import List, Optional, Dict, Any
import sys
import os
import logging
import pandas as pd
import numpy as np
from openpyxl import load_workbook
import json
from io import BytesIO
from typing import Optional, List
import pdfplumber
from pathlib import Path
import re


# =====================================================
# CONFIGURACIÓN DE LOGGING
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ====================================================
# Constantes
# ====================================================
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
# DETECCIÓN DE COLUMNA
# =====================================================

def detect_column_type(series: pd.Series, rules: Dict[str, Any]) -> str:
    """Intenta identificar a qué columna pertenece una serie según las reglas."""
    sample = series.dropna().astype(str).head(50)
    scores = {}

    for col_name, rule in rules.items():
        score = 0

        # Evaluar tipo de dato (numérico o texto)
        if "int" in rule.get("type", []) and pd.to_numeric(sample, errors="coerce").notnull().mean() > 0.8:
            score += 2
        if "float" in rule.get("type", []) and pd.to_numeric(sample, errors="coerce").notnull().mean() > 0.8:
            score += 2
        if "str" in rule.get("type", []) and sample.apply(lambda x: isinstance(x, str)).mean() > 0.8:
            score += 1

        # Evaluar patrones
        for pat in rule.get("pattern", []):
            try:
                match_ratio = sample.str.match(pat).mean()
                score += match_ratio * 2
            except Exception:
                continue

        # Longitud promedio
        avg_len = sample.str.len().mean()
        if "min_length" in rule and avg_len >= rule["min_length"]:
            score += 1
        if "max_length" in rule and avg_len <= rule["max_length"]:
            score += 1

        scores[col_name] = score

    best_match = max(scores, key=scores.get)
    return best_match


# =====================================================
# PROCESADORES DE ARCHIVOS
# =====================================================

def process_html(file_content: bytes) -> Optional[pd.DataFrame]:
    logger.info("Procesando archivo HTML desde contenido en memoria...")
    file_io = BytesIO(file_content)

    try:
        tables: List[pd.DataFrame] = pd.read_html(file_io, header=0, flavor='bs4')
        logger.info(f"Se encontraron {len(tables)} tablas en el HTML.")
        return tables[0] if tables else None
    except Exception as e:
        logger.error(f"Error al leer HTML: {e}", exc_info=True)
        return None


def process_excel(file_content: bytes) -> Optional[pd.DataFrame]:
    logger.info("Procesando archivo Excel desde contenido en memoria...")
    file_io = BytesIO(file_content)

    try:
        xls = pd.ExcelFile(file_io)
        df = pd.read_excel(xls, xls.sheet_names[0])
        return df
    except Exception as e:
        logger.error(f"Error al cargar Excel desde bytes: {e}", exc_info=True)
        return None


def process_pdf(file_content: bytes) -> Optional[pd.DataFrame]:
    logger.info("Procesando archivo PDF...")
    file_io = BytesIO(file_content)
    tablas = []

    with pdfplumber.open(file_io) as pdf:
        for pagina in pdf.pages:
            for tabla in pagina.extract_tables():
                df = pd.DataFrame(tabla)
                if not df.empty:
                    tablas.append(df)

    if not tablas:
        logger.warning("No se encontraron tablas válidas en el PDF.")
        return pd.DataFrame(columns=LIBRARY_COLUMNS)

    return tablas[0]


def process_data(file_content: bytes, filename: str) -> Optional[pd.DataFrame]:
    logger.info("Procesando archivo desde contenido en memoria...")
    ext = os.path.splitext(filename)[1].lower()

    try:
        if ext in [".html", ".htm"]:
            return process_html(file_content)
        elif ext in [".xls", ".xlsx", ".xlsm"]:
            return process_excel(file_content)
        elif ext in [".pdf"]:
            return process_pdf(file_content)
        else:
            logger.error(f"Formato no soportado: {ext}")
            return None
    except Exception as e:
        logger.error(f"Error al procesar el archivo: {e}", exc_info=True)
        return None


# ====================================================
# Script ejecutable
# ====================================================

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

    print("\n✅ Primeras filas del DataFrame original:")
    print(df.head())

    # =====================================================
    # Detección automática de columnas
    # =====================================================
    rules_path = Path(__file__).with_name("column_rules.json")
    COLUMN_RULES = load_column_rules(rules_path)

    mapping = {}
    for col in df.columns:
        best_match = detect_column_type(df[col], COLUMN_RULES)
        mapping[col] = best_match
        logger.info(f"Columna '{col}' detectada como '{best_match}'")

    df = df.rename(columns=mapping)

    print("\n✅ Columnas detectadas y renombradas:")
    print(df.columns.tolist())

    # =====================================================
    # Exportar a Excel
    # =====================================================
    excel_path = file_path.with_suffix(".xlsx")
    df.to_excel(excel_path, index=False, engine="openpyxl")
    print(f"\n📘 Datos exportados a Excel: {excel_path}")
