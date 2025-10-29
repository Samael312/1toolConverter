import pdfplumber
import pandas as pd
import os

def pdf_to_excel(pdf_path: str, x1_max: float = 450, min_rows: int = 5):
    print(f"📄 Leyendo tablas desde: {pdf_path} ...")
    valid_tables = []
    reference_columns = None  # Guardará la estructura estándar

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            print(f"\n🔍 Analizando página {page_number}...")
            for table_obj in page.find_tables():
                x0, y0, x1, y1 = table_obj.bbox
                raw_table = table_obj.extract()

                if not raw_table or len(raw_table) < 2:
                    print("🗑 Descartada (estructura inválida)")
                    continue

                # Convertir a DataFrame
                df = pd.DataFrame(raw_table[1:], columns=raw_table[0])

                # Descartar por posición
                if x1 > x1_max:
                    print(f"🗑 Descartada (muy a la derecha): x1={x1:.2f}")
                    continue

                # Descartar por tamaño
                if df.shape[0] < min_rows:
                    print(f"🗑 Descartada (muy pequeña: {df.shape[0]} filas)")
                    continue

                # Limpiar encabezados y eliminar duplicados
                df.columns = df.columns.str.strip()
                df = df.loc[:, ~df.columns.duplicated()]

                # Establecer columnas de referencia la primera vez
                if reference_columns is None:
                    reference_columns = df.columns.tolist()
                    print(f"✅ Estableciendo columnas de referencia: {reference_columns}")
                    valid_tables.append(df)
                else:
                    # Si el número de columnas coincide, ajustar encabezados
                    if len(df.columns) == len(reference_columns):
                        print(f"📎 Coinciden columnas en cantidad. Ajustando encabezados de página {page_number}...")
                        df.columns = reference_columns
                        valid_tables.append(df)
                    else:
                        print(f"🗑 Descartada (número de columnas diferente: {len(df.columns)})")

    if not valid_tables:
        print("⚠ No se detectaron tablas válidas.")
        return

    final_df = pd.concat(valid_tables, ignore_index=True)

    output_path = os.path.splitext(pdf_path)[0] + "_filtrado.xlsx"
    final_df.to_excel(output_path, index=False)
    print(f"\n✅ Archivo Excel generado: {output_path}")

if __name__ == "__main__":
    pdf_to_excel("cefa.pdf", x1_max=450, min_rows=5)
