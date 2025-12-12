import pandas as pd
import sys
import os

def analizar_excel(ruta_archivo):
    # Verificamos antes si el archivo existe para dar un error más claro
    if not os.path.exists(ruta_archivo):
        print(f"❌ Error: No se encuentra el archivo '{ruta_archivo}' en esta carpeta.")
        print(f"📂 Carpeta actual: {os.getcwd()}")
        return

    try:
        print(f"🔄 Cargando archivo: {ruta_archivo} ...")
        # Cargar el archivo Excel
        df = pd.read_excel(ruta_archivo, engine='openpyxl')
        
        print(f"✅ Archivo cargado exitosamente.")
        print("=" * 60)

        for col in df.columns:
            tipo_dato = df[col].dtype
            # Obtener top 5 valores más frecuentes
            ejemplos = df[col].value_counts().head(5).index.tolist()

            print(f"📌 Columna: {col}")
            print(f"   • Tipo de dato: {tipo_dato}")
            print(f"   • Ejemplos: {ejemplos}")
            print("-" * 60)

    except Exception as e:
        print(f"❌ Error procesando el Excel: {e}")

if __name__ == "__main__":
    # Lógica para leer argumentos de la terminal
    if len(sys.argv) > 1:
        # El usuario escribió: python c_ext.py archivo.xlsx
        ruta = sys.argv[1]
        analizar_excel(ruta)
    else:
        # El usuario NO escribió nada, usamos un valor por defecto o avisamos
        print("⚠️  Aviso: No indicaste ningún archivo.")
        print("   Uso correcto: python c_ext.py <nombre_del_archivo.xlsx>")