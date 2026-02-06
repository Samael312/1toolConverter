import pandas as pd
import os
import sys
from typing import List
import logging

logger = logging.getLogger(__name__)

def obtener_encabezados(ruta_archivo, fila_indices=2):
    """
    Lee los encabezados de un Excel en una fila específica.
    fila_indices=2 corresponde a la Fila 3 de Excel.
    """
    try:
        # Cargamos el archivo completo para acceder a todas las hojas
        excel_file = pd.ExcelFile(ruta_archivo)
        
        for nombre_hoja in excel_file.sheet_names:
            # Leer solo la fila de encabezados
            # nrows=0 es ultra rápido porque no carga los datos
            df = pd.read_excel(excel_file, sheet_name=nombre_hoja, header=fila_indices, nrows=0)
            
            encabezados = df.columns.tolist()
            
            print(f"📄 HOJA: '{nombre_hoja}'")
            if not encabezados:
                print("   ⚠️ [VACÍA] No se encontraron encabezados en la fila 3.")
            else:
                # Limpiamos posibles espacios en blanco para ver el nombre real
                limpios = [f"'{str(c)}'" for c in encabezados]
                print(f"   ✅ Columnas detectadas: {', '.join(limpios)}")
                
                # Alerta específica por si aparece "Category"
                check = [c for c in encabezados if "Category" in str(c)]
                if check:
                    print(f"   🚨 ALERTA: Se encontró algo similar a Category: {check}")
            
            print("-" * 30)

    except Exception as e:
        logger.error(f"❌ Error al procesar el archivo: {e}")

# =====================================================
# MAIN
# =====================================================

def _output_path(path: str) -> str:
    base = os.path.basename(path)
    name, _ = os.path.splitext(base)
    return os.path.join(os.path.dirname(path), f"processed_{name}.xlsx")

def main(argv: List[str]):
    if len(argv) < 2:
        print("Uso: python main.py archivo.xlsx")
        sys.exit(1)

    input_path = argv[1]
    headers = obtener_encabezados(input_path)

    print(f"📂 Archivo de entrada: {input_path}")

if __name__ == "__main__":
    main(sys.argv)