import pandas as pd

# Datos procesados en el turno anterior
data = [
    "Modo rotación bombas",
    "Banda punto de rocío",
    "Corrección batería",
    "Corrección temp. ventilador",
    "Intervalo rotación (horas)",
    "Caudal máximo",
    "Humedad máxima",
    "Ctrl. prop. bombas (Max)",
    "Regulación ventilador (Max)",
    "Caudal mínimo",
    "Caudal mín. apertura válvula",
    "Humedad mínima",
    "Ctrl. prop. bombas (Max)",
    "Regulación ventilador (Min)",
    "Límite alarmas bombas",
    "Límite alarmas chiller",
    "Temp. máxima chiller",
    "Temp. mínima chiller",
    "Consigna secundaria",
    "Paso velocidad ventilador",
    "Retardo temporizador",
    "Tipo sonda caudal",
    "Tipo sonda humedad",
    "Unidades punto rocío",
    "PID: Derivativo",
    "PID Vent.: Derivativo",
    "PID: Integral",
    "PID Vent.: Integral",
    "PID: Proporcional",
    "PID Vent.: Proporcional",
    "PID: Rampa",
    "PID Vent.: Rampa"
]

# Crear DataFrame
df = pd.DataFrame(data, columns=["Descripción UI Corta"])

# Guardar a Excel
file_path = "descripciones_ui.xlsx"
df.to_excel(file_path, index=False)

file_path