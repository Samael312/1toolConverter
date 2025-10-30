import pdfplumber
import pandas as pd
import os
from io import BytesIO
from typing import Optional, List

# ============================================
# Configuración de columnas y valores por defecto
# ============================================

COLUMN_MAPPING_PDF = {
    0: "register",
    1: "name",
    2: "description",
    3: "unit",
    4: "minvalue",
    5: "maxvalue",
    6: "offset",
    7: "system_category",
}

LIBRARY_COLUMNS = [
    "id",
    "register",
    "name",
    "description",
    "unit",
    "minvalue",
    "maxvalue",
    "offset",
    "system_category"
]

DEFAULT_VALUES = {
    "unit": "",
    "minvalue": 0,
    "maxvalue": 0,
    "offset": 0,
    "system_category": "DEFAULT"
}

# ============================================
# Función principal
# ============================================

def process_pdf(pdf_content: bytes) -> Optional[pd.DataFrame]:
    """
    Procesa un PDF y devuelve un DataFrame con lógica Keyter completa.
    """
    print("Procesando archivo PDF con backend Keyter...")
    pdf_io = BytesIO(pdf_content)

    try:
        tablas: List[pd.DataFrame] = []
        tabla_contador = 0

        with pdfplumber.open(pdf_io) as pdf:
            for pagina in pdf.pages:
                page_tables = pagina.extract_tables()
                for tabla in page_tables:
                    df = pd.DataFrame(tabla)
                    if not df.empty:
                        # Solo primera tabla elimina filas 1,2,3
                        if tabla_contador == 0:
                            df = df.drop(index=[1, 2, 3], errors='ignore').reset_index(drop=True)

                        # Renombrar columnas
                        df.rename(columns=COLUMN_MAPPING_PDF, inplace=True)

                        # Eliminar columnas no deseadas
                        for col in ["modo", "direccion plc"]:
                            if col in df.columns:
                                df.drop(columns=[col], inplace=True)

                        # Limpiar tipos numéricos
                        for col in ["minvalue", "maxvalue", "offset"]:
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

                        # Limpiar strings
                        for col in ["register", "name", "description", "unit"]:
                            if col in df.columns:
                                df[col] = df[col].astype(str).str.strip()

                        tablas.append(df)
                        tabla_contador += 1

        if not tablas:
            print("⚠️ No se encontraron tablas válidas en el PDF.")
            return pd.DataFrame(columns=LIBRARY_COLUMNS)

        df_final = pd.concat(tablas, ignore_index=True)

        # Agregar columnas faltantes con valores por defecto
        for col in LIBRARY_COLUMNS:
            if col not in df_final.columns:
                df_final[col] = DEFAULT_VALUES.get(col, "")

        # Asignar IDs
        df_final["id"] = range(1, len(df_final) + 1)

        # Reordenar columnas
        df_final = df_final.reindex(columns=LIBRARY_COLUMNS)

        print(f"✅ Procesamiento completado: {len(df_final)} filas.")
        return df_final

    except Exception as e:
        print(f"❌ Error procesando PDF Keyter: {e}")
        return None


# ============================================
# Ejemplo de uso con archivo local
# ============================================

def pdf_to_excel(pdf_path: str):
    """
    Convierte un PDF local a Excel usando process_pdf.
    """
    with open(pdf_path, "rb") as f:
        pdf_content = f.read()

    df = process_pdf(pdf_content)
    if df is not None and not df.empty:
        output_path = os.path.splitext(pdf_path)[0] + "_filtrado.xlsx"
        df.to_excel(output_path, index=False)
        print(f"📁 Archivo Excel generado: {output_path}")
    else:
        print("⚠️ No se generó ningún Excel (PDF vacío o error).")


if __name__ == "__main__":
    pdf_to_excel("cefa.pdf")
