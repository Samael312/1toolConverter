import sys
import logging
from pathlib import Path
from io import BytesIO
import pandas as pd
import pdfplumber

# ====================================================
# Configuración de logging
# ====================================================
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
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

COLUMN_MAPPING_PDF = {
    "DIRECCION": "register",
    "DIRECCIÓN": "register",
    "Nombre": "name",
    "Longitud Word Dato": "length",
    "Longitud\nWord Dato": "length",
    "Valores": "description"
}

DEFAULT_VALUES = {
    "system_category": "STATUS",
    "category": "DEFAULT",
    "view": "basic",
    "sampling": 60,
    "read": 0,
    "write": "",
    "minvalue": 0,
    "maxvalue": 0,
    "unit": "",
    "offset": 0,
    "addition": 0,
    "mask": 0,
    "value": 0,
    "general_icon": "",
    "alarm": '{"severity":"none"}',
    "metadata": "[]",
    "l10n": '{"_type":"l10n","default_lang":"en_US","translations":{"en_US":{"name":null,"_type":"languages","description":null}}}',
    "tags": "[]",
    "type": "modbus",
    "parameter_write_byte_position": 0,
    "mqtt": "",
    "json": "",
    "current_value": 0,
    "current_error_status": 0,
    "notes": ""
}

# ====================================================
# Nueva función de propagación de contexto con duplicados ID
# ====================================================
def propagate_context(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Propagando categorías basadas en duplicados de 'register' y eliminando los primeros duplicados...")

    # Normalizar columnas
    df["register"] = df["register"].astype(str).str.strip()
    df["name"] = df["name"].astype(str).str.strip()

    # Diccionarios auxiliares
    seen_registers = set()
    first_names = {}
    current_category = "DEFAULT"
    categories = []
    first_duplicate_indexes = []  # para marcar los primeros duplicados que luego se eliminarán

    for idx, row in df.iterrows():
        reg = row.get("register", "").strip()
        name = row.get("name", "").strip()

        if not reg:
            categories.append(current_category)
            continue

        # Si es la primera vez que aparece este register
        if reg not in first_names:
            first_names[reg] = name.replace(" ", "_")
            seen_registers.add(reg)
            categories.append(current_category)
            continue

        # Si este register ya apareció antes, se inicia un nuevo grupo
        if reg in seen_registers:
            current_category = first_names[reg]
            # Registrar el índice de la primera aparición para borrarlo después
            first_index = df.index[df["register"] == reg][0]
            if first_index not in first_duplicate_indexes:
                first_duplicate_indexes.append(first_index)

        categories.append(current_category)

    df["category"] = categories

    # Eliminar los primeros duplicados que sirvieron como encabezados de grupo
    df = df.drop(index=first_duplicate_indexes).reset_index(drop=True)

    logger.info(f"✅ Categorías propagadas y eliminadas {len(first_duplicate_indexes)} filas de encabezado de grupo.")
    return df



# ====================================================
# Función principal de procesamiento
# ====================================================
def process_pdf(pdf_content: bytes) -> pd.DataFrame:
    logger.info("Procesando archivo PDF con backend Keyter...")
    pdf_io = BytesIO(pdf_content)
    tablas = []

    # 1️⃣ Extraer todas las tablas del PDF
    with pdfplumber.open(pdf_io) as pdf:
        for pagina in pdf.pages:
            for tabla in pagina.extract_tables():
                df = pd.DataFrame(tabla)
                if not df.empty:
                    tablas.append(df)

    if not tablas:
        logger.warning("No se encontraron tablas válidas en el PDF.")
        return pd.DataFrame(columns=LIBRARY_COLUMNS)

    # 2️⃣ Concatenar todas las tablas antes de limpiar
    df = pd.concat(tablas, ignore_index=True)
    logger.info(f"Concatenadas {len(tablas)} tablas con {len(df)} filas totales.")

    # 3️⃣ Encabezados
    raw_headers = list(df.iloc[0])
    clean_headers = [(h if h is not None else "").strip() for h in raw_headers]

    seen = {}
    final_headers = []
    for h in clean_headers:
        if h not in seen:
            seen[h] = 0
            final_headers.append(h)
        else:
            seen[h] += 1
            final_headers.append(f"{h}_{seen[h]}")

    df.columns = final_headers
    df = df.drop(index=[0, 1, 2], errors="ignore").reset_index(drop=True)

    # 4️⃣ Mapeo de columnas
    df = df.rename(columns=COLUMN_MAPPING_PDF)

    # 5️⃣ Limpieza
    for col in ["minvalue", "maxvalue", "offset"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    for col in ["register", "name", "description", "unit"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # 6️⃣ Aplicar propagación jerárquica
    df = propagate_context(df)

    # 7️⃣ Añadir columnas faltantes
    for col in LIBRARY_COLUMNS:
        if col not in df.columns:
            df[col] = DEFAULT_VALUES.get(col, "")

    # 8️⃣ Asignar IDs y reordenar
    df["id"] = range(1, len(df) + 1)
    df = df.reindex(columns=LIBRARY_COLUMNS)

    logger.info(f"Procesamiento completado: {len(df)} filas finales.")
    return df

# ====================================================
# Script ejecutable
# ====================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python cefa.py <archivo.pdf>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])

    if not pdf_path.exists():
        print(f"❌ El archivo {pdf_path} no existe.")
        sys.exit(1)

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    df = process_pdf(pdf_bytes)

    if df is None or df.empty:
        print("⚠️ No se extrajo ninguna tabla del PDF.")
        sys.exit(0)

    print("\n✅ Primeras filas del DataFrame:")
    print(df.head())

    excel_path = pdf_path.with_suffix(".xlsx")
    df.to_excel(excel_path, index=False, engine="openpyxl")
    print(f"\n📘 Datos exportados a Excel: {excel_path}")
