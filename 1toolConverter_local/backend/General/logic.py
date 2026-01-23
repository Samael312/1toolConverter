import re
import pandas as pd
import numpy as np

def validate_description_text(texto: str) -> bool | str:
    """Valida un texto y devuelve True o el mensaje de error."""
    if texto is None: return "El texto está vacío"
    
    cleaned = re.sub(r"[^a-zA-Z0-9\s\.,;:_\-/=%°CñÑáéíóúÁÉÍÓÚ()]", "", texto)
    if cleaned != texto: return "Caracteres no permitidos encontrados"
    if len(texto) == 0: return "La descripción no puede estar vacía"
    if len(texto) > 150: return "Máximo 150 caracteres permitidos"
    if len(texto) > 60: return "La descripción supera el límite (60)"
    
    return True

def calculate_errors(df: pd.DataFrame) -> pd.DataFrame:
    """Añade la columna error_flag al DataFrame."""
    if df is None or df.empty: return df
    
    # Usamos la función pura de arriba
    df['error_flag'] = df['description'].apply(
        lambda x: 0 if validate_description_text(x) is True else 1
    )
    return df

def auto_classify_groups(df: pd.DataFrame) -> pd.DataFrame:
        """Genera el DataFrame de agrupaciones automáticas."""
        valid_groups1 = ['ALARM', 'SET_POINT', 'CONFIG_PARAMETER', 'COMMAND', 
                        'ANALOG_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT', 
                        'STATUS', 'SYSTEM']
        valid_groups2 = ['basic', 'primary']

        auto_grouped1 = df[df['system_category'].isin(valid_groups1)]
        auto_grouped2 = df[df['view'].isin(valid_groups2)]
        
        combined = pd.concat([auto_grouped1, auto_grouped2]).drop_duplicates()
        return combined.reset_index(drop=True)