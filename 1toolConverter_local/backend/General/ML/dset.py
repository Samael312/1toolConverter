import pandas as pd
import pdfplumber

def cargar_archivo(ruta):
    ruta = ruta.lower()
    
    if ruta.endswith(".xlsx") or ruta.endswith(".xls"):
        print("→ Cargando Excel...")
        return pd.read_excel(ruta)
    
    elif ruta.endswith(".html") or ruta.endswith(".htm"):
        print("→ Cargando HTML...")
        tablas = pd.read_html(ruta)
        print(f"Se encontraron {len(tablas)} tablas. Usando la primera.")
        return tablas[0]
    
    elif ruta.endswith(".csv"):
        print("→ Cargando CSV...")
        return pd.read_csv(ruta)
    
    elif ruta.endswith(".pdf"):
        print("→ Cargando PDF con pdfplumber...")
        data = []
        with pdfplumber.open(ruta) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    data.extend(table)
        
        if not data:
            raise ValueError("No se encontraron tablas en el PDF")
        
        df = pd.DataFrame(data[1:], columns=data[0])  # Primera fila como encabezado
        return df
    
    else:
        raise ValueError("Formato no soportado. Usa: xlsx, xls, html, csv o pdf.")

# === Entrada de usuario ===
ruta_fuente = input("Ruta del archivo FUENTE (Excel/HTML/PDF): ")
ruta_normalizado = input("Ruta del archivo NORMALIZADO (Excel/HTML/PDF con columnas mapeadas): ")

df_fuente = cargar_archivo(ruta_fuente)
df_norm = cargar_archivo(ruta_normalizado)

# Debe haber columnas col_name_input y label
if not {"col_name_input", "label"}.issubset(df_norm.columns):
    raise Exception("El archivo normalizado debe contener columnas: col_name_input y label")

mapeo = dict(zip(df_norm["col_name_input"], df_norm["label"]))

dataset = []

for col in df_fuente.columns:
    if col not in mapeo:
        print(f"⚠️ '{col}' no tiene etiqueta en el normalizado. Se omite.")
        continue
    
    sample_values = df_fuente[col].dropna().astype(str).head(5).tolist()
    
    dataset.append({
        "col_name_input": col,
        "sample_values": sample_values,
        "label": mapeo[col]
    })

print("\n✅ Dataset generado:\n")
from pprint import pprint
pprint(dataset)

guardar = input("\n¿Guardar resultado en JSON? (s/n): ").lower()
if guardar == "s":
    import json
    with open("dataset_generado.json", "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=4, ensure_ascii=False)
    print("💾 Guardado como dataset_generado.json")
