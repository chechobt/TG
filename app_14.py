# ===================================================================
# GEOPORTAL WEB - VERSIÓN 14.0
# Novedades frente a la 13.0:
# 1. Ficha Técnica del Levantamiento: formulario donde el usuario
#    registra proyecto, localización, cuadrilla, equipo y parámetros
#    de cálculo. Alimenta los informes LaTeX.
# 2. Aislamiento por sesión: cada usuario trabaja en su propio
#    directorio, evitando que dos usuarios concurrentes se pisen los
#    planos y las fotografías.
# 3. Caché de PDF invalidada por contenido real de las figuras.
# 4. Corrección de errores de arranque, de índices y de fugas de memoria.
# ===================================================================
import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import os
import base64
import pickle
import hashlib
import math
import uuid
from datetime import datetime, date
from streamlit_geolocation import streamlit_geolocation
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import numpy as np
import glob

# Importación de los Motores
from motor_v2_5 import poligonal_3d_v2_5, decimal_a_dms
from motor_abierta import poligonal_abierta_control
from motor_altimetria import calcular_cartera_nivelacion
from motor_proyecciones import MotorCoordenadasIGAC_V2
from motor_volumenes import generar_malla_vacia, calcular_cotas_seccion, calcular_cubicaje_total
from motor_grafico_poligonal import generar_plano_profesional
from motor_exportacion import generar_kml, generar_dxf, generar_shp_zip
from motor_informes import (generar_reporte_poligonal_latex, generar_reporte_volumenes_latex,
                            generar_reporte_nivelacion_latex, compilar_latex_a_pdf,
                            ORDENES_NIVELACION, FACTORES_MATERIAL, diagnostico_latex,
                            dms_a_segundos)
from motor_nube_puntos import procesar_archivo_nube, asignar_columnas
from modulo_fotos import guardar_foto_estampada

st.set_page_config(page_title="GeoPol Web | Topografía", layout="wide", page_icon="🌍")

# ===================================================================
# CONSTANTES GLOBALES Y UTILIDADES DE SESIÓN
# ===================================================================
VERSION_APP = "GeoPol Web 14.0"
AUTORES = ["Kevin Stiven Cubillos Ramirez", "Sergio Eduardo Barbosa Torres"]
TUTOR = "Ing. Edgar Ladino"

# Antes estaba duplicado en el módulo de nubes y en el de poligonales
OPCIONES_MAPA = {
    "🛰️ ESRI Satélite (Alta Resolución)": {"tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", "attr": "Esri"},
    "🌍 Google Híbrido (Satélite + Calles)": {"tiles": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", "attr": "Google"},
    "🗺️ OpenStreetMap (Clásico)": {"tiles": "OpenStreetMap", "attr": None},
    "🌙 Modo Oscuro (CartoDB)": {"tiles": "CartoDB dark_matter", "attr": None}
}

FICHA_POR_DEFECTO = {
    "nombre_proyecto": "", "localizacion": "", "municipio": "", "departamento": "",
    "fecha_levantamiento": None, "cuadrilla": "", "clima": "Despejado",
    "temperatura": 18.0, "presion": 752.0,
    "equipo_marca": "", "equipo_modelo": "", "equipo_serie": "",
    "equipo_calibracion": None, "equipo_prec_ang": 5.0,
    "equipo_edm_a": 2.0, "equipo_edm_b": 2.0,
    "datum_vertical": "Nivel medio del mar - Buenaventura",
    "punto_amarre": "", "fuente_amarre": "Vértice IGAC",
    "altura_elipsoidal": 2600.0,
    "precision_exigida": 10000, "factor_tolerancia": 2.0,
    "orden_nivelacion": "Tercer orden", "longitud_nivelada_km": 1.0,
    "material_volumenes": "Material común", "capacidad_volqueta": 7.0,
    "acarreo_libre": 100.0,
    "observaciones": ""
}


def obtener_dir_sesion():
    """
    Directorio privado de esta sesión del navegador.

    En Streamlit Cloud todos los usuarios comparten proceso y disco. Con
    rutas fijas ("Plano_Exportado.png", "Reportes_PDF/") dos usuarios
    concurrentes se sobrescriben el plano y las fotografías entre sí.
    Aislando por sesión el problema desaparece.
    """
    if "_sesion_id" not in st.session_state:
        st.session_state._sesion_id = uuid.uuid4().hex[:12]
    base = os.path.join("Trabajo", st.session_state._sesion_id)
    os.makedirs(base, exist_ok=True)
    return base


def dir_reportes():
    ruta = os.path.join(obtener_dir_sesion(), "Reportes_PDF")
    os.makedirs(ruta, exist_ok=True)
    return ruta


def dir_fotos(subcarpeta, estacion=None):
    partes = [obtener_dir_sesion(), subcarpeta,
              st.session_state.get("proyecto_actual") or "Sin_Proyecto"]
    if estacion is not None:
        partes.append(str(estacion))
    ruta = os.path.join(*partes)
    os.makedirs(ruta, exist_ok=True)
    return ruta


def firma_archivos(rutas):
    """
    Huella del CONTENIDO de unas rutas (tamaño + fecha de modificación).

    st.cache_data usa los argumentos como clave. Si se le pasa solo la ruta
    ("Plano_Exportado.png", siempre igual), al recalcular el levantamiento
    la clave no cambia y devuelve el PDF anterior con el plano viejo.
    Incluyendo esta firma entre los argumentos, la caché se invalida cuando
    la figura cambia de verdad.
    """
    partes = []
    for r in (rutas or []):
        if isinstance(r, (list, tuple)):
            r = r[-1]
        try:
            partes.append(f"{r}:{os.path.getmtime(r):.0f}:{os.path.getsize(r)}")
        except (OSError, TypeError):
            partes.append(f"{r}:ausente")
    return "|".join(partes)


def huella_datos(*dataframes):
    """Hash corto del conjunto de datos, para la trazabilidad del informe."""
    h = hashlib.sha256()
    for df in dataframes:
        try:
            h.update(pd.util.hash_pandas_object(df, index=True).values.tobytes())
        except Exception:
            h.update(str(df).encode("utf-8", errors="ignore"))
    return h.hexdigest()[:12].upper()


# ===================================================================
# FICHA TÉCNICA -> PARÁMETROS DEL MOTOR DE INFORMES
# ===================================================================
def _texto_fecha(valor):
    if isinstance(valor, (datetime, date)):
        return valor.strftime("%d/%m/%Y")
    return str(valor) if valor else ""


def construir_metadatos(sistema_referencia=None, huella=""):
    """Traduce la ficha del usuario a las claves que espera el informe."""
    f = {**FICHA_POR_DEFECTO, **st.session_state.get("ficha_tecnica", {})}
    lugar = ", ".join([x for x in [f["localizacion"], f["municipio"],
                                   f["departamento"]] if x])
    clima = f["clima"]
    if f.get("temperatura") is not None:
        clima += f" — {f['temperatura']:.1f} °C, {f['presion']:.0f} hPa"

    return {
        "Proyecto": f["nombre_proyecto"] or (st.session_state.get("proyecto_actual") or ""),
        "Localización": lugar,
        "Fecha de levantamiento": _texto_fecha(f["fecha_levantamiento"]),
        "Cuadrilla": f["cuadrilla"],
        "Condiciones climáticas": clima,
        "Sistema de referencia": sistema_referencia or "MAGNA-SIRGAS / Origen Nacional (EPSG:9377)",
        "Datum vertical": f["datum_vertical"],
        "Unidad angular": "Grados sexagesimales",
        "Punto de amarre": f["punto_amarre"],
        "Fuente del amarre": f["fuente_amarre"],
        "Versión GeoPol": VERSION_APP,
        "Huella del conjunto de datos": huella,
        "Observaciones": f["observaciones"],
    }


def construir_equipo():
    """Datos del instrumento. Activan el cálculo de tolerancia angular."""
    f = {**FICHA_POR_DEFECTO, **st.session_state.get("ficha_tecnica", {})}
    return {
        "marca": f["equipo_marca"], "modelo": f["equipo_modelo"],
        "serie": f["equipo_serie"],
        "fecha_calibracion": _texto_fecha(f["equipo_calibracion"]),
        "precision_angular_seg": f["equipo_prec_ang"],
        "edm_a_mm": f["equipo_edm_a"], "edm_b_ppm": f["equipo_edm_b"],
    }


def param_ficha(clave):
    f = {**FICHA_POR_DEFECTO, **st.session_state.get("ficha_tecnica", {})}
    return f.get(clave)


def coords_desde_ajuste(df_ajuste):
    """Vértices (Este, Norte) para el cálculo de área por Gauss."""
    try:
        pts = [(float(r["X_Estacion"]), float(r["Y_Estacion"]))
               for _, r in df_ajuste.iterrows()]
    except (KeyError, TypeError, ValueError):
        return None
    # En una poligonal cerrada el último vértice repite el primero
    if len(pts) > 2 and math.isclose(pts[0][0], pts[-1][0], abs_tol=1e-6) \
       and math.isclose(pts[0][1], pts[-1][1], abs_tol=1e-6):
        pts = pts[:-1]
    return pts if len(pts) >= 3 else None


def este_medio(df_ajuste):
    """Este representativo de la zona, para el factor de escala combinado."""
    try:
        return float(pd.to_numeric(df_ajuste["X_Estacion"], errors="coerce").mean())
    except (KeyError, TypeError, ValueError):
        return None


def lados_para_memoria(met, df_campo, df_ajuste, modo):
    """
    Lados (nombre, distancia horizontal, azimut) para la memoria de
    proyecciones de Bowditch del informe.

    Solo aplica a POLIGONAL CERRADA: en una abierta la suma de proyecciones
    no debe ser cero sino el desnivel entre los puntos de control conocidos,
    y la tabla reportaría un cierre falso.

    Prioriza met["lados"], que motor_v2_5 entrega sin redondear. La
    reconstrucción desde los DataFrames es un respaldo, pero Dist_Horiz
    viene redondeado a milímetro y en poligonales muy precisas eso mueve
    el cierre lo suficiente como para contradecir las métricas: por eso
    solo se acepta si reproduce el error de cierre dentro de 0,1 mm.
    """
    if modo != "Cerrada":
        return None

    lados = met.get("lados")
    if lados:
        return [{"lado": l["lado"], "distancia": l["distancia"],
                 "azimut": l["azimut"]} for l in lados]

    try:
        if "Dist_Horiz" not in df_campo.columns or "Azimut_Línea" not in df_ajuste.columns:
            return None
        recon = []
        for i in range(1, len(df_ajuste)):
            az = dms_a_segundos(df_ajuste.iloc[i]["Azimut_Línea"]) / 3600.0
            recon.append({
                "lado": f"{df_ajuste.iloc[i]['Estacionado']}-{df_ajuste.iloc[i]['Pto_Obs']}",
                "distancia": float(df_campo.iloc[i]["Dist_Horiz"]),
                "azimut": az})
        sum_e = sum(l["distancia"] * math.sin(math.radians(l["azimut"])) for l in recon)
        sum_n = sum(l["distancia"] * math.cos(math.radians(l["azimut"])) for l in recon)
        if abs(sum_e - float(met["err_e_ant"])) > 1e-4 or \
           abs(sum_n - float(met["err_n_ant"])) > 1e-4:
            return None   # no reproduce el cierre reportado: mejor omitir la tabla
        return recon
    except Exception:
        return None


def secciones_para_prismoidal(df_calculado, df_volumenes):
    """
    Construye la lista de secciones que el informe usa para contrastar
    áreas medias contra el método prismoidal y para localizar los puntos
    de paso (abscisas donde la cota roja se anula).

    Por abscisa se necesitan:
      area      : área neta con signo, (+) corte y (-) relleno
      cota_roja : diferencia terreno - diseño medida EN EL EJE
      ancho     : ancho total de la sección levantada
    """
    try:
        salida = []
        for _, fila in df_volumenes.iterrows():
            abscisa = float(fila['Abscisa (K)'])
            sec = df_calculado[df_calculado['Abscisa (K)'] == abscisa].dropna(
                subset=['Cota Terreno (m)', 'Cota Diseño (m)'])
            if sec.empty:
                continue
            eje = sec[sec['Distancia Eje (m)'] == 0.0]
            if eje.empty:
                cota_roja = float(sec['Cota Terreno (m)'].mean()
                                  - sec['Cota Diseño (m)'].mean())
            else:
                cota_roja = float(eje['Cota Terreno (m)'].iloc[0]
                                  - eje['Cota Diseño (m)'].iloc[0])
            salida.append({
                "abscisa": abscisa,
                "area": float(fila['Área Corte (m²)'] - fila['Área Relleno (m²)']),
                "cota_roja": round(cota_roja, 4),
                "ancho": float(sec['Distancia Eje (m)'].max()
                               - sec['Distancia Eje (m)'].min()),
            })
        return salida if len(salida) >= 2 else None
    except (KeyError, TypeError, ValueError):
        return None


def ficha_incompleta():
    """Campos mínimos sin diligenciar, para avisar antes de compilar."""
    f = {**FICHA_POR_DEFECTO, **st.session_state.get("ficha_tecnica", {})}
    faltan = []
    if not f["nombre_proyecto"]: faltan.append("Nombre del proyecto")
    if not f["localizacion"]: faltan.append("Localización")
    if not f["fecha_levantamiento"]: faltan.append("Fecha de levantamiento")
    if not f["cuadrilla"]: faltan.append("Cuadrilla")
    if not f["equipo_marca"]: faltan.append("Marca del equipo")
    return faltan


# ===================================================================
# PLANTILLAS BASE INDEPENDIENTES
# ===================================================================
df_plantilla_cerrada = pd.DataFrame({
    "Estacionado": ['GPS-11', 'P1', 'P2', 'P3', 'P4', 'P5', 'GPS-11'], 
    "Pto_Obs": ['P1', 'P2', 'P3', 'P4', 'P5', 'GPS-11', 'P1'],
    "Hz_G": [275, 249, 191, 281, 246, 188, 282], "Hz_M": [43, 53, 47, 3, 35, 26, 14], "Hz_S": [41.0, 14.0, 17.0, 0.0, 32.0, 50.0, 12.0],
    "Z_G": [89, 90, 90, 89, 89, 89, 89], "Z_M": [40, 0, 13, 50, 58, 21, 40], "Z_S": [53.0, 14.0, 6.0, 53.0, 3.0, 11.0, 46.0],
    "Dist_Inc": [69.249, 50.148, 57.843, 61.563, 75.728, 31.260, 69.250],
    "hi": [1.617, 1.596, 1.575, 1.551, 1.597, 1.541, 1.615], "hr": [1.700, 1.700, 1.700, 1.700, 1.700, 1.700, 1.700],
    "📸 Tomar_Fotos": [False]*7
})

df_plantilla_abierta = pd.DataFrame({
    "Estacionado": ['GPS-09', 'C-1', 'C-2', 'C-3', 'C-4', 'C-5', 'C-6', 'C-7', 'GPS-06'],
    "Pto_Obs":     ['C-1', 'C-2', 'C-3', 'C-4', 'C-5', 'C-6', 'C-7', 'GPS-06', 'GPS-05'],
    "Hz_G": [76, 246, 135, 223, 205, 197, 162, 180, 180], "Hz_M": [56, 58, 51, 25, 20, 17, 49, 0, 0], "Hz_S": [32.0, 41.0, 53.0, 11.0, 14.0, 36.0, 57.0, 0.0, 0.0],
    "Z_G": [81, 89, 89, 89, 90, 89, 90, 90, 90], "Z_M": [4, 45, 30, 39, 14, 43, 33, 0, 0], "Z_S": [20.0, 10.0, 13.0, 21.0, 0.0, 33.0, 19.0, 0.0, 0.0],
    "Dist_Inc": [20.119, 73.699, 116.226, 96.228, 47.085, 32.462, 58.209, 50.000, 50.000],
    "hi": [1.398, 1.470, 1.528, 1.537, 1.534, 1.563, 1.550, 1.500, 1.500], "hr": [1.800, 1.800, 1.800, 1.800, 1.800, 1.800, 1.800, 1.800, 1.800],
    "📸 Tomar_Fotos": [False]*9
})

df_plantilla_niv_cerrada = pd.DataFrame({
    "Estaca / Punto": ["BM-1", "K0+000", "K0+010", "PC-1", "K0+020", "BM-1"],
    "Vista Atrás (V+)": [1.250, None, None, 1.420, None, None],
    "Vista Intermedia (V-)": [None, 1.100, 1.550, None, 1.320, None],
    "Vista Adelante (V-)": [None, None, None, 0.980, None, 1.685],
    "📸 Tomar_Fotos": [False, False, False, False, False, False]
})

df_plantilla_niv_abierta = pd.DataFrame({
    "Estaca / Punto": ["BM-INICIO", "K0+000", "PC-1", "K0+010", "BM-LLEGADA"],
    "Vista Atrás (V+)": [1.500, None, 1.620, None, None],
    "Vista Intermedia (V-)": [None, 1.200, None, 1.450, None],
    "Vista Adelante (V-)": [None, None, 1.100, None, 2.505],
    "📸 Tomar_Fotos": [False, False, False, False, False]
})

# ===================================================================
# FUNCIONES MATEMÁTICAS PARA GRÁFICOS (PLOTLY + MATPLOTLIB)
# ===================================================================
def calcular_intersecciones_seccion(x_vals, y_dis, y_ter):
    x_final, y_dis_final, y_ter_final = [], [], []
    for i in range(len(x_vals) - 1):
        x_final.append(x_vals[i])
        y_dis_final.append(y_dis[i])
        y_ter_final.append(y_ter[i])
        diff1 = y_ter[i] - y_dis[i]
        diff2 = y_ter[i+1] - y_dis[i+1]
        if diff1 * diff2 < 0:
            dx = x_vals[i+1] - x_vals[i]
            frac = abs(diff1) / (abs(diff1) + abs(diff2))
            x_inter = x_vals[i] + (dx * frac)
            y_inter = y_dis[i] + (y_dis[i+1] - y_dis[i]) * frac
            x_final.append(x_inter)
            y_dis_final.append(y_inter)
            y_ter_final.append(y_inter)
    x_final.append(x_vals[-1])
    y_dis_final.append(y_dis[-1])
    y_ter_final.append(y_ter[-1])
    return np.array(x_final), np.array(y_dis_final), np.array(y_ter_final)

def crear_figura_seccion_plotly(df_plot, abs_plot):
    x_vals = df_plot['Distancia Eje (m)'].values.tolist()
    y_dis = df_plot['Cota Diseño (m)'].values.tolist()
    y_ter = df_plot['Cota Terreno (m)'].values.tolist()
    x_f, y_dis_f, y_ter_f = calcular_intersecciones_seccion(x_vals, y_dis, y_ter)
    y_min, y_max = np.minimum(y_dis_f, y_ter_f), np.maximum(y_dis_f, y_ter_f)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_f, y=y_dis_f, mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=x_f, y=y_max, mode='none', fill='tonexty', fillcolor='rgba(220, 53, 69, 0.45)', name='Corte'))
    fig.add_trace(go.Scatter(x=x_f, y=y_min, mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=x_f, y=y_dis_f, mode='none', fill='tonexty', fillcolor='rgba(40, 167, 69, 0.45)', name='Relleno'))
    fig.add_trace(go.Scatter(x=x_vals, y=y_ter, mode='lines+markers', name='Terreno', line=dict(color='#8D6E63', width=2), marker=dict(size=4, color='#5D4037')))
    fig.add_trace(go.Scatter(x=x_vals, y=y_dis, mode='lines+markers', name='Diseño', line=dict(color='#343A40', width=2), marker=dict(size=4, color='#212529')))
    
    fig.update_layout(title=dict(text=f'Sección K{abs_plot:.3f}', font=dict(size=14)), xaxis_title='Dist. Eje (m)', yaxis_title='Cota (m)', margin=dict(l=30, r=30, t=40, b=30), plot_bgcolor='rgba(245, 245, 245, 1)', showlegend=False)
    return fig

