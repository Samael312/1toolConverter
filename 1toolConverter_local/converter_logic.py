import pandas as pd
from pathlib import Path

def load_and_preprocess_html(html_path: str) -> pd.DataFrame:
    """
    Ejemplo simulado: genera un DataFrame de variables a partir de un HTML ficticio.
    En tu versión real, aquí iría el parseo con BeautifulSoup o pandas.read_html().
    """
    try:
        # Simulación de datos procesados
        data = {
            'register': [40001, 40002, 40003, 40004],
            'name': ['Temp01', 'Press02', 'Flow03', 'Valve04'],
            'description': ['Sensor de temperatura', 'Sensor de presión', 'Caudalímetro', 'Válvula de salida'],
            'system_category': ['', '', '', ''],
            'read': [True, True, True, False],
            'write': [False, False, False, True],
            'sampling': [1.0, 0.5, 0.2, 0.1],
        }
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        print(f"Error procesando HTML: {e}")
        return pd.DataFrame()


def export_to_excel(df: pd.DataFrame, output_filename: str) -> Path:
    """
    Exporta el DataFrame a Excel en la carpeta actual.
    """
    try:
        output_path = Path(output_filename)
        df.to_excel(output_path, index=False)
        return output_path
    except Exception as e:
        print(f"Error exportando a Excel: {e}")
        return None
