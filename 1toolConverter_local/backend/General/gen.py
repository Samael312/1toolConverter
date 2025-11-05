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
import pandas as pd
from openpyxl import load_workbook
import pdfplumber
from pathlib import Path


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
    "current_value", "current_error_status", "notes"]

# =====================================================
# LECTURA DE VALORES
# =====================================================

def process_data(file_content: bytes, filename:str) -> Optional[pd.DataFrame]:
    logger.info("Procesando archivo desde contenido en memoria (todas las hojas)...")
    file_io = BytesIO(file_content)
    ext = os.path.splitext(filename)[1].lower()

    try:
        if ext in [".html", "htm"]:
           return process_html(file_content= file_content)
        elif ext in [".xls", ".xlsx", ".xlsm"]:
            return process_excel(file_content=file_content)
        elif ext in [".pdf"]:
            return process_pdf(file_content=file_content)
    
    except Exception as e:
        logger.error(f"Error al cargar el archivo desde bytes: {e}", exc_info=True)
        return None

def process_html(file_content: bytes) -> Optional[pd.DataFrame]:
    logger.info("Procesando archivo desde contenido en memoria (todas las hojas)...")
    file_io = BytesIO(file_content)

    try:
        tables:List[pd.DataFrame] = pd.read_html(file_io, header=0, flavor='bs4')
        logger.info(f"Se encontraron {len(tables)} tablas en el HTML.")
    except Exception as e:
        logger.error(f"Error al leer HTML: {e}", exc_info=True)
        return None

def process_excel(file_content: bytes) -> Optional[pd.DataFrame]:
    logger.info("Procesando archivo Excel desde contenido en memoria (todas las hojas)...")
    file_io = BytesIO(file_content)

    try:
        wb = load_workbook(file_io, data_only=True, read_only=False, keep_vba=True)
    except Exception as e:
        logger.error(f"Error al cargar Excel desde bytes: {e}", exc_info=True)
    return None

def process_pdf(file_content: bytes) -> pd.DataFrame:
    logger.info("Procesando archivo PDF con backend Keyter...")
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

    df = process_pdf(file_bytes)

    if df is None or df.empty:
        print("⚠️ No se extrajo ningun dato del archivo.")
        sys.exit(0)

    print("\n✅ Primeras filas del DataFrame:")
    print(df.head())

    excel_path = file_path.with_suffix(".xlsx")
    df.to_excel(excel_path, index=False, engine="openpyxl")
    print(f"\n📘 Datos exportados a Excel: {excel_path}")