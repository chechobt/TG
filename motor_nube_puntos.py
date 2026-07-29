# ===================================================================
# MOTOR DE PROCESAMIENTO DE NUBES DE PUNTOS
# Desarrollado para Geoportal Web (GeoPol)
# Se encarga de leer, limpiar y emparejar columnas de archivos TXT/CSV
# ===================================================================
import pandas as pd
import numpy as np

def procesar_archivo_nube(archivo):
    """
    Lee un archivo TXT o CSV y devuelve un DataFrame limpio.
    Utiliza el motor 'python' y sep=None para autodetectar si el 
    archivo está separado por comas, tabuladores o puntos y comas.
    """
    try:
        df = pd.read_csv(archivo, sep=None, engine='python')
        return df
    except Exception as e:
        raise ValueError(f"No se pudo leer el archivo. Verifique el formato. Detalle: {e}")

def asignar_columnas(df, col_punto, col_este, col_norte, col_z, col_desc):
    """
    Recibe el DataFrame bruto y los nombres de las columnas seleccionadas
    por el usuario, devolviendo un DataFrame estandarizado para Folium.
    """
    df_clean = pd.DataFrame()
    
    # Si el usuario no selecciona columna de punto, autogeneramos un ID
    df_clean['Punto'] = df[col_punto] if col_punto else np.arange(1, len(df) + 1)
    
    # Coordenadas obligatorias
    df_clean['Este'] = pd.to_numeric(df[col_este], errors='coerce')
    df_clean['Norte'] = pd.to_numeric(df[col_norte], errors='coerce')
    
    # Cota opcional (si no hay, asumimos 0)
    df_clean['Cota'] = pd.to_numeric(df[col_z], errors='coerce') if col_z else 0.0
    
    # Descripción opcional
    df_clean['Descripcion'] = df[col_desc] if col_desc else "Punto Topográfico"
    
    # Limpieza de seguridad: Eliminar filas donde Este o Norte estén vacíos
    df_clean = df_clean.dropna(subset=['Este', 'Norte'])
    
    return df_clean