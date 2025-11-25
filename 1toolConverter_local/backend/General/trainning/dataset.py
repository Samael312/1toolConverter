import pandas as pd
from sklearn.model_selection import train_test_split
import random
import sys

def generar_sinteticos_range(base_ranges, n):
    sinteticos = []
    for _ in range(n):
        if base_ranges:
            r = random.choice(base_ranges)
            parts = str(r).split()
            if len(parts) == 2 and all(p.replace("-", "").replace(".", "").isdigit() for p in parts):
                start = float(parts[0]) + random.uniform(-10, 10)
                end = float(parts[1]) + random.uniform(-10, 10)
                sinteticos.append(f"{start:.1f} {end:.1f}")
        else:
            start = random.uniform(-100, 100)
            end = start + random.uniform(1, 200)
            sinteticos.append(f"{start:.1f} {end:.1f}")
    return sinteticos

def generar_sinteticos_length(n):
    options = ["8bit", "16bit", "32bit", "64bit", "128bit"]
    return random.choices(options, k=n)

def generar_sinteticos_offset(n):
    offsets = [round(random.uniform(-50, 50), 2) for _ in range(n)]
    return [str(o) for o in offsets]

def construir_dataset(excel_file):
    df_excel = pd.read_excel(excel_file)
    target_rows = len(df_excel)  # 554 filas aproximadamente
    data = []

    # --- REGISTER ---
    if "REGISTER" in df_excel.columns:
        for val in df_excel["REGISTER"].dropna():
            data.append({"text": str(val), "label": "REGISTER"})

    # --- UNIT ---
    if "UNIT" in df_excel.columns:
        for val in df_excel["UNIT"].dropna():
            data.append({"text": str(val), "label": "UNIT"})

    # --- RANGE ---
    base_ranges = []
    if "RANGE" in df_excel.columns:
        for val in df_excel["RANGE"].dropna():
            data.append({"text": str(val), "label": "RANGE"})
            data.append({"text": str(val).replace(" ", "/"), "label": "RANGE"})
            base_ranges.append(val)
    # Generar sintéticos hasta completar filas
    n_range = max(target_rows // 8, 20)  # aprox. 1/8 del dataset
    for r in generar_sinteticos_range(base_ranges, n=n_range):
        data.append({"text": r, "label": "RANGE"})

    # --- PERMISSION ---
    permissions_base = ["R/W", "R", "W"]
    if "PERMISSION" in df_excel.columns:
        permissions_base += df_excel["PERMISSION"].dropna().tolist()
    n_perm = max(target_rows // 8, 20)
    for _ in range(n_perm):
        p = random.choice(permissions_base)
        data.append({"text": str(p), "label": "PERMISSION"})

    # --- LENGTH ---
    lengths_base = ["16bit", "32bit"]
    if "LENGTH" in df_excel.columns:
        lengths_base += df_excel["LENGTH"].dropna().tolist()
    n_length = max(target_rows // 8, 20)
    for _ in range(n_length):
        l = random.choice(lengths_base + generar_sinteticos_length(5))
        data.append({"text": l, "label": "LENGTH"})

    # --- OFFSET ---
    offset_vals = []
    if "OFFSET" in df_excel.columns:
        for val in df_excel["OFFSET"].dropna():
            data.append({"text": str(val), "label": "OFFSET"})
            offset_vals.append(val)
    n_offset = max(target_rows // 8, 20)
    for o in generar_sinteticos_offset(n_offset):
        data.append({"text": o, "label": "OFFSET"})

    # --- DESCRIPTION ---
    if "DESCRIPTION" in df_excel.columns:
        for val in df_excel["DESCRIPTION"].dropna():
            data.append({"text": str(val), "label": "DESCRIPTION"})

    # --- VAR ---
    if "VAR" in df_excel.columns:
        for val in df_excel["VAR"].dropna():
            data.append({"text": str(val), "label": "VAR"})

    # --- Convertir a DataFrame ---
    df = pd.DataFrame(data)
    df.dropna(inplace=True)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    # --- Dividir en train/val (80/20) ---
    train_df, val_df = train_test_split(df, test_size=0.2, random_state=42)
    train_df.to_csv("train.csv", index=False)
    val_df.to_csv("val.csv", index=False)

    print(f"Total filas dataset: {len(df)}")
    print("Train CSV preview:")
    print(train_df.head())
    print("\nValidation CSV preview:")
    print(val_df.head())

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ruta_excel = sys.argv[1]
    else:
        ruta_excel = "datos.xlsx"
        print(f"⚠️  Aviso: No se indicó archivo, se usa {ruta_excel}")

    construir_dataset(ruta_excel)
