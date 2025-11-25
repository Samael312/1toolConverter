from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import pandas as pd
import joblib
import tempfile
from io import BytesIO
import pdfplumber
import numpy as np

# === Cargar modelos entrenados ===
clf = joblib.load("cell_type_classifier.pkl")
embedder = joblib.load("sentence_embedder.pkl")

LIBRARY_COLUMNS = [
    "id", "register", "name", "description", "system_category", "category", "view",
    "sampling", "read", "write", "minvalue", "maxvalue", "unit", "offset",
    "addition", "mask", "value", "length", "general_icon", "alarm", "metadata",
    "l10n", "tags", "type", "parameter_write_byte_position", "mqtt", "json",
    "current_value", "current_error_status", "notes"
]

app = FastAPI(title="Keyter Backend Universal")

# === Funciones auxiliares ===
def predecir_tipo_celda(texto: str) -> str:
    emb = embedder.encode([str(texto)])
    return clf.predict(emb)[0]

def cargar_archivo(file: UploadFile) -> pd.DataFrame:
    ext = file.filename.lower()
    if ext.endswith((".xlsx", ".xls")):
        return pd.read_excel(file.file)
    elif ext.endswith((".html", ".htm")):
        return pd.read_html(file.file)[0]
    elif ext.endswith(".pdf"):
        data = []
        with pdfplumber.open(file.file) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    data.extend(table)
        if not data:
            raise ValueError("No se encontraron tablas en el PDF")
        return pd.DataFrame(data[1:], columns=data[0])
    else:
        raise ValueError("Formato no soportado. Usa .xlsx, .xls, .html, .htm o .pdf")

def construir_library_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recorre cada celda del DataFrame y asigna tipo de celda mediante el clasificador.
    Construye un DataFrame final con LIBRARY_COLUMNS.
    """
    final_rows = []
    for idx, row in df.iterrows():
        for col in df.columns:
            value = row[col]
            if pd.isna(value) or str(value).strip() == "":
                continue
            tipo_celda = predecir_tipo_celda(str(value))
            new_row = {c: "" for c in LIBRARY_COLUMNS}
            new_row["id"] = len(final_rows) + 1
            new_row["name"] = col
            new_row["register"] = ""
            new_row["description"] = str(value)
            new_row["system_category"] = tipo_celda
            # Opcional: asignar category según tipo de celda
            new_row["category"] = tipo_celda
            final_rows.append(new_row)
    return pd.DataFrame(final_rows)

# === Endpoint FastAPI ===
@app.post("/procesar_archivo/")
async def procesar_archivo(file: UploadFile = File(...)):
    # Cargar archivo de entrada
    df_fuente = cargar_archivo(file)

    # Construir DataFrame final con LIBRARY_COLUMNS
    df_final = construir_library_columns(df_fuente)

    # Guardar temporalmente y devolver como descarga
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    df_final.to_excel(tmp_file.name, index=False)
    tmp_file.close()
    return FileResponse(tmp_file.name, filename="procesado_final.xlsx",
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