def guardar_imagen_masa_plt(df_vol, ruta):
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df_vol['Abscisa (K)'], df_vol['Masa Acumulada (m³)'], color='#0D47A1', linewidth=2, marker='o', markersize=4, markerfacecolor='#FF8C00')
    ax.fill_between(df_vol['Abscisa (K)'], df_vol['Masa Acumulada (m³)'], 0, color='#0D47A1', alpha=0.2)
    ax.set_title("Diagrama de Masas (Curva Masa)", fontsize=14, fontweight='bold')
    ax.set_xlabel("Abscisa (Distancia en K)", fontsize=11)
    ax.set_ylabel("Volumen Neto Acumulado (m³)", fontsize=11)
    ax.grid(True, linestyle='--', alpha=0.6)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)

def guardar_seccion_plt(df_plot, abs_plot, ruta):
    x_vals = df_plot['Distancia Eje (m)'].values.tolist()
    y_dis = df_plot['Cota Diseño (m)'].values.tolist()
    y_ter = df_plot['Cota Terreno (m)'].values.tolist()
    
    x_f, y_dis_f, y_ter_f = calcular_intersecciones_seccion(x_vals, y_dis, y_ter)
    y_min, y_max = np.minimum(y_dis_f, y_ter_f), np.maximum(y_dis_f, y_ter_f)
    
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.fill_between(x_f, y_dis_f, y_max, where=(y_max > y_dis_f), color='#DC3545', alpha=0.45, label='Corte')
    ax.fill_between(x_f, y_min, y_dis_f, where=(y_dis_f > y_min), color='#28A745', alpha=0.45, label='Relleno')
    
    ax.plot(x_vals, y_ter, marker='.', color='#8D6E63', label='Terreno', linewidth=1.5)
    ax.plot(x_vals, y_dis, marker='.', color='#343A40', label='Diseño', linewidth=1.5)
    
    ax.set_title(f'Sección K{abs_plot:.3f}', fontsize=11, fontweight='bold')
    ax.set_xlabel('Distancia Eje (m)', fontsize=9)
    ax.set_ylabel('Cota (m)', fontsize=9)
    ax.grid(True, linestyle='--', alpha=0.4)
    fig.tight_layout()
    fig.savefig(ruta, dpi=120)
    plt.close(fig)

def guardar_perfil_altimetria_plt(df_niv, ruta):
    # copy(): sin esto se modifica in-place el DataFrame que recibió la
    # función cacheada, que es lo que Streamlit desaconseja expresamente.
    df_niv = df_niv.copy()
    df_niv['Cota Ajustada'] = pd.to_numeric(df_niv['Cota Ajustada'], errors='coerce')
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df_niv['Estaca / Punto'], df_niv['Cota Ajustada'], color='#FF8C00', marker='o', linewidth=2, markersize=6, markerfacecolor='#0D47A1')
    ax.set_title("Perfil Topográfico Altimétrico", fontsize=14, fontweight='bold')
    ax.set_xlabel("Estaciones / Puntos", fontsize=11)
    ax.set_ylabel("Elevación (msnm)", fontsize=11)
    ax.grid(True, linestyle='--', alpha=0.6)
    plt.xticks(rotation=45)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)

# ===================================================================
# GENERADORES DE CACHÉ GLOBAL (PDFS)
# ===================================================================
@st.cache_data(show_spinner=False)
def cachear_pdf_volumenes(df_calculado_interno, df_vol_interno, met, p_actual,
                          imprimir_secciones, salida, metadatos, equipo, params):
    """metadatos/equipo/params vienen de la Ficha Técnica y forman parte de
    la clave de caché, de modo que al editarla el informe se regenera."""
    ruta_masa = os.path.join(salida, "Curva_Masa.png")
    guardar_imagen_masa_plt(df_vol_interno, ruta_masa)

    paths_sec = []
    if imprimir_secciones:
        for a_val in sorted(df_calculado_interno['Abscisa (K)'].unique()):
            df_p = df_calculado_interno[df_calculado_interno['Abscisa (K)'] == a_val].copy().dropna(subset=['Cota Terreno (m)', 'Cota Diseño (m)']).sort_values('Distancia Eje (m)')
            if not df_p.empty:
                ruta_s = os.path.join(salida, f"Sec_K{a_val:.3f}.png")
                guardar_seccion_plt(df_p, a_val, ruta_s)
                paths_sec.append((a_val, ruta_s))

    # Curva masa: el motor de informes acumula internamente, así que aquí
    # hay que entregarle el volumen neto POR TRAMO, no el ya acumulado.
    abscisas, vol_netos = None, None
    try:
        neto_tramo = (df_vol_interno['Vol. Corte (m³)'].fillna(0)
                      - df_vol_interno['Vol. Relleno (m³)'].fillna(0))
        abscisas = df_vol_interno['Abscisa (K)'].astype(float).tolist()
        vol_netos = neto_tramo.astype(float).tolist()
    except Exception:
        abscisas, vol_netos = None, None

    # Secciones para el contraste áreas medias / prismoidal y los puntos de paso
    secciones = secciones_para_prismoidal(df_calculado_interno, df_vol_interno)

    tex_vol = generar_reporte_volumenes_latex(
        df_vol_interno, met, AUTORES, TUTOR,
        path_masas=ruta_masa, paths_secciones=paths_sec,
        directorio_salida=salida,
        metadatos=metadatos, equipo=equipo,
        material=params["material"],
        capacidad_volqueta=params["capacidad_volqueta"],
        acarreo_libre=params["acarreo_libre"],
        abscisas=abscisas, volumenes_netos=vol_netos,
        secciones=secciones)
    pdf_bytes, pdf_path, debug_msg = compilar_latex_a_pdf(
        tex_vol, output_dir=salida, filename=f"Cubicaje_{p_actual}")
    return pdf_bytes, tex_vol, debug_msg

@st.cache_data(show_spinner=False)
def cachear_pdf_altimetria(df_niv_interno, met, p_actual, tipo_niv, fotos_paths,
                           salida, firma_fotos, metadatos, equipo, params, bm):
    ruta_perfil = os.path.join(salida, "Perfil_Nivelacion.png")
    guardar_perfil_altimetria_plt(df_niv_interno, ruta_perfil)

    tex_niv = generar_reporte_nivelacion_latex(
        df_niv_interno, met, tipo_niv, AUTORES, TUTOR,
        path_grafico=ruta_perfil, fotos_paths=fotos_paths,
        directorio_salida=salida,
        metadatos=metadatos, equipo=equipo,
        longitud_km=params["longitud_km"], orden=params["orden"],
        bm_partida=bm)
    pdf_bytes, pdf_path, debug_msg = compilar_latex_a_pdf(
        tex_niv, output_dir=salida, filename=f"Nivelacion_{p_actual}")
    return pdf_bytes, tex_niv, debug_msg

@st.cache_data(show_spinner=False)
def cachear_pdf_poli(df_campo_i, df_ajuste_i, met, p_actual, ruta_p, f_tomadas, t_app,
                     salida, firma_figs, metadatos, equipo, params, coords, este_ref,
                     lados):
    titulo = "Poligonal Cerrada" if t_app == "Cerrada" else "Poligonal Abierta con Control"
    data_tex = generar_reporte_poligonal_latex(
        df_campo_i, df_ajuste_i, met, titulo, AUTORES, TUTOR,
        path_grafico=ruta_p, fotos_paths=f_tomadas,
        directorio_salida=salida,
        metadatos=metadatos, equipo=equipo,
        coords_poligono=coords,
        lados=lados,
        este_referencia=este_ref,
        altura_elipsoidal=params["altura_elipsoidal"],
        precision_exigida=params["precision_exigida"],
        factor_tolerancia=params["factor_tolerancia"])
    pdf_bytes, pdf_path, debug_msg = compilar_latex_a_pdf(
        data_tex, output_dir=salida, filename=f"Reporte_{p_actual}")
    return pdf_bytes, data_tex, debug_msg

# ===================================================================
# GESTOR DE PROYECTOS Y SISTEMA DE GUARDADO LOCAL (.GP)
# ===================================================================

def generar_datos_guardado():
    """Compila las variables de entorno para exportarlas como archivo."""
    tipos_seguros = (int, float, str, bool, list, dict, tuple, set, pd.DataFrame, type(None))
    estado_a_guardar = {}
    # _sesion_id identifica el directorio privado de ESTE navegador: si viajara
    # dentro del .gp, al cargarlo en otra sesión se apuntaría a carpetas ajenas.
    llaves_prohibidas = ["sel_cargar", "sel_eliminar", "nav", "FormSubmitter",
                         "_sesion_id", "fw_"]
    
    for k, v in st.session_state.items():
        if any(k.startswith(prohibida) for prohibida in llaves_prohibidas) or k.startswith("cam_") or k.startswith("editor_"):
            continue
        if isinstance(v, tipos_seguros):
            estado_a_guardar[k] = v
            
    return pickle.dumps(estado_a_guardar)

def cargar_proyecto_desde_archivo(file_bytes, nombre):
    """Reconstruye el entorno desde un archivo subido."""
    llaves_vitales = ["proyecto_actual", "modo_app"]
    for k in list(st.session_state.keys()):
        if k not in llaves_vitales:
            del st.session_state[k]
            
    st.session_state.proyecto_actual = nombre
    inicializar_variables_proyecto() 
    
    estado_guardado = pickle.loads(file_bytes)
    for k, v in estado_guardado.items():
        if not k.startswith("sel_"):
            st.session_state[k] = v
            
    st.session_state.modo_app = "Menu_Principal"

def inicializar_variables_proyecto():
    defaults = {
        "modo_app": "Inicio", 
        "calc_cerrada": False, "calc_abierta": False, 
        "calc_niv_cerrada": False, "calc_niv_abierta": False, 
        "calc_vol": False,
        "nubes_guardadas": {}, 
        "c_n_ini": 102340.641, "c_e_ini": 87677.229, "c_z_ini": 100.0,
        "c_n_ref": 102295.280, "c_e_ref": 87588.109, "c_z_ref": 100.0,
        "c_az_g": 243, "c_az_m": 1, "c_az_s": 28.0,
        "c_tipo_amarre": "Dos Coordenadas Conocidas", "c_tipo_ang": "exterior",
        "a_n_ini": 102562.748, "a_e_ini": 86138.390, "a_z_ini": 2565.979,
        "a_n_ref_arr": 102578.559, "a_e_ref_arr": 86236.815, "a_z_ref_arr": 2569.150,
        "a_n_fin": 102379.463, "a_e_fin": 85957.573, "a_z_fin": 2565.807,
        "a_n_ref_lleg": 102478.065, "a_e_ref_lleg": 86007.693, "a_z_ref_lleg": 2566.112,
        "a_azA_g": 76, "a_azA_m": 56, "a_azA_s": 32.0, "a_azL_g": 250, "a_azL_m": 15, "a_azL_s": 10.0,
        "a_tipo_amarre_arr": "Dos Coordenadas Conocidas", "a_tipo_amarre_lleg": "Dos Coordenadas Conocidas",
        "vol_abs_ini": 0.0, "vol_abs_fin": 40.0, "vol_int_long": 10.0, "vol_ancho_izq": 6.0, "vol_ancho_der": 6.0,
        "vol_int_transv": 2.0, "vol_bom_izq": -2.0, "vol_bom_der": -2.0,
        "vol_cota_ras": 500.000, "vol_pend": 0.500, "vol_hi_ini": 504.000,
        "niv_cota_datum_c": 100.000, "niv_cota_datum_a": 500.000, "niv_cota_llegada": 499.520,
        "df_cerrada_campo": df_plantilla_cerrada.copy(), 
        "df_abierta_campo": df_plantilla_abierta.copy(), 
        "df_niv_cerrada_campo": df_plantilla_niv_cerrada.copy(),
        "df_niv_abierta_campo": df_plantilla_niv_abierta.copy(),
        "df_malla_vol": None,
        "proyecto_actual": None,
        # proy_guardada solo se creaba dentro del módulo de poligonales, así
        # que entrar directo a Nube de Puntos lanzaba AttributeError.
        "proy_guardada": 0,
        "ficha_tecnica": dict(FICHA_POR_DEFECTO)
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def crear_nuevo_proyecto(nombre):
    llaves_vitales = ["proyecto_actual", "modo_app"]
    for k in list(st.session_state.keys()):
        if k not in llaves_vitales:
            del st.session_state[k]
            
    st.session_state.proyecto_actual = nombre
    st.session_state.modo_app = "Menu_Principal"
    inicializar_variables_proyecto()

# ===================================================================
# INICIALIZACIÓN DE MOTORES
# ===================================================================
@st.cache_resource
def iniciar_motor_coordenadas():
    return MotorCoordenadasIGAC_V2()

motor_igac = iniciar_motor_coordenadas()
inicializar_variables_proyecto()
st.query_params.clear()

@st.cache_data(show_spinner=False)
def obtener_b64_imagen(ruta):
    with open(ruta, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def mostrar_icono(nombre_archivo, fallback_emoji, width=120, hover_effect=True, shadow=True, border_radius="30px"):
    ruta = os.path.join("Iconos", nombre_archivo)
    if not os.path.exists(ruta):
        ruta_alt = ruta.replace(".png", ".svg") if nombre_archivo.endswith(".png") else ruta.replace(".svg", ".png")
        if os.path.exists(ruta_alt): ruta = ruta_alt
        else:
            st.markdown(f"<div style='text-align:center; font-size:{width*0.7}px;'>{fallback_emoji}</div>", unsafe_allow_html=True)
            return

    b64 = obtener_b64_imagen(ruta)
    mime_type = "image/svg+xml" if ruta.endswith(".svg") else "image/png"
    css_class = f"icono-{nombre_archivo.replace('.','-')}"
    
    html = f"<style>.{css_class} {{ width: {width}px; border-radius: {border_radius}; display: block; margin: 0 auto; cursor: default;"
    if shadow: html += "box-shadow: 0 8px 16px rgba(0,0,0,0.2);"
    if hover_effect and shadow: html += f"}} .{css_class}:hover {{ transform: scale(1.05) translateY(-5px); box-shadow: 0 12px 20px rgba(0,0,0,0.3); "
    html += "}</style>"
    
    img_html = f'<img src="data:{mime_type};base64,{b64}" class="{css_class}">'
    st.markdown(f'{html}<div style="text-align:center;">{img_html}</div><br>', unsafe_allow_html=True)

def renderizar_banner_proyecto():
    if st.session_state.get("proyecto_actual"):
        with st.container():
            st.markdown(f"""
            <div style='background-color: #E3F2FD; padding: 15px; border-radius: 10px; border-left: 8px solid #2196F3; margin-bottom: 15px;'>
                <h4 style='color: #0D47A1; margin: 0;'>📂 Workspace Activo: {st.session_state.get("proyecto_actual")}</h4>
                <p style='margin: 0; color: #1565C0; font-size: 14px;'>Descarga tu archivo de seguridad desde la barra lateral para no perder el progreso.</p>
            </div>
            """, unsafe_allow_html=True)
            # El botón de descarga vive solo en la barra lateral. Tenerlo aquí
            # también obligaba a serializar TODO el session_state dos veces en
            # cada rerun, lo que con nubes de puntos grandes se nota mucho.

# ===================================================================
# BARRA LATERAL (SIDEBAR)
# ===================================================================
with st.sidebar:
    mostrar_icono("logo_geopol.svg", "🌐", width=220, hover_effect=False, shadow=False, border_radius="0px")
    st.markdown("---")
    
    if st.session_state.get("proyecto_actual"):
        st.info(f"📌 **Trabajando en:**\n### {st.session_state.get('proyecto_actual')}")
        
        datos_gp = generar_datos_guardado()
        st.download_button(
            label="💾 Guardar Proyecto (.gp)",
            data=datos_gp,
            file_name=f"{st.session_state.get('proyecto_actual')}.gp",
            mime="application/octet-stream",
            use_container_width=True,
            type="primary"
        )
            
        if st.button("❌ Cerrar Proyecto", use_container_width=True):
            st.session_state.proyecto_actual = None
            st.session_state.modo_app = "Inicio"
            st.rerun()
        st.markdown("---")
        
    st.markdown("### 🗂️ Navegación")
    if st.button("🏠 Inicio", use_container_width=True):
        st.session_state.modo_app = "Inicio"
        st.rerun()
        
    if st.session_state.get("proyecto_actual"):
        if st.button("🗂️ Menú Principal", use_container_width=True):
            st.session_state.modo_app = "Menu_Principal"
            st.rerun()
        etiqueta_ficha = "📋 Ficha Técnica"
        if ficha_incompleta():
            etiqueta_ficha += " ⚠️"
        if st.button(etiqueta_ficha, use_container_width=True):
            st.session_state.modo_app = "Ficha_Tecnica"
            st.rerun()
        if st.button("📐 Ir a Planimetría", use_container_width=True):
            st.session_state.modo_app = "Menu_Poligonales"
            st.rerun()
        if st.button("⛰️ Ir a Altimetría", use_container_width=True):
            st.session_state.modo_app = "Menu_Altimetria"
            st.rerun()
        if st.button("📍 Ir a Nube de Puntos", use_container_width=True):
            st.session_state.modo_app = "Nube_Puntos"
            st.rerun()

    st.markdown("---")
    mostrar_icono("logo_udistrital.png", "🎓", width=160, hover_effect=False, shadow=False, border_radius="0px")
    st.markdown("<p style='text-align:center; font-size:12px; color:gray;'>Kevin Cubillos & Sergio Barbosa</p>", unsafe_allow_html=True)


if st.session_state.modo_app in ["Inicio", "Menu_Principal"]:
    col_logo, col_info = st.columns([1, 4])
    with col_logo:
        mostrar_icono("logo_udistrital.png", "🎓", width=180, hover_effect=False, shadow=False, border_radius="0px")
    with col_info:
        st.markdown("## **UNIVERSIDAD DISTRITAL FRANCISCO JOSÉ DE CALDAS**")
        st.markdown("#### **Facultad Tecnológica - Ingeniería Civil / Topográfica**")
        st.markdown("**Trabajo de Grado:** Desarrollo de un Geoportal Web para la Automatización del Cálculo de Poligonales")
        
        st.markdown("""
        <div style='background-color: #f8f9fa; padding: 12px; border-radius: 8px; border-left: 5px solid #FF8C00; margin-top: 10px;'>
            <span style='color: #0D47A1; font-size: 15px;'><b>Tutor:</b> Ing. Edgar Ladino &nbsp; | &nbsp; <b>Autores:</b> Kevin Stiven Cubillos Ramirez & Sergio Eduardo Barbosa Torres</span>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("---")

# ===================================================================
# PANTALLAS DE NAVEGACIÓN
# ===================================================================
if st.session_state.modo_app == "Inicio":
    col_hero1, col_hero2, col_hero3 = st.columns([1, 2, 1])
    with col_hero2:
        mostrar_icono("logo_geopol.svg", "🌐", width=350, hover_effect=False, shadow=False)
        st.markdown("<h2 style='text-align: center; color: #FF8C00; margin-top: -30px; font-weight: 800; font-style: italic;'>Máxima precisión al alcance de tus manos</h2>", unsafe_allow_html=True)
    
    st.markdown("---")
    tab_proyectos, tab_sobre, tab_equipo = st.tabs(["📂 Gestor de Proyectos", "📖 ¿Qué es GeoPol Web?", "👨‍💻 Nuestro Equipo"])
    
    with tab_proyectos:
        st.markdown("### 🏢 Centro de Trabajo")
        st.caption("Crea un nuevo proyecto en blanco o carga uno de tus archivos .gp para retomar tu trabajo.")
        
        col_new, col_load = st.columns(2)
        with col_new:
            st.success("✨ **Iniciar Nuevo Proyecto**")
            nuevo_nombre = st.text_input("Ingresa el nombre del proyecto:")
            if st.button("➕ Crear Workspace", use_container_width=True):
                if nuevo_nombre.strip() == "": st.warning("Debe ingresar un nombre válido.")
                else: crear_nuevo_proyecto(nuevo_nombre.strip()); st.rerun()
        with col_load:
            st.info("📂 **Cargar Copia de Seguridad**")
            archivo_gp = st.file_uploader("Sube tu archivo .gp de GeoPol Web", type=['gp'])
            if archivo_gp is not None:
                if st.button("🚀 Cargar Workspace", use_container_width=True): 
                    nombre_base = archivo_gp.name.replace(".gp", "")
                    cargar_proyecto_desde_archivo(archivo_gp.getvalue(), nombre_base)
                    st.rerun()

    with tab_sobre:
        col_txt, col_img = st.columns([2, 1])
        with col_txt:
            st.markdown("### 🌍 El Origen de GeoPol Web")
            st.write("El trabajo de campo topográfico siempre ha sido riguroso, pero el procesamiento en oficina suele ser un cuello de botella tedioso. GeoPol Web nace como la solución definitiva a este problema.")
            st.markdown("### 🚀 Características Únicas")
            st.markdown("- 📐 Motor CAD 2D Interactivo.\n- 🚜 Modelo Civil 3D en Tiempo Real.\n- 📑 Reportes Científicos Nativos en LaTeX.\n- 🗺️ Interoperabilidad GIS Total.")
        with col_img:
            mostrar_icono("planimetria.png", "📐", width=250, shadow=False)
            mostrar_icono("volumenes.png", "🚜", width=250, shadow=False)

    with tab_equipo:
        st.markdown("<h3 style='text-align:center;'>Conoce a los creadores de esta plataforma</h3><br>", unsafe_allow_html=True)
        col_k, col_s, col_e = st.columns(3)
        with col_k:
            st.markdown("<div style='text-align:center; padding: 20px; background-color: #f8f9fa; border-radius: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);'>", unsafe_allow_html=True)
            mostrar_icono("kevin.png", "👨‍💻", width=120, shadow=False)
            st.markdown("### Kevin Cubillos")
            st.caption("Desarrollador Core & Co-Autor")
            st.write("Estudiante de Ingeniería en la U. Distrital, apasionado por la automatización de procesos topográficos y el desarrollo de arquitecturas en Python.")
            st.markdown("</div>", unsafe_allow_html=True)
        with col_s:
            st.markdown("<div style='text-align:center; padding: 20px; background-color: #f8f9fa; border-radius: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);'>", unsafe_allow_html=True)
            mostrar_icono("sergio.png", "👨‍💻", width=120, shadow=False)
            st.markdown("### Sergio Barbosa")
            st.caption("Co-Autor & Analista Espacial")
            st.write("Estudiante de Ingeniería en la U. Distrital. Especializado en el aseguramiento de la calidad geométrica y la integración de estándares GIS/CAD.")
            st.markdown("</div>", unsafe_allow_html=True)
        with col_e:
            st.markdown("<div style='text-align:center; padding: 20px; background-color: #fff4e6; border-radius: 15px; border: 2px solid #FF8C00; box-shadow: 0 4px 8px rgba(0,0,0,0.1);'>", unsafe_allow_html=True)
            mostrar_icono("edgar.png", "🎓", width=120, shadow=False)
            st.markdown("### Ing. Edgar Ladino")
            st.caption("Director del Proyecto de Grado")
            st.write("Tutor académico y guía fundamental en la estructuración matemática y metodológica de este sistema experto. Su visión permitió escalar el proyecto a la web.")
            st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.modo_app == "Menu_Principal":
    st.markdown("<h4 style='text-align: center; color: gray;'>Seleccione la Disciplina Topográfica a trabajar</h4><br>", unsafe_allow_html=True)
    col_disc1, col_disc2, col_disc3 = st.columns(3)
    with col_disc1:
        mostrar_icono("planimetria.png", "📐", width=220)
        if st.button("⚙️ Ingresar a Planimetría", use_container_width=True): st.session_state.modo_app = "Menu_Poligonales"; st.rerun()
    with col_disc2:
        mostrar_icono("altimetria.png", "⛰️", width=220)
        if st.button("⚙️ Ingresar a Altimetría", use_container_width=True): st.session_state.modo_app = "Menu_Altimetria"; st.rerun()
    with col_disc3:
        mostrar_icono("nube_puntos.png", "📍", width=220)
        if st.button("⚙️ Nube de Puntos", use_container_width=True): st.session_state.modo_app = "Nube_Puntos"; st.rerun()

    st.markdown("---")
    faltantes_ficha = ficha_incompleta()
    if faltantes_ficha:
        st.warning("📋 **La Ficha Técnica del Levantamiento está incompleta.** "
                   "Sin ella los informes salen con el encabezado en blanco. "
                   "Faltan: " + ", ".join(faltantes_ficha))
    else:
        st.success("📋 Ficha Técnica del Levantamiento diligenciada.")
    if st.button("📋 Abrir Ficha Técnica del Levantamiento", use_container_width=True,
                 type="primary" if faltantes_ficha else "secondary"):
        st.session_state.modo_app = "Ficha_Tecnica"
        st.rerun()

elif st.session_state.modo_app == "Menu_Poligonales":
    st.markdown("<h3 style='text-align: center; color: #4A4A4A;'>Módulo de Poligonales (Planimetría)</h3><br>", unsafe_allow_html=True)
    colA, colB = st.columns(2)
    with colA:
        mostrar_icono("poligonal_cerrada.png", "🔄", width=240)
        if st.button("🚀 Iniciar Circuito Cerrado", use_container_width=True): st.session_state.modo_app = "Cerrada"; st.rerun()
    with colB:
        mostrar_icono("poligonal_abierta.png", "🛤️", width=240)
        if st.button("🚀 Iniciar Poligonal Abierta", use_container_width=True): st.session_state.modo_app = "Abierta"; st.rerun()

elif st.session_state.modo_app == "Menu_Altimetria":
    st.markdown("<h3 style='text-align: center; color: #4A4A4A;'>Módulo de Altimetría y Topografía Vertical</h3><br>", unsafe_allow_html=True)
    colA, colB, colC = st.columns(3)
    with colA:
        mostrar_icono("niv_cerrada.png", "🔄", width=180)
        if st.button("🚀 Nivelación Cerrada", use_container_width=True): st.session_state.modo_app = "Niv_Cerrada"; st.rerun()
    with colB:
        mostrar_icono("niv_abierta.png", "🛤️", width=180)
        if st.button("🚀 Nivelación Abierta", use_container_width=True): st.session_state.modo_app = "Niv_Abierta"; st.rerun()
    with colC:
        mostrar_icono("volumenes.png", "🚜", width=180)
        if st.button("🚀 Volúmenes y Diseño", use_container_width=True): st.session_state.modo_app = "Volumenes"; st.rerun()

# ===================================================================
# MÓDULO DE FICHA TÉCNICA DEL LEVANTAMIENTO
# ===================================================================
elif st.session_state.modo_app == "Ficha_Tecnica":
    renderizar_banner_proyecto()
    st.title("📋 Ficha Técnica del Levantamiento")
    st.markdown("Estos datos encabezan **todos** los informes PDF que genere la "
                "plataforma. Son los que sustentan la trazabilidad exigida en "
                "interventoría: sin ellos el informe sale con los campos en blanco.")

    faltantes = ficha_incompleta()
    if faltantes:
        st.warning("⚠️ Campos mínimos sin diligenciar: " + ", ".join(faltantes))
    else:
        st.success("✅ Ficha completa. Los informes saldrán con el encabezado lleno.")

    f = {**FICHA_POR_DEFECTO, **st.session_state.get("ficha_tecnica", {})}

    with st.form("form_ficha_tecnica"):
        tab_proy, tab_eq, tab_ref, tab_par = st.tabs([
            "📋 Proyecto y Cuadrilla", "🔭 Equipo Topográfico",
            "🌐 Referencia y Amarre", "⚙️ Parámetros de Cálculo"])

        # ---------------- Proyecto ----------------
        with tab_proy:
            c1, c2 = st.columns(2)
            nombre_proyecto = c1.text_input(
                "Nombre del proyecto",
                value=f["nombre_proyecto"] or (st.session_state.get("proyecto_actual") or ""),
                placeholder="Levantamiento topográfico Sede Tecnológica")
            fecha_lev = c2.date_input(
                "Fecha de levantamiento",
                value=f["fecha_levantamiento"] or date.today())

            st.markdown("**📍 Localización**")
            c1, c2, c3 = st.columns(3)
            localizacion = c1.text_input("Sector / vereda / dirección",
                                         value=f["localizacion"],
                                         placeholder="Carrera 7 con Calle 40 Sur")
            municipio = c2.text_input("Municipio", value=f["municipio"],
                                      placeholder="Bogotá D.C.")
            departamento = c3.text_input("Departamento", value=f["departamento"],
                                         placeholder="Cundinamarca")

            st.markdown("**👷 Cuadrilla y condiciones**")
            cuadrilla = st.text_input(
                "Integrantes de la cuadrilla",
                value=f["cuadrilla"],
                placeholder="Topógrafo: ... | Cadeneros: ... | Anotador: ...")
            c1, c2, c3 = st.columns(3)
            opciones_clima = ["Despejado", "Parcialmente nublado", "Nublado",
                              "Llovizna", "Lluvia", "Neblina"]
            clima = c1.selectbox(
                "Condiciones climáticas", opciones_clima,
                index=opciones_clima.index(f["clima"]) if f["clima"] in opciones_clima else 0)
            temperatura = c2.number_input("Temperatura (°C)", value=float(f["temperatura"]),
                                          step=0.5, format="%.1f")
            presion = c3.number_input("Presión (hPa)", value=float(f["presion"]),
                                      step=1.0, format="%.0f")
            st.caption("Temperatura y presión son los valores con los que se aplicó "
                       "la corrección atmosférica del distanciómetro.")

            observaciones = st.text_area(
                "Observaciones generales", value=f["observaciones"], height=80,
                placeholder="Incidencias de campo, obstrucciones, repeticiones...")

        # ---------------- Equipo ----------------
        with tab_eq:
            st.markdown("**🔭 Instrumento utilizado**")
            c1, c2, c3 = st.columns(3)
            equipo_marca = c1.text_input("Marca", value=f["equipo_marca"],
                                         placeholder="Leica / Topcon / South")
            equipo_modelo = c2.text_input("Modelo", value=f["equipo_modelo"],
                                          placeholder="TS07")
            equipo_serie = c3.text_input("Número de serie", value=f["equipo_serie"])

            st.markdown("**📐 Precisiones nominales y calibración**")
            c1, c2, c3 = st.columns(3)
            equipo_calib = c1.date_input("Fecha del certificado de calibración",
                                         value=f["equipo_calibracion"] or date.today())
            equipo_prec_ang = c2.number_input(
                "Precisión angular (segundos)", value=float(f["equipo_prec_ang"]),
                min_value=0.1, max_value=60.0, step=0.5, format="%.1f")
            c3.markdown("&nbsp;")
            c3.caption("La precisión angular define la tolerancia "
                       "Ta = k · a · √n del informe de poligonal.")

            c1, c2 = st.columns(2)
            equipo_edm_a = c1.number_input("Precisión EDM — término fijo (mm)",
                                           value=float(f["equipo_edm_a"]),
                                           step=0.5, format="%.1f")
            equipo_edm_b = c2.number_input("Precisión EDM — término proporcional (ppm)",
                                           value=float(f["equipo_edm_b"]),
                                           step=0.5, format="%.1f")

        # ---------------- Referencia ----------------
        with tab_ref:
            st.markdown("**🌐 Sistema de referencia**")
            st.info("El sistema horizontal se toma automáticamente de la proyección "
                    "que selecciones en cada módulo de cálculo.")
            datum_vertical = st.text_input("Datum vertical", value=f["datum_vertical"])

            st.markdown("**📌 Amarre del levantamiento**")
            c1, c2 = st.columns(2)
            punto_amarre = c1.text_input(
                "Código del punto de amarre", value=f["punto_amarre"],
                placeholder="BM-IGAC-4521 / GPS-11")
            opciones_fuente = ["Vértice IGAC", "GNSS estático", "GNSS RTK",
                               "Red geodésica municipal", "Arbitrario / local"]
            fuente_amarre = c2.selectbox(
                "Fuente del amarre", opciones_fuente,
                index=opciones_fuente.index(f["fuente_amarre"])
                if f["fuente_amarre"] in opciones_fuente else 0)

            altura_elipsoidal = st.number_input(
                "Altura elipsoidal media de la zona (m)",
                value=float(f["altura_elipsoidal"]), step=10.0, format="%.1f")
            st.caption("Necesaria para el factor de escala combinado. Es la altura "
                       "sobre el elipsoide (h = H + ondulación geoidal), no la cota "
                       "sobre el nivel del mar. En la sabana de Bogotá ronda los 2.600 m.")

        # ---------------- Parámetros ----------------
        with tab_par:
            st.markdown("**📐 Planimetría**")
            c1, c2 = st.columns(2)
            precision_exigida = c1.number_input(
                "Precisión relativa exigida (1 : P)",
                value=int(f["precision_exigida"]), min_value=500,
                max_value=100000, step=500)
            factor_tolerancia = c2.number_input(
                "Factor k de tolerancia angular", value=float(f["factor_tolerancia"]),
                min_value=0.5, max_value=5.0, step=0.5, format="%.1f")
            st.caption("k = 1 exigente · k = 2 estándar en obra civil · k = 3 expedito.")

            st.markdown("**⛰️ Altimetría**")
            c1, c2 = st.columns(2)
            ordenes = list(ORDENES_NIVELACION.keys())
            orden_nivelacion = c1.selectbox(
                "Orden de nivelación exigido", ordenes,
                index=ordenes.index(f["orden_nivelacion"])
                if f["orden_nivelacion"] in ordenes else ordenes.index("Tercer orden"))
            longitud_nivelada_km = c2.number_input(
                "Longitud total nivelada (km)",
                value=float(f["longitud_nivelada_km"]), min_value=0.0,
                step=0.1, format="%.3f")
            st.caption("La tolerancia altimétrica es e = k·√K, con K en kilómetros. "
                       "La cartera de nivelación no registra distancias, por eso hay "
                       "que indicar aquí la longitud del circuito.")

            st.markdown("**🚜 Movimiento de tierras**")
            c1, c2, c3 = st.columns(3)
            materiales = list(FACTORES_MATERIAL.keys())
            material_volumenes = c1.selectbox(
                "Material predominante", materiales,
                index=materiales.index(f["material_volumenes"])
                if f["material_volumenes"] in materiales else 0)
            capacidad_volqueta = c2.number_input(
                "Capacidad de volqueta (m³)", value=float(f["capacidad_volqueta"]),
                min_value=1.0, step=0.5, format="%.1f")
            acarreo_libre = c3.number_input(
                "Distancia de acarreo libre (m)", value=float(f["acarreo_libre"]),
                min_value=0.0, step=10.0, format="%.0f")
            st.caption("El material determina el esponjamiento y la contracción con "
                       "los que se corrige el balance volumétrico real.")

        guardado = st.form_submit_button("💾 Guardar Ficha Técnica",
                                         type="primary", use_container_width=True)

    if guardado:
        st.session_state.ficha_tecnica = {
            "nombre_proyecto": nombre_proyecto.strip(),
            "localizacion": localizacion.strip(),
            "municipio": municipio.strip(),
            "departamento": departamento.strip(),
            "fecha_levantamiento": fecha_lev,
            "cuadrilla": cuadrilla.strip(),
            "clima": clima, "temperatura": temperatura, "presion": presion,
            "equipo_marca": equipo_marca.strip(),
            "equipo_modelo": equipo_modelo.strip(),
            "equipo_serie": equipo_serie.strip(),
            "equipo_calibracion": equipo_calib,
            "equipo_prec_ang": equipo_prec_ang,
            "equipo_edm_a": equipo_edm_a, "equipo_edm_b": equipo_edm_b,
            "datum_vertical": datum_vertical.strip(),
            "punto_amarre": punto_amarre.strip(),
            "fuente_amarre": fuente_amarre,
            "altura_elipsoidal": altura_elipsoidal,
            "precision_exigida": int(precision_exigida),
            "factor_tolerancia": factor_tolerancia,
            "orden_nivelacion": orden_nivelacion,
            "longitud_nivelada_km": longitud_nivelada_km,
            "material_volumenes": material_volumenes,
            "capacidad_volqueta": capacidad_volqueta,
            "acarreo_libre": acarreo_libre,
            "observaciones": observaciones.strip(),
        }
        st.cache_data.clear()   # los PDFs cacheados llevan la ficha anterior
        st.success("✅ Ficha guardada. Los informes que generes ahora la incluirán.")
        st.rerun()

    st.markdown("---")
    with st.expander("👁️ Vista previa del encabezado que verá el informe"):
        previa = construir_metadatos(huella="(se calcula al compilar)")
        st.dataframe(
            pd.DataFrame({"Campo": list(previa.keys()),
                          "Valor": [v if v else "— sin diligenciar —"
                                    for v in previa.values()]}),
            use_container_width=True, hide_index=True)

    with st.expander("🔧 Estado del motor LaTeX en este servidor"):
        diag = diagnostico_latex()
        if not diag["pdflatex"]:
            st.error("No hay pdflatex instalado. Añade packages.txt al repositorio.")
        elif diag["criticos"]:
            st.error(diag["mensaje"])
        elif diag["faltantes"]:
            st.warning(diag["mensaje"])
        else:
            st.success(diag["mensaje"])
        if diag["faltantes"]:
            st.caption("Contenido recomendado para packages.txt:")
            st.code(diag["packages_txt"], language="text")

# ===================================================================
# MÓDULO DE NUBE DE PUNTOS (GIS MULTI-ARCHIVO INDEPENDIENTE)
# ===================================================================
elif st.session_state.modo_app == "Nube_Puntos":
    renderizar_banner_proyecto()
    st.title("📍 Visor GIS de Nubes de Puntos Topográficos")
    st.markdown("Carga y consolida múltiples archivos de coordenadas de campo para previsualizar el levantamiento masivo sobre el mapa base oficial y validar tu trabajo diario.")
    
    lista_proyecciones_disp = list(motor_igac.transformadores.keys())
    nombre_proyeccion = st.selectbox("📍 Sistema de Coordenadas del Levantamiento:", lista_proyecciones_disp, index=st.session_state.proy_guardada)
    st.session_state.proy_guardada = lista_proyecciones_disp.index(nombre_proyeccion)
    trans_to_wgs = motor_igac.transformadores_inversos[nombre_proyeccion]

    st.markdown("---")
    st.subheader("1. Carga de Archivos de Campo")
    st.info("💡 **Guía de Formato:** Sube archivos separados por comas o tabuladores (.csv, .txt). El sistema los irá acumulando. Te sugerimos que todos los archivos tengan el formato clásico **PNEZD** (Punto, Norte, Este, Cota, Descripción) para facilitar el emparejamiento.")
    
    archivos_nube = st.file_uploader("📂 Añade tus archivos diarios aquí...", type=['csv', 'txt'], accept_multiple_files=True)
    
    if archivos_nube:
        for archivo in archivos_nube:
            if archivo.name not in st.session_state.nubes_guardadas:
                try:
                    df_temp = procesar_archivo_nube(archivo)
                    st.session_state.nubes_guardadas[archivo.name] = df_temp
                except Exception as e:
                    st.error(f"❌ Error leyendo '{archivo.name}': {e}")
                    
    if st.session_state.nubes_guardadas:
        st.markdown("**📂 Archivos en Memoria RAM:**")
        nombres_archivos = list(st.session_state.nubes_guardadas.keys())
        total_puntos = sum(len(df) for df in st.session_state.nubes_guardadas.values())
        st.success(f"✅ Se han consolidado {len(nombres_archivos)} archivo(s) con un total de {total_puntos} puntos.")
        
        for n_arch in nombres_archivos:
            c_info, c_btn = st.columns([5, 1])
            c_info.write(f"📄 {n_arch} - ({len(st.session_state.nubes_guardadas[n_arch])} puntos)")
            if c_btn.button("🗑️ Quitar", key=f"del_{n_arch}"):
                del st.session_state.nubes_guardadas[n_arch]
                st.rerun()
                
        if st.button("🧹 Limpiar Memoria Completa", type="secondary"):
            st.session_state.nubes_guardadas = {}
            st.rerun()

    if st.session_state.nubes_guardadas:
        st.markdown("---")
        st.subheader("2. Emparejamiento de Columnas por Archivo (Mapping)")
        st.caption("Verifica o selecciona qué columna corresponde a cada coordenada de forma independiente para cada archivo.")
        
        mapeo_archivos = {}
        for n_arch, df_bruto in st.session_state.nubes_guardadas.items():
            with st.expander(f"⚙️ Configurar columnas para: {n_arch} ({len(df_bruto)} puntos)", expanded=(len(st.session_state.nubes_guardadas)==1)):
                st.dataframe(df_bruto.head(5), use_container_width=True)
                cols = ["Ninguna"] + list(df_bruto.columns)
                c1, c2, c3, c4, c5 = st.columns(5)
                
                col_pto = c1.selectbox("Punto / ID", cols, index=1 if len(cols)>1 else 0, key=f"pto_{n_arch}")
                col_e = c2.selectbox("Este (X)", cols, index=2 if len(cols)>2 else 0, key=f"e_{n_arch}")
                col_n = c3.selectbox("Norte (Y)", cols, index=3 if len(cols)>3 else 0, key=f"n_{n_arch}")
                col_z = c4.selectbox("Cota (Z)", cols, index=4 if len(cols)>4 else 0, key=f"z_{n_arch}")
                col_desc = c5.selectbox("Descripción", cols, index=5 if len(cols)>5 else 0, key=f"desc_{n_arch}")
                
                mapeo_archivos[n_arch] = {"pto": col_pto, "e": col_e, "n": col_n, "z": col_z, "desc": col_desc}
        
        st.markdown("---")
        st.subheader("3. Renderizado y Estilo Visual")
        
        col_vis1, col_vis2 = st.columns(2)
        with col_vis1:
            modo_vista = st.radio("Tecnología de visualización:", 
                                ["Agrupado (Clúster de Alto Rendimiento)", 
                                 "Puntos Exactos Individuales"], 
                                horizontal=False)
        with col_vis2:
            opciones_mapa = OPCIONES_MAPA
            tipo_mapa = st.selectbox("Capa Base del Mapa:", list(opciones_mapa.keys()), key="map_nube")
        
        if st.button("🚀 Renderizar Múltiples Nubes", type="primary", use_container_width=True):
            archivos_invalidos = []
            for n_arch, map_val in mapeo_archivos.items():
                if map_val["e"] == "Ninguna" or map_val["n"] == "Ninguna":
                    archivos_invalidos.append(n_arch)
                    
            if archivos_invalidos:
                st.warning(f"⚠️ Debes seleccionar obligatoriamente las columnas Este (X) y Norte (Y) en: {', '.join(archivos_invalidos)}")
            else:
                with st.spinner("Transformando coordenadas y construyendo el sistema de capas espaciales (LayerControl)..."):
                    todas_latitudes = []
                    todas_longitudes = []
                    
                    t_tiles = opciones_mapa[tipo_mapa]["tiles"]
                    t_attr = opciones_mapa[tipo_mapa]["attr"]
                    
                    if t_attr: mapa_nube = folium.Map(zoom_start=18, max_zoom=22, tiles=t_tiles, attr=t_attr)
                    else: mapa_nube = folium.Map(zoom_start=18, max_zoom=22, tiles=t_tiles)
                    
                    colores_archivos = ['#FF8C00', '#0D47A1', '#E53935', '#43A047', '#8E24AA', '#FDD835']
                    color_idx = 0

                    for nombre_archivo, map_val in mapeo_archivos.items():
                        df_bruto = st.session_state.nubes_guardadas[nombre_archivo]
                        df_limpio = asignar_columnas(
                            df_bruto, 
                            None if map_val["pto"] == "Ninguna" else map_val["pto"],
                            map_val["e"],
                            map_val["n"],
                            None if map_val["z"] == "Ninguna" else map_val["z"],
                            None if map_val["desc"] == "Ninguna" else map_val["desc"]
                        )
                        
                        color_actual = colores_archivos[color_idx % len(colores_archivos)]
                        color_idx += 1
                        
                        fg = folium.FeatureGroup(name=nombre_archivo)
                        
                        if "Agrupado" in modo_vista:
                            parent = MarkerCluster(name=nombre_archivo).add_to(fg)
                            radio_p = 5
                        else:
                            parent = fg
                            radio_p = 2
                        
                        for idx, row in df_limpio.iterrows():
                            lon_wgs, lat_wgs = trans_to_wgs.transform(row['Este'], row['Norte'])
                            todas_latitudes.append(lat_wgs)
                            todas_longitudes.append(lon_wgs)
                            
                            html_popup = f"<b>Archivo:</b> {nombre_archivo}<br><b>Punto:</b> {row['Punto']}<br><b>E:</b> {row['Este']:.3f}<br><b>N:</b> {row['Norte']:.3f}<br><b>Z:</b> {row['Cota']:.3f}<br><b>Desc:</b> {row['Descripcion']}"
                            folium.CircleMarker(
                                location=[lat_wgs, lon_wgs],
                                radius=radio_p,
                                color=color_actual,
                                fill=True,
                                fill_color=color_actual,
                                fill_opacity=0.8,
                                popup=folium.Popup(html_popup, max_width=300),
                                tooltip=str(row['Punto'])
                            ).add_to(parent)
                            
                        fg.add_to(mapa_nube)
                    
                    if todas_latitudes and todas_longitudes:
                        mapa_nube.location = [sum(todas_latitudes)/len(todas_latitudes), sum(todas_longitudes)/len(todas_longitudes)]
                        
                    folium.LayerControl().add_to(mapa_nube)
                    st_folium(mapa_nube, width=1100, height=650, returned_objects=[])

# ===================================================================
# MÓDULO DE VOLÚMENES Y DISEÑO 3D
# ===================================================================
elif st.session_state.modo_app in ["Volumenes"]:
    renderizar_banner_proyecto()
    st.title("🚜 Diseño Civil y Volúmenes de Tierra en 3D")
    
    st.header("1. Parámetros de Diseño y Topografía")
    col_img, col_params = st.columns([1, 2.5])
    with col_img:
        mostrar_icono("seccion_tipica.png", "🛣️", width=220, hover_effect=False, shadow=False)
        st.caption("Esquema de Sección Típica (Anchos y Bombeos)")

    with col_params:
        tab_eje, tab_sec, tab_datum = st.tabs(["📏 Alineamiento Eje", "📐 Sección Típica (Bombeo)", "📍 Elevaciones (Datum)"])
        with tab_eje:
            c1, c2, c3 = st.columns(3)
            abs_ini = c1.number_input("Abscisa Inicial (K)", value=0.0, step=10.0, format="%.3f")
            abs_fin = c2.number_input("Abscisa Final (K)", value=40.0, step=10.0, format="%.3f")
            int_long = c3.number_input("Secciones cada (m)", value=10.0, step=5.0, format="%.3f")
        with tab_sec:
            c1, c2, c3 = st.columns(3)
            ancho_izq = c1.number_input("Ancho Izquierdo (m)", value=6.0, step=1.0, format="%.3f")
            ancho_der = c2.number_input("Ancho Derecho (m)", value=6.0, step=1.0, format="%.3f")
            int_transv = c3.number_input("Resolución Transversal (m)", value=2.0, step=1.0, format="%.3f")
            bom_izq = c1.number_input("Pendiente Izquierda (%)", value=-2.0, step=0.5, format="%.3f")
            bom_der = c2.number_input("Pendiente Derecha (%)", value=-2.0, step=0.5, format="%.3f")
        with tab_datum:
            c1, c2 = st.columns(2)
            cota_rasante_ini = c1.number_input("Cota Rasante Inicio (Diseño)", value=500.000, format="%.3f")
            pend_long = c1.number_input("Pendiente Longitudinal Vía (%)", value=0.500, step=0.5, format="%.3f")
            hi_ini = c2.number_input("HI Inicial (Datum Topografía)", value=504.000, format="%.3f")

    if st.button("⚙️ 2. Generar Cartera de Levantamiento", type="secondary", use_container_width=True):
        try:
            st.session_state.cota_rasante_ini_mem = cota_rasante_ini
            st.session_state.pend_long_mem = pend_long
            st.session_state.abs_ini_mem = abs_ini
            st.session_state.bom_izq_memory = bom_izq
            st.session_state.bom_der_memory = bom_der
            
            st.session_state.df_malla_vol = generar_malla_vacia(abs_ini, abs_fin, int_long, ancho_izq, ancho_der, int_transv, hi_ini)
            for i, row in st.session_state.df_malla_vol.iterrows():
                abs_k = row['Abscisa (K)']
                dist = row['Distancia Eje (m)']
                terr_base = 502.0 - (abs_k / 10.0) * 1.2
                terr_elev = terr_base - (dist * 0.15) 
                current_hi = 504.0 if abs_k < 30.0 else 501.0
                st.session_state.df_malla_vol.at[i, 'Lectura Mira (-)'] = round(current_hi - terr_elev, 3)
            st.session_state.calc_vol = False
        except Exception as e:
            st.error(f"❌ Error al generar la malla: {e}")

    if st.session_state.get("df_malla_vol") is not None:
        st.markdown("---")
        st.header("3. Ingreso de Cartera (Cálculos en Vivo)")
        
        if "editor_vol_key" in st.session_state:
            cambios = st.session_state["editor_vol_key"]
            if "edited_rows" in cambios:
                for idx_str, row_changes in cambios["edited_rows"].items():
                    for col, val in row_changes.items():
                        st.session_state.df_malla_vol.loc[int(idx_str), col] = val
                        
        df_calculado = calcular_cotas_seccion(
            st.session_state.df_malla_vol, st.session_state.bom_izq_memory, st.session_state.bom_der_memory,
            st.session_state.cota_rasante_ini_mem, st.session_state.pend_long_mem, st.session_state.abs_ini_mem
        )
        st.session_state.df_malla_vol = df_calculado.copy()
        
        def highlight_eje(row): return ['background-color: rgba(255, 235, 59, 0.3)'] * len(row) if row.get('Distancia Eje (m)', 1) == 0.0 else [''] * len(row)
        
        st.session_state.df_malla_vol = st.data_editor(
            st.session_state.df_malla_vol.style.apply(highlight_eje, axis=1), 
            key="editor_vol_key", num_rows="dynamic", use_container_width=True,
            disabled=["Abscisa (K)", "Distancia Eje (m)", "Cota Terreno (m)", "Cota Diseño (m)"],
            column_config={
                "Abscisa (K)": st.column_config.NumberColumn(format="%.3f"),
                "Distancia Eje (m)": st.column_config.NumberColumn(format="%.3f"),
                "Altura Inst. (HI)": st.column_config.NumberColumn(format="%.3f"),
                "Lectura Mira (-)": st.column_config.NumberColumn(format="%.3f"),
                "Cota Terreno (m)": st.column_config.NumberColumn(format="%.3f"),
                "Cota Diseño (m)": st.column_config.NumberColumn(format="%.3f")
            }
        )

        st.markdown("### 🌐 Modelo 3D en Vivo: Superficies de Terreno y Diseño")
        pivot_diseno = df_calculado.pivot_table(index='Abscisa (K)', columns='Distancia Eje (m)', values='Cota Diseño (m)', dropna=False)
        pivot_terreno = df_calculado.pivot_table(index='Abscisa (K)', columns='Distancia Eje (m)', values='Cota Terreno (m)', dropna=False)
        
        fig3d = go.Figure()
        fig3d.add_trace(go.Surface(z=pivot_diseno.values, x=pivot_diseno.columns.values, y=pivot_diseno.index.values, colorscale=[[0, 'rgba(176, 190, 197, 0.95)'], [1, 'rgba(176, 190, 197, 0.95)']], opacity=0.95, name='Diseño (Vía)', showscale=False))
        if not np.isnan(pivot_terreno.values).all():
            fig3d.add_trace(go.Surface(z=pivot_terreno.values, x=pivot_diseno.columns.values, y=pivot_diseno.index.values, colorscale='YlOrBr', opacity=0.75, name='Terreno', showscale=False))
        fig3d.update_layout(scene=dict(aspectmode='manual', aspectratio=dict(x=1, y=2.5, z=0.5)), margin=dict(l=0, r=0, b=0, t=0), height=550)
        st.plotly_chart(fig3d, use_container_width=True)

        if st.button("🚀 4. Procesar y Calcular Cubicaje Final", type="primary", use_container_width=True):
            try:
                res_df, metricas = calcular_cubicaje_total(df_calculado)
                # OJO: 'Volumen Neto (m³)' que devuelve motor_volumenes YA es
                # acumulado (Vol. Acumulado Corte - Vol. Acumulado Relleno).
                # Aplicarle .cumsum() encima acumulaba dos veces y la curva
                # masa terminaba en 942 m3 donde el valor real era 328,8.
                # La masa acumulada se calcula desde el neto POR TRAMO.
                v_neto_tramo = (res_df['Vol. Corte (m³)'].fillna(0)
                                - res_df['Vol. Relleno (m³)'].fillna(0))
                res_df['Volumen Neto Tramo (m³)'] = v_neto_tramo.round(3)
                res_df['Masa Acumulada (m³)'] = v_neto_tramo.cumsum().round(3)
                
                st.session_state.df_vol_calc = res_df
                st.session_state.met_vol = metricas
                st.session_state.calc_vol = True
            except Exception as e:
                st.error(f"❌ Completa las lecturas numéricas. Detalle: {e}")

    if st.session_state.calc_vol:
        st.success("✅ ¡Cubicaje y Áreas Medias calculadas con éxito!")
        met = st.session_state.met_vol
        df_vol_final = st.session_state.df_vol_calc
        
        colA, colB, colC = st.columns(3)
        colA.metric("🔴 Volumen de Corte Total", f"{met['Corte_Total']:.3f} m³")
        colB.metric("🟢 Volumen de Relleno Total", f"{met['Relleno_Total']:.3f} m³")
        colC.metric("⚖️ Balance Neto", f"{met['Volumen_Neto']:.3f} m³", delta="Superávit" if met['Volumen_Neto']>0 else "Déficit", delta_color="off")
        
        st.subheader("📋 Cuadro de Movimiento de Tierras (Cubicaje)")
        st.dataframe(df_vol_final.style.format("{:.3f}"), use_container_width=True)
        
        st.markdown("---")
        st.subheader("📈 Diagrama de Masas (Curva Masa)")
        fig_masa = go.Figure()
        fig_masa.add_trace(go.Scatter(x=df_vol_final['Abscisa (K)'], y=df_vol_final['Masa Acumulada (m³)'], mode='lines+markers', fill='tozeroy', line=dict(color='#0D47A1', width=3), marker=dict(size=8, color='#FF8C00')))
        fig_masa.update_layout(xaxis_title='Abscisa (Distancia en K)', yaxis_title='Volumen Neto Acumulado (m³)', height=450, plot_bgcolor='rgba(245, 245, 245, 0.8)')
        st.plotly_chart(fig_masa, use_container_width=True)
        
        st.markdown("---")
        st.subheader("📐 Visor de Perfiles Transversales")
        abs_plot = st.selectbox("Seleccione Abscisa a Visualizar:", df_calculado['Abscisa (K)'].unique())
        df_plot = df_calculado[df_calculado['Abscisa (K)'] == abs_plot].copy().dropna(subset=['Cota Terreno (m)', 'Cota Diseño (m)']).sort_values(by='Distancia Eje (m)').reset_index(drop=True)
        
        if not df_plot.empty:
            fig_visual = crear_figura_seccion_plotly(df_plot, abs_plot)
            fig_visual.update_layout(height=550)
            st.plotly_chart(fig_visual, use_container_width=True)
            
        st.markdown("---")
        with st.expander("📥 Exportar Memorias Matemáticas y Planos (PDF / LaTeX)", expanded=True):
            st.info("💡 El motor LaTeX redactará el informe incluyendo la Curva Masa y el dictamen técnico. Si activa la casilla inferior, se renderizarán todas las secciones en grillas (Bottom-Up).")
            imprimir_secciones = st.checkbox("Generar anexo gráfico con todas las Secciones Transversales (Aumenta el tiempo de compilación)", value=True)
            
            if ficha_incompleta():
                st.warning("📋 La Ficha Técnica está incompleta: " +
                           ", ".join(ficha_incompleta()) +
                           ". El informe saldrá con esos campos en blanco.")

            if st.button("🔨 Construir y Compilar Documento Oficial", type="primary", use_container_width=True, key="btn_vol"):
                with st.spinner("Construyendo gráficas y ejecutando motor LaTeX..."):
                    p_act = st.session_state.get('proyecto_actual') or "Proyecto"
                    salida = dir_reportes()
                    metadatos = construir_metadatos(
                        huella=huella_datos(df_calculado, df_vol_final))
                    params_vol = {
                        "material": param_ficha("material_volumenes"),
                        "capacidad_volqueta": param_ficha("capacidad_volqueta"),
                        "acarreo_libre": param_ficha("acarreo_libre"),
                    }

                    pdf_bytes, tex_vol, debug_msg = cachear_pdf_volumenes(
                        df_calculado, df_vol_final, met, p_act, imprimir_secciones,
                        salida, metadatos, construir_equipo(), params_vol)
                    
                    st.session_state.vol_pdf_bytes = pdf_bytes
                    st.session_state.vol_tex_code = tex_vol
                    st.session_state.vol_debug_msg = debug_msg
            
            if st.session_state.get('vol_pdf_bytes'):
                st.success("✅ ¡El documento PDF fue ensamblado exitosamente!")
                b64_pdf = base64.b64encode(st.session_state.vol_pdf_bytes).decode('utf-8')
                st.markdown(f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="800" type="application/pdf"></iframe>', unsafe_allow_html=True)
                col1, col2 = st.columns(2)
                col1.download_button("📄 Descargar PDF Oficial", st.session_state.vol_pdf_bytes, f"Cubicaje_{st.session_state.get('proyecto_actual')}.pdf", "application/pdf", use_container_width=True)
                col2.download_button("📄 Descargar Código LaTeX (.TEX)", st.session_state.vol_tex_code, f"Cubicaje_{st.session_state.get('proyecto_actual')}.tex", "text/plain", use_container_width=True)
            elif st.session_state.get('vol_tex_code'):
                st.warning(f"⚠️ Falló la compilación del PDF por falta de TeX Live local. Diagnóstico:\n{st.session_state.vol_debug_msg}")
                st.download_button("📄 Descargar Código LaTeX (.TEX)", st.session_state.vol_tex_code, f"Cubicaje_{st.session_state.get('proyecto_actual')}.tex", "text/plain", use_container_width=True)


# ------------------ MÓDULOS DE NIVELACIÓN NORMAL ------------------
elif st.session_state.modo_app in ["Niv_Cerrada", "Niv_Abierta"]:
    renderizar_banner_proyecto()
            
    if st.session_state.modo_app == "Niv_Cerrada":
        st.title("🔄 Nivelación Geométrica Cerrada")
        st.header("1. Datos de Arranque (Datum)")
        st.session_state.niv_cota_datum_c = st.number_input("Elevación Inicial (Cota del BM de Partida)", value=st.session_state.niv_cota_datum_c, format="%.3f")
        cota_datum = st.session_state.niv_cota_datum_c
        cota_llegada = None 
        st.header("2. Ingreso de Cartera de Nivelación")
        st.session_state.df_niv_cerrada_campo = st.data_editor(st.session_state.df_niv_cerrada_campo, num_rows="dynamic", use_container_width=True)
        df_niv_activo = st.session_state.df_niv_cerrada_campo
    else:
        st.title("🛤️ Nivelación Geométrica Abierta (Con Control)")
        col1, col2 = st.columns(2)
        with col1:
            st.header("1. Arranque (Datum)")
            st.session_state.niv_cota_datum_a = st.number_input("Elevación Inicial (BM de Partida)", value=st.session_state.niv_cota_datum_a, format="%.3f")
            cota_datum = st.session_state.niv_cota_datum_a
        with col2:
            st.header("2. Control Final (Llegada)")
            st.session_state.niv_cota_llegada = st.number_input("Elevación Conocida (BM de Llegada)", value=st.session_state.niv_cota_llegada, format="%.3f")
            cota_llegada = st.session_state.niv_cota_llegada
        st.header("3. Ingreso de Cartera de Nivelación")
        st.session_state.df_niv_abierta_campo = st.data_editor(st.session_state.df_niv_abierta_campo, num_rows="dynamic", use_container_width=True)
        df_niv_activo = st.session_state.df_niv_abierta_campo

    estaciones_con_foto_niv = df_niv_activo[df_niv_activo["📸 Tomar_Fotos"] == True]["Estaca / Punto"].unique()
    if len(estaciones_con_foto_niv) > 0:
        st.markdown("---")
        st.header("📸 4. Registro Fotográfico de Puntos Verticales")
        tabs = st.tabs([f"Estación {est}" for est in estaciones_con_foto_niv])
        secuencia_fotos = [{"paso": 1, "sufijo": "Placa-Punto"}, {"paso": 2, "sufijo": "Norte"}, {"paso": 3, "sufijo": "Este"}, {"paso": 4, "sufijo": "Sur"}, {"paso": 5, "sufijo": "Oeste"}]
        
        for i, est in enumerate(estaciones_con_foto_niv):
            with tabs[i]:
                estado_paso = f"paso_foto_niv_{est}"
                if estado_paso not in st.session_state: st.session_state[estado_paso] = 0
                paso_actual = st.session_state[estado_paso]
                if paso_actual < 5:
                    st.progress(paso_actual / 5.0)
                    foto = st.camera_input(f"Capturar {secuencia_fotos[paso_actual]['sufijo']}", key=f"cam_niv_{est}_{paso_actual}")
                    if foto is not None:
                        carpeta = dir_fotos("Fotos_Nivelacion", est)
                        nombre = f"{est}_{secuencia_fotos[paso_actual]['paso']}_{secuencia_fotos[paso_actual]['sufijo']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        # Estampa estación, orientación, fecha y proyecto sobre la
                        # imagen. Si falla, guarda la foto sin estampar en vez de
                        # perderla.
                        guardar_foto_estampada(
                            foto, os.path.join(carpeta, nombre), est,
                            secuencia_fotos[paso_actual]['sufijo'],
                            proyecto=param_ficha("nombre_proyecto")
                                     or st.session_state.get("proyecto_actual"))
                        st.session_state[estado_paso] += 1
                        st.rerun()
                else: st.success(f"🎉 Registro completado.")

    if st.button("🚀 Calcular Nivelación", type="primary"):
        try:
            puntos = df_niv_activo["Estaca / Punto"].tolist()
            v_atras = df_niv_activo["Vista Atrás (V+)"].tolist()
            v_intermedia = df_niv_activo["Vista Intermedia (V-)"].tolist()
            v_adelante = df_niv_activo["Vista Adelante (V-)"].tolist()
            
            res_df, metricas = calcular_cartera_nivelacion(puntos, v_atras, v_intermedia, v_adelante, cota_datum, cota_llegada)
            
            if st.session_state.modo_app == "Niv_Cerrada":
                st.session_state.df_niv_calc_cerrada = res_df
                st.session_state.met_niv_cerrada = metricas
                st.session_state.calc_niv_cerrada = True
            else:
                st.session_state.df_niv_calc_abierta = res_df
                st.session_state.met_niv_abierta = metricas
                st.session_state.calc_niv_abierta = True
                
        except Exception as e:
            st.error(f"❌ Error en el cálculo: {e}")

    calc_niv_done = st.session_state.calc_niv_cerrada if st.session_state.modo_app == "Niv_Cerrada" else st.session_state.calc_niv_abierta
    if calc_niv_done:
        st.success("✅ ¡Cálculo y Compensación de Cotas ejecutado con éxito!")
        met = st.session_state.met_niv_cerrada if st.session_state.modo_app == "Niv_Cerrada" else st.session_state.met_niv_abierta
        df_calc = st.session_state.df_niv_calc_cerrada if st.session_state.modo_app == "Niv_Cerrada" else st.session_state.df_niv_calc_abierta
        
        pdf_bytes_key = 'niv_cerrada_pdf_bytes' if st.session_state.modo_app == "Niv_Cerrada" else 'niv_abierta_pdf_bytes'
        tex_code_key = 'niv_cerrada_tex_code' if st.session_state.modo_app == "Niv_Cerrada" else 'niv_abierta_tex_code'
        debug_msg_key = 'niv_cerrada_debug_msg' if st.session_state.modo_app == "Niv_Cerrada" else 'niv_abierta_debug_msg'

        st.subheader("📋 Reporte Técnico de Cierre Altimétrico")
        df_rep_niv = pd.DataFrame({
            "Parámetro Evaluado": ["Sumatoria Vista Atrás (ΣV+)", "Sumatoria Vista Adelante (ΣV-)", "Cota Final Cruda (Sin Ajuste)", "Cota Teórica Esperada", "Error de Cierre Altimétrico (m)", "Error de Cierre Altimétrico (mm)"],
            "Valor Obtenido": [f"{met['sum_vista_atras']:.3f} m", f"{met['sum_vista_adelante']:.3f} m", f"{met['cota_final_cruda']:.3f} m", f"{met['cota_teorica_final']:.3f} m", f"{met['error_cierre_m']:.4f} m", f"{met['error_cierre_mm']:.1f} mm"]
        })
        st.table(df_rep_niv)
        
        st.subheader("📋 Cartera Altimétrica Compensada")
        st.dataframe(df_calc, use_container_width=True)
        
        st.markdown("---")
        st.subheader("📈 Perfil Topográfico de Nivelación")
        df_plot = df_calc[['Estaca / Punto', 'Cota Ajustada']].copy()
        df_plot['Cota Ajustada'] = df_plot['Cota Ajustada'].astype(float)
        
        fig_perf = go.Figure()
        fig_perf.add_trace(go.Scatter(x=df_plot['Estaca / Punto'], y=df_plot['Cota Ajustada'], mode='lines+markers', line=dict(color='#FF8C00', width=3), marker=dict(size=10)))
        fig_perf.update_layout(xaxis_title='Estaciones / Puntos Visados', yaxis_title='Elevación Ajustada (msnm)', height=450)
        st.plotly_chart(fig_perf, use_container_width=True)

        st.markdown("---")
        with st.expander("📥 Exportar Memorias Matemáticas y Planos (PDF / LaTeX)", expanded=True):
            st.info("💡 El motor LaTeX redactará el informe técnico altimétrico incluyendo el perfil topográfico compensado.")
            
            if ficha_incompleta():
                st.warning("📋 La Ficha Técnica está incompleta: " +
                           ", ".join(ficha_incompleta()) +
                           ". El informe saldrá con esos campos en blanco.")

            if st.button("🔨 Construir y Compilar Documento Oficial", type="primary", use_container_width=True, key="btn_niv"):
                with st.spinner("Construyendo gráficas y ejecutando motor LaTeX..."):
                    dir_fotos_proy = dir_fotos("Fotos_Nivelacion")
                    fotos_tomadas = sorted(glob.glob(os.path.join(dir_fotos_proy, "*", "*.jpg")))
                    tipo_niv = "Nivelación Cerrada" if st.session_state.modo_app == "Niv_Cerrada" else "Nivelación Abierta con Control"
                    p_act = st.session_state.get('proyecto_actual') or 'Altimetria'
                    salida = dir_reportes()
                    metadatos = construir_metadatos(huella=huella_datos(df_calc))
                    params_niv = {
                        "longitud_km": param_ficha("longitud_nivelada_km"),
                        "orden": param_ficha("orden_nivelacion"),
                    }
                    bm_partida = {"codigo": param_ficha("punto_amarre"),
                                  "cota": f"{cota_datum:.3f}",
                                  "entidad": param_ficha("fuente_amarre")}

                    pdf_bytes, tex_niv, debug_msg = cachear_pdf_altimetria(
                        df_calc, met, p_act, tipo_niv, fotos_tomadas,
                        salida, firma_archivos(fotos_tomadas),
                        metadatos, construir_equipo(), params_niv, bm_partida)
                    
                    st.session_state[pdf_bytes_key] = pdf_bytes
                    st.session_state[tex_code_key] = tex_niv
                    st.session_state[debug_msg_key] = debug_msg
                    
            if st.session_state.get(pdf_bytes_key):
                st.success("✅ ¡El documento PDF fue ensamblado exitosamente!")
                b64_pdf = base64.b64encode(st.session_state[pdf_bytes_key]).decode('utf-8')
                st.markdown(f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="800" type="application/pdf"></iframe>', unsafe_allow_html=True)
                col1, col2 = st.columns(2)
                col1.download_button("📄 Descargar PDF Oficial", st.session_state[pdf_bytes_key], f"Nivelacion_{st.session_state.get('proyecto_actual') or 'Altimetria'}.pdf", "application/pdf", use_container_width=True)
                col2.download_button("📄 Descargar Código LaTeX (.TEX)", st.session_state[tex_code_key], f"Nivelacion_{st.session_state.get('proyecto_actual') or 'Altimetria'}.tex", "text/plain", use_container_width=True)
            elif st.session_state.get(tex_code_key):
                st.warning(f"⚠️ Falló la compilación del PDF por falta de TeX Live local. Diagnóstico:\n{st.session_state[debug_msg_key]}")
                st.download_button("📄 Descargar Código LaTeX (.TEX)", st.session_state[tex_code_key], f"Nivelacion_{st.session_state.get('proyecto_actual') or 'Altimetria'}.tex", "text/plain", use_container_width=True)

# ===================================================================
# ENTORNO DE CÁLCULO DE POLIGONALES (PLANIMETRÍA)
# ===================================================================
elif st.session_state.modo_app in ["Cerrada", "Abierta"]:
    renderizar_banner_proyecto()
    
    if st.session_state.modo_app == "Cerrada":
        st.title("🔄 Poligonal Cerrada")
    else:
        st.title("🛤️ Poligonal Abierta con Control")
            
    lista_proyecciones_disp = list(motor_igac.transformadores.keys())
    if "proy_guardada" not in st.session_state: st.session_state.proy_guardada = 0
    nombre_proyeccion = st.selectbox("📍 Sistema de Coordenadas (Estándar IGAC):", lista_proyecciones_disp, index=st.session_state.proy_guardada)
    st.session_state.proy_guardada = lista_proyecciones_disp.index(nombre_proyeccion)

    st.subheader(f"🛰️ Centro de Captura GPS -> Proyectando a: {nombre_proyeccion}")
    col_gps1, col_gps2 = st.columns([1, 2])
    with col_gps1: location = streamlit_geolocation()
    
    with col_gps2:
        if location and location['latitude'] is not None:
            lat_gps, lon_gps, alt_gps = location['latitude'], location['longitude'], location['altitude'] or 100.0
            resultados_conversion = motor_igac.convertir_coordenada(lat_gps, lon_gps)
            x_plana = resultados_conversion[nombre_proyeccion]["Este"]
            y_plana = resultados_conversion[nombre_proyeccion]["Norte"]
            
            st.success(f"Satélite Vinculado: Lat {lat_gps:.9f}°, Lon {lon_gps:.9f}°")
            
            if st.session_state.modo_app == "Cerrada": opciones_destino = ["Punto Ocupado (Arranque)", "Punto de Referencia (Visual)"]
            else: opciones_destino = ["Ocupado Inicial (Arranque)", "Referencia Atrás (Visual Arranque)", "Ocupado Final (Llegada)", "Referencia Adelante (Visual Llegada)"]
                
            destino = st.selectbox("¿A qué punto desea asignar esta coordenada plana?", opciones_destino)
            if st.button("📥 Aplicar Coordenada a Casilla", type="primary"):
                if destino == "Punto Ocupado (Arranque)": 
                    st.session_state.c_e_ini, st.session_state.c_n_ini, st.session_state.c_z_ini = x_plana, y_plana, alt_gps
                elif destino == "Punto de Referencia (Visual)": 
                    st.session_state.c_e_ref, st.session_state.c_n_ref, st.session_state.c_z_ref = x_plana, y_plana, alt_gps
                elif destino == "Ocupado Inicial (Arranque)": 
                    st.session_state.a_e_ini, st.session_state.a_n_ini, st.session_state.a_z_ini = x_plana, y_plana, alt_gps
                elif destino == "Referencia Atrás (Visual Arranque)": 
                    st.session_state.a_e_ref_arr, st.session_state.a_n_ref_arr, st.session_state.a_z_ref_arr = x_plana, y_plana, alt_gps
                elif destino == "Ocupado Final (Llegada)": 
                    st.session_state.a_e_fin, st.session_state.a_n_fin, st.session_state.a_z_fin = x_plana, y_plana, alt_gps
                elif destino == "Referencia Adelante (Visual Llegada)": 
                    st.session_state.a_e_ref_lleg, st.session_state.a_n_ref_lleg, st.session_state.a_z_ref_lleg = x_plana, y_plana, alt_gps
                st.rerun() 
        else: st.caption("Esperando activación del sensor GPS...")

    st.markdown("---")
    
    if st.session_state.modo_app == "Cerrada":
        st.header("1. Datos de Arranque (Amarre)")
        st.session_state.c_tipo_amarre = st.radio("Método de orientación inicial:", ["Dos Coordenadas Conocidas", "Una Coordenada y Azimut"], index=0 if st.session_state.c_tipo_amarre=="Dos Coordenadas Conocidas" else 1)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.subheader("📍 Punto Ocupado")
            st.session_state.c_n_ini = st.number_input("Norte (Y)", value=st.session_state.c_n_ini, format="%.3f")
            st.session_state.c_e_ini = st.number_input("Este (X)", value=st.session_state.c_e_ini, format="%.3f")
            st.session_state.c_z_ini = st.number_input("Cota (Z)", value=st.session_state.c_z_ini, format="%.3f")
        with col2:
            if st.session_state.c_tipo_amarre == "Dos Coordenadas Conocidas":
                st.subheader("🎯 Punto de Referencia")
                st.session_state.c_n_ref = st.number_input("Norte Ref (Y)", value=st.session_state.c_n_ref, format="%.3f")
                st.session_state.c_e_ref = st.number_input("Este Ref (X)", value=st.session_state.c_e_ref, format="%.3f")
                st.session_state.c_z_ref = st.number_input("Cota Ref (Z)", value=st.session_state.c_z_ref, format="%.3f")
                azimut_input = None
            else:
                st.subheader("🧭 Azimut de Partida")
                st.session_state.c_az_g = st.number_input("Grados (°)", value=st.session_state.c_az_g, step=1)
                st.session_state.c_az_m = st.number_input("Minutos (')", value=st.session_state.c_az_m, step=1)
                st.session_state.c_az_s = st.number_input("Segundos (\")", value=st.session_state.c_az_s, format="%.2f")
                azimut_input = (st.session_state.c_az_g, st.session_state.c_az_m, st.session_state.c_az_s)
        with col3:
            st.subheader("⚙️ Configuración")
            st.session_state.c_tipo_ang = st.selectbox("Orientación de Ángulos", ["exterior", "interior"], index=0 if st.session_state.c_tipo_ang=="exterior" else 1)
            
        st.header("2. Ingreso de Cartera de Campo")
        st.session_state.df_cerrada_campo = st.data_editor(st.session_state.df_cerrada_campo, num_rows="dynamic", use_container_width=True)

    else:
        st.header("1. Datos de Control Geodésico")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🏁 Arranque")
            st.session_state.a_tipo_amarre_arr = st.radio("Orientación de Entrada:", ["Dos Coordenadas Conocidas", "Una Coordenada y Azimut"], index=0 if st.session_state.a_tipo_amarre_arr=="Dos Coordenadas Conocidas" else 1)
            st.markdown("**Punto Ocupado Inicial (GPS-09)**")
            st.session_state.a_n_ini = st.number_input("Norte (Y) Arranque", value=st.session_state.a_n_ini, format="%.3f")
            st.session_state.a_e_ini = st.number_input("Este (X) Arranque", value=st.session_state.a_e_ini, format="%.3f")
            st.session_state.a_z_ini = st.number_input("Cota (Z) Arranque", value=st.session_state.a_z_ini, format="%.3f")
            
            if st.session_state.a_tipo_amarre_arr == "Dos Coordenadas Conocidas":
                st.markdown("**Referencia Atrás (GPS-10)**")
                st.session_state.a_n_ref_arr = st.number_input("Norte (Y) Ref. Atrás", value=st.session_state.a_n_ref_arr, format="%.3f")
                st.session_state.a_e_ref_arr = st.number_input("Este (X) Ref. Atrás", value=st.session_state.a_e_ref_arr, format="%.3f")
                st.session_state.a_z_ref_arr = st.number_input("Cota (Z) Ref. Atrás", value=st.session_state.a_z_ref_arr, format="%.3f")
                azimut_arr_input = None
            else:
                st.markdown("**🧭 Azimut de Partida**")
                st.session_state.a_azA_g = st.number_input("Grados (°)", value=st.session_state.a_azA_g, step=1)
                st.session_state.a_azA_m = st.number_input("Minutos (')", value=st.session_state.a_azA_m, step=1)
                st.session_state.a_azA_s = st.number_input("Segundos (\")", value=st.session_state.a_azA_s, format="%.2f")
                azimut_arr_input = (st.session_state.a_azA_g, st.session_state.a_azA_m, st.session_state.a_azA_s)

        with col2:
            st.subheader("🎯 Llegada")
            st.session_state.a_tipo_amarre_lleg = st.radio("Orientación de Salida:", ["Dos Coordenadas Conocidas", "Una Coordenada y Azimut"], index=0 if st.session_state.a_tipo_amarre_lleg=="Dos Coordenadas Conocidas" else 1)
            st.markdown("**Punto Ocupado Final (GPS-06)**")
            st.session_state.a_n_fin = st.number_input("Norte (Y) Llegada", value=st.session_state.a_n_fin, format="%.3f")
            st.session_state.a_e_fin = st.number_input("Este (X) Llegada", value=st.session_state.a_e_fin, format="%.3f")
            st.session_state.a_z_fin = st.number_input("Cota (Z) Llegada", value=st.session_state.a_z_fin, format="%.3f")
            
            if st.session_state.a_tipo_amarre_lleg == "Dos Coordenadas Conocidas":
                st.markdown("**Referencia Adelante (GPS-05)**")
                st.session_state.a_n_ref_lleg = st.number_input("Norte (Y) Ref. Adelante", value=st.session_state.a_n_ref_lleg, format="%.3f")
                st.session_state.a_e_ref_lleg = st.number_input("Este (X) Ref. Adelante", value=st.session_state.a_e_ref_lleg, format="%.3f")
                st.session_state.a_z_ref_lleg = st.number_input("Cota (Z) Ref. Adelante", value=st.session_state.a_z_ref_lleg, format="%.3f")
                azimut_lleg_input = None
            else:
                st.markdown("**🧭 Azimut de Llegada**")
                st.session_state.a_azL_g = st.number_input("Grados (°)", value=st.session_state.a_azL_g, step=1)
                st.session_state.a_azL_m = st.number_input("Minutos (')", value=st.session_state.a_azL_m, step=1)
                st.session_state.a_azL_s = st.number_input("Segundos (\")", value=st.session_state.a_azL_s, format="%.2f")
                azimut_lleg_input = (st.session_state.a_azL_g, st.session_state.a_azL_m, st.session_state.a_azL_s)

        st.header("2. Ingreso de Cartera de Campo")
        st.session_state.df_abierta_campo = st.data_editor(st.session_state.df_abierta_campo, num_rows="dynamic", use_container_width=True)

    df_activo = st.session_state.df_cerrada_campo if st.session_state.modo_app == "Cerrada" else st.session_state.df_abierta_campo
    estaciones_con_foto = df_activo[df_activo["📸 Tomar_Fotos"] == True]["Estacionado"].unique()
    
    if len(estaciones_con_foto) > 0:
        st.markdown("---")
        st.header("📸 3. Registro Fotográfico Panorámico")
        tabs = st.tabs([f"Estación {est}" for est in estaciones_con_foto])
        secuencia_fotos = [{"paso": 1, "sufijo": "Punto"}, {"paso": 2, "sufijo": "Norte"}, {"paso": 3, "sufijo": "Este"}, {"paso": 4, "sufijo": "Sur"}, {"paso": 5, "sufijo": "Oeste"}]
        
        for i, est in enumerate(estaciones_con_foto):
            with tabs[i]:
                estado_paso = f"paso_foto_{est}"
                if estado_paso not in st.session_state: st.session_state[estado_paso] = 0
                paso_actual = st.session_state[estado_paso]
                if paso_actual < 5:
                    st.progress(paso_actual / 5.0)
                    foto = st.camera_input(f"Capturar {secuencia_fotos[paso_actual]['sufijo']}", key=f"cam_{est}_{paso_actual}")
                    if foto is not None:
                        carpeta = dir_fotos("Fotos_Cartera", est)
                        nombre = f"{est}_{secuencia_fotos[paso_actual]['paso']}_{secuencia_fotos[paso_actual]['sufijo']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        # Estampa estación, orientación, fecha y proyecto sobre la
                        # imagen. Si falla, guarda la foto sin estampar en vez de
                        # perderla.
                        guardar_foto_estampada(
                            foto, os.path.join(carpeta, nombre), est,
                            secuencia_fotos[paso_actual]['sufijo'],
                            proyecto=param_ficha("nombre_proyecto")
                                     or st.session_state.get("proyecto_actual"))
                        st.session_state[estado_paso] += 1
                        st.rerun()
                else: st.success(f"🎉 Registro completado.")

    if st.button("🚀 Calcular Levantamiento", type="primary"):
        df_calculo = st.session_state.df_cerrada_campo if st.session_state.modo_app == "Cerrada" else st.session_state.df_abierta_campo
        try:
            estacionado, punto_obs = df_calculo["Estacionado"].tolist(), df_calculo["Pto_Obs"].tolist()
            ang_h = list(zip(df_calculo["Hz_G"], df_calculo["Hz_M"], df_calculo["Hz_S"]))
            ang_z = list(zip(df_calculo["Z_G"], df_calculo["Z_M"], df_calculo["Z_S"]))
            d_inc, hi, hr = df_calculo["Dist_Inc"].tolist(), df_calculo["hi"].tolist(), df_calculo["hr"].tolist()
            
            if st.session_state.modo_app == "Cerrada":
                res_c, res_a, res_m = poligonal_3d_v2_5(
                    estacionado, punto_obs, ang_h, ang_z, d_inc, hi, hr, 
                    (st.session_state.c_e_ini, st.session_state.c_n_ini, st.session_state.c_z_ini), 
                    (st.session_state.c_e_ref, st.session_state.c_n_ref, st.session_state.c_z_ref) if st.session_state.c_tipo_amarre == "Dos Coordenadas Conocidas" else None, 
                    azimut_input if st.session_state.c_tipo_amarre != "Dos Coordenadas Conocidas" else None, 
                    st.session_state.c_tipo_ang)
                st.session_state.df_ajuste_cerrada = res_a
                st.session_state.metricas_cerrada = res_m
                st.session_state.calc_cerrada = True
            else:
                res_c, res_a, res_m = poligonal_abierta_control(
                    estacionado, punto_obs, ang_h, ang_z, d_inc, hi, hr, 
                    (st.session_state.a_e_ini, st.session_state.a_n_ini, st.session_state.a_z_ini), 
                    (st.session_state.a_e_fin, st.session_state.a_n_fin, st.session_state.a_z_fin), 
                    (st.session_state.a_e_ref_arr, st.session_state.a_n_ref_arr, st.session_state.a_z_ref_arr) if st.session_state.a_tipo_amarre_arr == "Dos Coordenadas Conocidas" else None, 
                    azimut_arr_input, 
                    (st.session_state.a_e_ref_lleg, st.session_state.a_n_ref_lleg, st.session_state.a_z_ref_lleg) if st.session_state.a_tipo_amarre_lleg == "Dos Coordenadas Conocidas" else None, 
                    azimut_lleg_input)
                st.session_state.df_ajuste_abierta = res_a
                st.session_state.metricas_abierta = res_m
                st.session_state.calc_abierta = True
                
        except Exception as e:
            st.error(f"❌ Error en el cálculo: {e}")

    calc_done = st.session_state.calc_cerrada if st.session_state.modo_app == "Cerrada" else st.session_state.calc_abierta
    if calc_done:
        st.success("✅ ¡Cálculo y Ajuste ejecutado con éxito!")
        met = st.session_state.metricas_cerrada if st.session_state.modo_app == "Cerrada" else st.session_state.metricas_abierta
        df_ajuste = st.session_state.df_ajuste_cerrada if st.session_state.modo_app == "Cerrada" else st.session_state.df_ajuste_abierta
        df_campo = st.session_state.df_cerrada_campo if st.session_state.modo_app == "Cerrada" else st.session_state.df_abierta_campo
        
        pdf_bytes_key = 'cerrada_pdf_bytes' if st.session_state.modo_app == "Cerrada" else 'abierta_pdf_bytes'
        tex_code_key = 'cerrada_tex_code' if st.session_state.modo_app == "Cerrada" else 'abierta_tex_code'
        debug_msg_key = 'cerrada_debug_msg' if st.session_state.modo_app == "Cerrada" else 'abierta_debug_msg'

        st.subheader("📋 1. Reporte Técnico de Cierre")
        df_comparativo = pd.DataFrame({
            "Parámetro de Cierre": ["Error Angular", "Error Horizontal Este (X)", "Error Horizontal Norte (Y)", "Error Vertical Cota (Z)", "Error Lineal Total", "Precisión Horizontal", "Precisión Vertical"],
            "Antes del Ajuste": [decimal_a_dms(met["err_ang_ant"]), f"{met['err_e_ant']:.5f} m", f"{met['err_n_ant']:.5f} m", f"{met.get('err_v_ant', 0):.5f} m", f"{met['err_h_ant']:.5f} m", f"1 en {int(met['prec_h']) if met['prec_h'] != 0 else 0}", f"1 en {int(met.get('prec_v', 0)) if met.get('prec_v', 0) != 0 else 0}"],
            "Después del Ajuste": [decimal_a_dms(met["err_ang_des"]), f"{met['err_e_des']:.5f} m", f"{met['err_n_des']:.5f} m", f"{met.get('err_v_des', 0):.5f} m", f"{met['err_h_des']:.5f} m", "Exacta (Compensada)", "Exacta (Compensada)"]
        })
        st.table(df_comparativo)
        
        colA, colB = st.columns(2)
        with colA: st.dataframe(df_campo, use_container_width=True)
        with colB: st.dataframe(df_ajuste, use_container_width=True)

        st.markdown("---")
        st.subheader("📐 Plano Planimétrico Profesional (Local)")
        tipo_plano = "Plano Topográfico - Poligonal Cerrada" if st.session_state.modo_app == "Cerrada" else "Plano Topográfico - Poligonal Abierta"
        
        try:
            fig_plano = generar_plano_profesional(df_ajuste, titulo=tipo_plano)
            st.pyplot(fig_plano)
            ruta_plano_export = os.path.join(dir_reportes(), "Plano_Exportado.png")
            fig_plano.savefig(ruta_plano_export, dpi=300, bbox_inches='tight')
            # Sin close() cada rerun de esta pantalla deja una figura viva
            plt.close(fig_plano)
        except Exception as e:
            st.error(f"⚠️ Hubo un problema al generar el plano CAD: {e}")
            ruta_plano_export = None

        with st.expander("📥 Exportar Datos de Levantamiento (CAD / GIS / Reportes)", expanded=True):
            st.markdown("Seleccione el formato oficial de descarga para sus programas de diseño de oficina:")
            col_kml, col_dxf, col_shp, col_tex = st.columns(4)
            
            trans_to_wgs = motor_igac.transformadores_inversos[nombre_proyeccion]
            data_kml = generar_kml(df_ajuste, trans_to_wgs)
            data_dxf = generar_dxf(df_ajuste)
            data_shp = generar_shp_zip(df_ajuste, nombre_proyeccion)
            
            if ficha_incompleta():
                st.warning("📋 La Ficha Técnica está incompleta: " +
                           ", ".join(ficha_incompleta()) +
                           ". El informe saldrá con esos campos en blanco.")

            if st.button("🔨 Construir y Compilar Documento Oficial", type="primary", use_container_width=True, key="btn_poli"):
                with st.spinner("Compilando Documento LaTeX..."):
                    dir_fotos_proy = dir_fotos("Fotos_Cartera")
                    fotos_tomadas = sorted(glob.glob(os.path.join(dir_fotos_proy, "*", "*.jpg")))
                    p_act = st.session_state.get('proyecto_actual') or 'Poli'
                    salida = dir_reportes()
                    metadatos = construir_metadatos(
                        sistema_referencia=nombre_proyeccion,
                        huella=huella_datos(df_campo, df_ajuste))
                    params_poli = {
                        "altura_elipsoidal": param_ficha("altura_elipsoidal"),
                        "precision_exigida": param_ficha("precision_exigida"),
                        "factor_tolerancia": param_ficha("factor_tolerancia"),
                    }
                    # La firma incluye el plano y las fotos: si cambian, la
                    # caché se invalida y no se reutiliza un PDF viejo.
                    firma = firma_archivos([ruta_plano_export] + list(fotos_tomadas))

                    pdf_bytes, data_tex, debug_msg = cachear_pdf_poli(
                        df_campo, df_ajuste, met, p_act, ruta_plano_export,
                        fotos_tomadas, st.session_state.modo_app,
                        salida, firma, metadatos, construir_equipo(), params_poli,
                        coords_desde_ajuste(df_ajuste), este_medio(df_ajuste),
                        lados_para_memoria(met, df_campo, df_ajuste,
                                           st.session_state.modo_app))
                    
                    st.session_state[pdf_bytes_key] = pdf_bytes
                    st.session_state[tex_code_key] = data_tex
                    st.session_state[debug_msg_key] = debug_msg

            if st.session_state.get(pdf_bytes_key):
                st.success("✅ ¡El documento PDF fue ensamblado exitosamente!")
                b64_pdf = base64.b64encode(st.session_state[pdf_bytes_key]).decode('utf-8')
                st.markdown(f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="800" type="application/pdf"></iframe>', unsafe_allow_html=True)
            elif st.session_state.get(tex_code_key) and not st.session_state.get(pdf_bytes_key):
                st.warning(f"⚠️ Falló la compilación del PDF. Diagnóstico:\n{st.session_state[debug_msg_key]}")
            
            with col_kml: st.download_button(label="🌍 Google Earth (.KML)", data=data_kml, file_name=f"{st.session_state.get('proyecto_actual') or 'Poli'}_Plano.kml", mime="application/vnd.google-earth.kml+xml", use_container_width=True)
            with col_dxf: st.download_button(label="📐 AutoCAD (.DXF)", data=data_dxf, file_name=f"{st.session_state.get('proyecto_actual') or 'Poli'}_CAD.dxf", mime="application/dxf", use_container_width=True)
            with col_shp: st.download_button(label="🗺️ Shapefile (.ZIP)", data=data_shp, file_name=f"{st.session_state.get('proyecto_actual') or 'Poli'}_GIS.zip", mime="application/zip", use_container_width=True)
            with col_tex: 
                if st.session_state.get(pdf_bytes_key):
                    st.download_button(label="📄 Descargar PDF Oficial", data=st.session_state[pdf_bytes_key], file_name=f"Reporte_{st.session_state.get('proyecto_actual') or 'Poli'}.pdf", mime="application/pdf", use_container_width=True)
                elif st.session_state.get(tex_code_key):
                    st.download_button(label="📄 Descargar Código LaTeX (.TEX)", data=st.session_state[tex_code_key], file_name=f"Reporte_{st.session_state.get('proyecto_actual') or 'Poli'}.tex", mime="text/plain", use_container_width=True)

        st.markdown("---")
        st.subheader(f"🗺️ Visualización Espacial Oficial ({nombre_proyeccion})")
        
        opciones_mapa = OPCIONES_MAPA
        tipo_mapa = st.selectbox("Selecciona la Capa Base del Mapa:", list(opciones_mapa.keys()))
        t_tiles = opciones_mapa[tipo_mapa]["tiles"]
        t_attr = opciones_mapa[tipo_mapa]["attr"]
        
        coordenadas_mapa, latitudes, longitudes = [], [], []

        # reset_index: iterrows() devuelve la ETIQUETA del índice, no la
        # posición. Si el DataFrame llega filtrado, coordenadas_mapa[idx] falla.
        df_mapa = df_ajuste.reset_index(drop=True)
        for _, row in df_mapa.iterrows():
            lon_wgs, lat_wgs = trans_to_wgs.transform(row['X_Estacion'], row['Y_Estacion'])
            coordenadas_mapa.append((lat_wgs, lon_wgs))
            latitudes.append(lat_wgs)
            longitudes.append(lon_wgs)
            
        centro_lat = sum(latitudes)/len(latitudes)
        centro_lon = sum(longitudes)/len(longitudes)
        
        if t_attr: mapa = folium.Map(location=[centro_lat, centro_lon], zoom_start=19, max_zoom=21, tiles=t_tiles, attr=t_attr)
        else: mapa = folium.Map(location=[centro_lat, centro_lon], zoom_start=19, max_zoom=21, tiles=t_tiles)
            
        folium.PolyLine(locations=coordenadas_mapa, color="yellow", weight=3, opacity=0.8).add_to(mapa)
        
        for idx, row in df_mapa.iterrows():
            if st.session_state.modo_app == "Cerrada" and idx == len(df_mapa)-1 and row['Estacionado'] == df_mapa.iloc[0]['Estacionado']: continue
            folium.Marker(location=coordenadas_mapa[idx], popup=f"<b>{row['Estacionado']}</b><br>Z: {row['Z_Estacion']:.3f} m", tooltip=row['Estacionado'], icon=folium.Icon(color="red", icon="screenshot", prefix="fa")).add_to(mapa)
        
        st_folium(mapa, width=1100, height=550)
