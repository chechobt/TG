# ===================================================================
# GEOPORTAL WEB - VERSIÓN 10.1 (PREVISUALIZADOR PDF LATEX INTEGRADO)
# Novedades: 
# 1. Guardado 100% manual (eliminado el autoguardado).
# 2. Información del proyecto y botón de guardado SIEMPRE en la barra lateral.
# 3. Navegación global (Menú, Planimetría, Altimetría) desde la barra lateral.
# 4. Solución del AttributeError de df_malla_vol con inicialización segura.
# 5. Inyección del visor inmersivo PDF y compilación automática LaTeX in situ.
# ===================================================================
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
import base64
import pickle
import shutil
from datetime import datetime
from streamlit_geolocation import streamlit_geolocation
import plotly.graph_objects as go
import numpy as np
import pyproj 
import glob

# Importación de los Motores
from motor_v2_5 import poligonal_3d_v2_5, decimal_a_dms
from motor_abierta import poligonal_abierta_control
from motor_altimetria import calcular_cartera_nivelacion
from motor_proyecciones import MotorCoordenadasIGAC_V2
from motor_volumenes import generar_malla_vacia, calcular_cotas_seccion, calcular_cubicaje_total
from motor_grafico_poligonal import generar_plano_profesional
from motor_exportacion import generar_kml, generar_dxf, generar_shp_zip
from motor_informes import generar_reporte_poligonal_latex, generar_reporte_volumenes_latex, compilar_latex_a_pdf

st.set_page_config(page_title="GeoPol Web | Topografía", layout="wide", page_icon="🌍")

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

df_plantilla_niv = pd.DataFrame({
    "Estaca / Punto": ["BM-INICIO", "K0+000", "PC-1", "K0+010", "BM-LLEGADA"],
    "Vista Atrás (V+)": [1.500, None, 1.620, None, None],
    "Vista Intermedia (V-)": [None, 1.200, None, 1.450, None],
    "Vista Adelante (V-)": [None, None, 1.100, None, 2.505],
    "📸 Tomar_Fotos": [False, False, False, False, False]
})

# ===================================================================
# GESTOR DE PROYECTOS Y GUARDADO MANUAL
# ===================================================================
DIR_PROYECTOS = "Proyectos_GeoPol"
os.makedirs(DIR_PROYECTOS, exist_ok=True)

def guardar_proyecto_actual(mostrar_mensaje=True):
    """Guarda el proyecto de manera 100% manual mediante el botón de la barra lateral."""
    if st.session_state.get("proyecto_actual"):
        ruta = os.path.join(DIR_PROYECTOS, f"{st.session_state.get('proyecto_actual')}.pkl")
        tipos_seguros = (int, float, str, bool, list, dict, tuple, set, pd.DataFrame, type(None))
        estado_a_guardar = {}
        
        llaves_prohibidas = ["sel_cargar", "sel_eliminar", "nav", "FormSubmitter"]
        
        for k, v in st.session_state.items():
            if any(k.startswith(prohibida) for prohibida in llaves_prohibidas) or k.startswith("cam_") or k.startswith("editor_"):
                continue
            if isinstance(v, tipos_seguros):
                estado_a_guardar[k] = v
        try:
            with open(ruta, 'wb') as f:
                pickle.dump(estado_a_guardar, f)
            if mostrar_mensaje:
                st.sidebar.success(f"✅ Proyecto '{st.session_state.get('proyecto_actual')}' guardado exitosamente.")
                st.toast("✅ Cambios guardados", icon="💾")
        except Exception as e:
            if mostrar_mensaje:
                st.sidebar.error(f"Error al guardar: {e}")

def inicializar_variables_proyecto():
    """Asigna valores iniciales limpios si el proyecto es nuevo."""
    defaults = {
        "modo_app": "Inicio", "calc_cerrada": False, "calc_abierta": False, "calc_niv": False, "calc_vol": False,
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
        "df_niv_campo": df_plantilla_niv.copy(),
        "df_malla_vol": None, # Solución al error de inicialización
        "proy_guardada": 0, "proyecto_actual": None
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def crear_nuevo_proyecto(nombre):
    """Limpia RAM pero protege variables vitales."""
    llaves_vitales = ["proyecto_actual", "modo_app"]
    for k in list(st.session_state.keys()):
        if k not in llaves_vitales:
            del st.session_state[k]
            
    st.session_state.proyecto_actual = nombre
    st.session_state.modo_app = "Menu_Principal"
    inicializar_variables_proyecto()
    guardar_proyecto_actual(mostrar_mensaje=False)

def cargar_proyecto(nombre):
    llaves_vitales = ["proyecto_actual", "modo_app"]
    for k in list(st.session_state.keys()):
        if k not in llaves_vitales:
            del st.session_state[k]
            
    st.session_state.proyecto_actual = nombre
    inicializar_variables_proyecto() 
    
    ruta = os.path.join(DIR_PROYECTOS, f"{nombre}.pkl")
    if os.path.exists(ruta):
        with open(ruta, 'rb') as f:
            estado_guardado = pickle.load(f)
        for k, v in estado_guardado.items():
            if not k.startswith("sel_"):
                st.session_state[k] = v
                
    st.session_state.modo_app = "Menu_Principal"

# ===================================================================
# INICIALIZACIÓN DE MOTORES
# ===================================================================
@st.cache_resource
def iniciar_motor_coordenadas():
    return MotorCoordenadasIGAC_V2()

motor_igac = iniciar_motor_coordenadas()

inicializar_variables_proyecto()

# Limpiamos query_params para que nunca causen recargas indeseadas
st.query_params.clear()

# ===================================================================
# FUNCIONES VISUALES (SIN ENLACES HTML PARA EVITAR HARD REFRESH)
# ===================================================================
def mostrar_icono(nombre_archivo, fallback_emoji, width=120, hover_effect=True, shadow=True, border_radius="30px"):
    ruta = os.path.join("Iconos", nombre_archivo)
    if not os.path.exists(ruta):
        ruta_alt = ruta.replace(".png", ".svg") if nombre_archivo.endswith(".png") else ruta.replace(".svg", ".png")
        if os.path.exists(ruta_alt): ruta = ruta_alt
        else:
            st.markdown(f"<div style='text-align:center; font-size:{width*0.7}px;'>{fallback_emoji}</div>", unsafe_allow_html=True)
            return

    with open(ruta, "rb") as f: b64 = base64.b64encode(f.read()).decode("utf-8")
    mime_type = "image/svg+xml" if ruta.endswith(".svg") else "image/png"
    css_class = f"icono-{nombre_archivo.replace('.','-')}"
    
    html = f"<style>.{css_class} {{ width: {width}px; border-radius: {border_radius}; display: block; margin: 0 auto; cursor: default;"
    if shadow: html += "box-shadow: 0 8px 16px rgba(0,0,0,0.2);"
    if hover_effect and shadow: html += f"}} .{css_class}:hover {{ transform: scale(1.05) translateY(-5px); box-shadow: 0 12px 20px rgba(0,0,0,0.3); "
    html += "}</style>"
    
    img_html = f'<img src="data:{mime_type};base64,{b64}" class="{css_class}">'
    st.markdown(f'{html}<div style="text-align:center;">{img_html}</div><br>', unsafe_allow_html=True)


def renderizar_banner_proyecto():
    """Inyecta el banner SÓLO dentro de los módulos de trabajo con el botón de Guardado Manual."""
    if st.session_state.get("proyecto_actual"):
        with st.container():
            st.markdown(f"""
            <div style='background-color: #E3F2FD; padding: 15px; border-radius: 10px; border-left: 8px solid #2196F3; margin-bottom: 15px;'>
                <h4 style='color: #0D47A1; margin: 0;'>📂 Workspace Activo: {st.session_state.get("proyecto_actual")}</h4>
                <p style='margin: 0; color: #1565C0; font-size: 14px;'>Recuerda oprimir 'Guardar Cambios' para asegurar tu progreso.</p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("💾 Guardar Cambios (Manual)", use_container_width=True, type="primary"):
                guardar_proyecto_actual(mostrar_mensaje=True)
            st.markdown("<br>", unsafe_allow_html=True)

# ===================================================================
# BARRA LATERAL (SIDEBAR) - NAVEGACIÓN Y GUARDADO GLOBAL
# ===================================================================
with st.sidebar:
    mostrar_icono("logo_geopol.svg", "🌐", width=220, hover_effect=False, shadow=False, border_radius="0px")
    st.markdown("---")
    
    if st.session_state.get("proyecto_actual"):
        st.info(f"📌 **Trabajando en:**\n### {st.session_state.get('proyecto_actual')}")
        
        if st.button("💾 Guardar Proyecto", use_container_width=True, type="primary"):
            guardar_proyecto_actual(mostrar_mensaje=True)
            
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
        if st.button("📐 Ir a Planimetría", use_container_width=True):
            st.session_state.modo_app = "Menu_Poligonales"
            st.rerun()
        if st.button("⛰️ Ir a Altimetría", use_container_width=True):
            st.session_state.modo_app = "Menu_Altimetria"
            st.rerun()

    st.markdown("---")
    mostrar_icono("logo_udistrital.png", "🎓", width=160, hover_effect=False, shadow=False, border_radius="0px")
    st.markdown("<p style='text-align:center; font-size:12px; color:gray;'>Kevin Cubillos & Sergio Barbosa</p>", unsafe_allow_html=True)


# ===================================================================
# HEADER UNIVERSITARIO (SÓLO VISIBLE EN INICIO Y MENÚS)
# ===================================================================
if st.session_state.modo_app in ["Inicio", "Menu_Principal"]:
    col_logo, col_info = st.columns([1, 4])
    with col_logo:
        mostrar_icono("logo_udistrital.png", "🎓", width=180, hover_effect=False, shadow=False, border_radius="0px")
    with col_info:
        st.markdown("## **UNIVERSIDAD DISTRITAL FRANCISCO JOSÉ DE CALDAS**\n#### **Facultad de Medio Ambiente y Recursos Naturales - Ingeniería Topográfica / Civil**\n**Trabajo de Grado:** Desarrollo de un Geoportal Web para la Automatización del Cálculo de Poligonales\n**Tutor:** Ing. Edgar Ladino\n**Autores:** Kevin Stiven Cubillos Ramirez y Sergio Eduardo Barbosa Torres")
    st.markdown("---")


# ===================================================================
# PANTALLA 1: LANDING PAGE Y GESTOR DE PROYECTOS 
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
        st.caption("Crea un nuevo proyecto para comenzar a calcular, o carga uno existente para retomar tu trabajo exacto donde lo dejaste.")
        
        lista_proyectos = [f.replace(".pkl", "") for f in os.listdir(DIR_PROYECTOS) if f.endswith(".pkl")]
        
        col_new, col_load, col_del = st.columns(3)
        
        with col_new:
            st.success("✨ **Iniciar Nuevo Proyecto**")
            nuevo_nombre = st.text_input("Ingresa el nombre del proyecto:")
            if st.button("➕ Crear Workspace", use_container_width=True):
                if nuevo_nombre.strip() == "":
                    st.warning("Debe ingresar un nombre válido.")
                else:
                    crear_nuevo_proyecto(nuevo_nombre.strip())
                    st.rerun()
                    
        with col_load:
            st.info("📂 **Continuar Proyecto**")
            if lista_proyectos:
                proy_cargar = st.selectbox("Seleccione un proyecto existente:", lista_proyectos, key="sel_cargar")
                if st.button("🚀 Cargar Workspace", use_container_width=True):
                    cargar_proyecto(proy_cargar)
                    st.rerun()
            else:
                st.write("No hay proyectos guardados aún.")
                
        with col_del:
            st.error("🗑️ **Eliminar Proyecto**")
            if lista_proyectos:
                proy_eliminar = st.selectbox("Seleccione un proyecto para borrar:", lista_proyectos, key="sel_eliminar")
                if st.button("⚠️ Eliminar Permanentemente", use_container_width=True):
                    os.remove(os.path.join(DIR_PROYECTOS, f"{proy_eliminar}.pkl"))
                    if os.path.exists(os.path.join("Fotos_Cartera", proy_eliminar)):
                        shutil.rmtree(os.path.join("Fotos_Cartera", proy_eliminar), ignore_errors=True)
                    st.success(f"Proyecto {proy_eliminar} eliminado.")
                    st.rerun()
            else:
                st.write("Directorio vacío.")

    with tab_sobre:
        col_txt, col_img = st.columns([2, 1])
        with col_txt:
            st.markdown("### 🌍 El Origen de GeoPol Web")
            st.write("""
            El trabajo de campo topográfico siempre ha sido riguroso, pero el procesamiento en oficina suele ser un cuello de botella tedioso, propenso a errores humanos y dependiente de software extremadamente costoso y pesado. 
            **GeoPol Web nace como la solución definitiva a este problema.** Ideado originalmente como un proyecto de grado en la **Universidad Distrital Francisco José de Caldas**, esta plataforma fue programada desde cero para democratizar el acceso a herramientas de alta ingeniería, trasladando la potencia de cálculo de un computador de escritorio directamente a la nube.
            """)
            st.markdown("### 🚀 ¿Qué nos hace únicos frente a la competencia?")
            st.markdown("""
            - 📐 **Motor CAD 2D Interactivo:** No solo calculamos. GeoPol traza tus planos con Líneas Directrices Inteligentes anti-colisión, grillas y Escalas ISO.
            - 🚜 **Modelo Civil 3D en Tiempo Real:** Visualiza cómo el terreno natural interactúa con tu rasante de diseño vial mientras digitas la cartera.
            - 📑 **Reportes Científicos Nativos:** Somos el único portal que empaqueta todo tu procesamiento y lo redacta automáticamente en código fuente **LaTeX**, listo para firma.
            - 🗺️ **Interoperabilidad GIS Total:** Exportación directa a Google Earth (.KML), AutoCAD Civil 3D (.DXF) y ArcGIS/QGIS (.SHP).
            """)
        with col_img:
            mostrar_icono("planimetria.png", "📐", width=250, shadow=False)
            mostrar_icono("volumenes.png", "🚜", width=250, shadow=False)

    with tab_equipo:
        st.markdown("<h3 style='text-align:center;'>Conoce a los creadores de esta plataforma</h3><br>", unsafe_allow_html=True)
        col_k, col_s, col_e = st.columns(3)
        with col_k:
            st.markdown("<div style='text-align:center; padding: 20px; background-color: #f8f9fa; border-radius: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);'>", unsafe_allow_html=True)
            st.markdown("### 👨‍💻 Kevin Cubillos")
            st.caption("Desarrollador Core & Co-Autor")
            st.write("Estudiante de Ingeniería en la U. Distrital, apasionado por la automatización de procesos topográficos y el desarrollo de arquitecturas en Python.")
            st.markdown("</div>", unsafe_allow_html=True)
        with col_s:
            st.markdown("<div style='text-align:center; padding: 20px; background-color: #f8f9fa; border-radius: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);'>", unsafe_allow_html=True)
            st.markdown("### 👨‍💻 Sergio Barbosa")
            st.caption("Co-Autor & Analista Espacial")
            st.write("Estudiante de Ingeniería en la U. Distrital. Especializado en el aseguramiento de la calidad geométrica y la integración de estándares GIS/CAD.")
            st.markdown("</div>", unsafe_allow_html=True)
        with col_e:
            st.markdown("<div style='text-align:center; padding: 20px; background-color: #fff4e6; border-radius: 15px; border: 2px solid #FF8C00; box-shadow: 0 4px 8px rgba(0,0,0,0.1);'>", unsafe_allow_html=True)
            st.markdown("### 🎓 Ing. Edgar Ladino")
            st.caption("Director del Proyecto de Grado")
            st.write("Tutor académico y guía fundamental en la estructuración matemática y metodológica de este sistema experto. Su visión permitió escalar el proyecto a la web.")
            st.markdown("</div>", unsafe_allow_html=True)

# ===================================================================
# PANTALLA 2: SELECCIÓN DE MÓDULOS 
# ===================================================================
elif st.session_state.modo_app == "Menu_Principal":
    st.markdown("<h4 style='text-align: center; color: gray;'>Seleccione la Disciplina Topográfica a trabajar</h4><br>", unsafe_allow_html=True)
    col_disc1, col_disc2 = st.columns(2)
    with col_disc1:
        mostrar_icono("planimetria.png", "📐", width=220)
        if st.button("⚙️ Ingresar a Planimetría", use_container_width=True):
            st.session_state.modo_app = "Menu_Poligonales"
            st.rerun()
        st.info("📐 **Módulo de Planimetría:** Procesamiento de poligonales mediante circuitos cerrados y abiertos con control geodésico.")
    with col_disc2:
        mostrar_icono("altimetria.png", "⛰️", width=220)
        if st.button("⚙️ Ingresar a Altimetría", use_container_width=True):
            st.session_state.modo_app = "Menu_Altimetria"
            st.rerun()
        st.success("⛰️ **Módulo de Altimetría:** Nivelaciones, control de cotas y cálculo de volúmenes de tierra.")


# ===================================================================
# ENRUTAMIENTO DE SUB-MÓDULOS
# ===================================================================
elif st.session_state.modo_app == "Menu_Poligonales":
    mostrar_icono("planimetria.png", "📐", width=90, hover_effect=False, shadow=False)
    st.markdown("<h3 style='text-align: center; color: #4A4A4A; margin-top: -20px;'>Módulo de Poligonales (Planimetría)</h3><br>", unsafe_allow_html=True)
    colA, colB = st.columns(2)
    with colA:
        mostrar_icono("poligonal_cerrada.png", "🔄", width=240)
        if st.button("🚀 Iniciar Circuito Cerrado", use_container_width=True):
            st.session_state.modo_app = "Cerrada"
            st.rerun()
        st.info("🔄 **Circuito Cerrado:** Inicia y termina en el mismo punto físico.")
    with colB:
        mostrar_icono("poligonal_abierta.png", "🛤️", width=240)
        if st.button("🚀 Iniciar Poligonal Abierta", use_container_width=True):
            st.session_state.modo_app = "Abierta"
            st.rerun()
        st.success("🛤️ **Poligonal Enlazada:** Inicia en un control y cierra en otro distinto.")

elif st.session_state.modo_app == "Menu_Altimetria":
    mostrar_icono("altimetria.png", "⛰️", width=90, hover_effect=False, shadow=False)
    st.markdown("<h3 style='text-align: center; color: #4A4A4A; margin-top: -20px;'>Módulo de Altimetría y Topografía Vertical</h3><br>", unsafe_allow_html=True)
    colA, colB, colC = st.columns(3)
    with colA:
        mostrar_icono("niv_cerrada.png", "🔄", width=180)
        if st.button("🚀 Nivelación Cerrada", use_container_width=True):
            st.session_state.modo_app = "Niv_Cerrada"
            st.rerun()
        st.info("🔄 **Nivelación Cerrada:** Circuito altimétrico que regresa al mismo BM de partida.")
    with colB:
        mostrar_icono("niv_abierta.png", "🛤️", width=180)
        if st.button("🚀 Nivelación Abierta", use_container_width=True):
            st.session_state.modo_app = "Niv_Abierta"
            st.rerun()
        st.success("🛤️ **Nivelación Abierta:** Línea que parte de un BM conocido y cierra sobre un BM final.")
    with colC:
        mostrar_icono("volumenes.png", "🚜", width=180)
        if st.button("🚀 Volúmenes y Diseño", use_container_width=True):
            st.session_state.modo_app = "Volumenes"
            st.rerun()
        st.warning("🚜 **Cálculo de Volúmenes:** Generación de secciones transversales y movimiento de tierras.")


# ===================================================================
# MÓDULO DE VOLÚMENES Y DISEÑO 3D
# ===================================================================
elif st.session_state.modo_app in ["Volumenes"]:
    renderizar_banner_proyecto() # LLAMADA EXPLÍCITA AL BANNER
    
    st.title("🚜 Diseño Civil y Volúmenes de Tierra en 3D")
    st.markdown("Genera mallas transversales paramétricas. Ingresa tus lecturas y el motor de **Auto-Propagación de HI** calculará el terreno, dibujando la topografía en tiempo real.")
    
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
            
            if abs_fin >= 30.0:
                idx_30 = st.session_state.df_malla_vol[st.session_state.df_malla_vol['Abscisa (K)'] == 30.0].index
                if len(idx_30) > 0:
                    st.session_state.df_malla_vol.at[idx_30[0], 'Altura Inst. (HI)'] = 501.000
            
            for i, row in st.session_state.df_malla_vol.iterrows():
                abs_k = row['Abscisa (K)']
                dist = row['Distancia Eje (m)']
                terr_base = 502.0 - (abs_k / 10.0) * 1.2
                terr_elev = terr_base - (dist * 0.15) 
                current_hi = 504.0 if abs_k < 30.0 else 501.0
                lectura = current_hi - terr_elev
                st.session_state.df_malla_vol.at[i, 'Lectura Mira (-)'] = round(lectura, 3)

            st.session_state.calc_vol = False
        except Exception as e:
            st.error(f"❌ Error al generar la malla: {e}")

    # TABLA DE EDICIÓN Y GRÁFICO 3D EN TIEMPO REAL
    if st.session_state.get("df_malla_vol") is not None:
        st.markdown("---")
        st.header("3. Ingreso de Cartera (Cálculos en Vivo)")
        st.info("💡 **Dato Inteligente:** Las filas del Eje Central están resaltadas en 🟡 amarillo. El HI se propaga automáticamente hacia abajo.")
        
        if "editor_vol_key" in st.session_state:
            cambios = st.session_state["editor_vol_key"]
            if "edited_rows" in cambios:
                for idx_str, row_changes in cambios["edited_rows"].items():
                    idx = int(idx_str)
                    for col, val in row_changes.items():
                        st.session_state.df_malla_vol.loc[idx, col] = val
                        
        df_calculado = calcular_cotas_seccion(
            st.session_state.df_malla_vol, 
            st.session_state.bom_izq_memory, 
            st.session_state.bom_der_memory,
            st.session_state.cota_rasante_ini_mem,
            st.session_state.pend_long_mem,
            st.session_state.abs_ini_mem
        )
        st.session_state.df_malla_vol = df_calculado.copy()
        st.session_state.df_vol_campo_calc = df_calculado
        
        def highlight_eje(row):
            if row.get('Distancia Eje (m)', 1) == 0.0:
                return ['background-color: rgba(255, 235, 59, 0.3)'] * len(row)
            return [''] * len(row)
            
        df_styled = st.session_state.df_malla_vol.style.apply(highlight_eje, axis=1)

        st.session_state.df_malla_vol = st.data_editor(
            df_styled, 
            key="editor_vol_key",
            num_rows="dynamic", 
            use_container_width=True,
            disabled=["Abscisa (K)", "Distancia Eje (m)", "Cota Terreno (m)", "Cota Diseño (m)"],
            column_config={
                "Abscisa (K)": st.column_config.NumberColumn(format="%.3f"),
                "Distancia Eje (m)": st.column_config.NumberColumn(format="%.3f"),
                "Altura Inst. (HI)": st.column_config.NumberColumn(format="%.3f", help="Deje vacío para usar la armada anterior"),
                "Lectura Mira (-)": st.column_config.NumberColumn(format="%.3f"),
                "Cota Terreno (m)": st.column_config.NumberColumn(format="%.3f"),
                "Cota Diseño (m)": st.column_config.NumberColumn(format="%.3f")
            }
        )

        st.markdown("### 🌐 Modelo 3D en Vivo: Superficies de Terreno y Diseño")
        
        pivot_diseno = df_calculado.pivot_table(index='Abscisa (K)', columns='Distancia Eje (m)', values='Cota Diseño (m)', dropna=False)
        X = pivot_diseno.columns.values
        Y = pivot_diseno.index.values
        Z_diseno = pivot_diseno.values
        
        pivot_terreno = df_calculado.pivot_table(index='Abscisa (K)', columns='Distancia Eje (m)', values='Cota Terreno (m)', dropna=False)
        Z_terreno = pivot_terreno.values
        
        fig3d = go.Figure()
        gray_scale = [[0, 'rgba(176, 190, 197, 0.95)'], [1, 'rgba(176, 190, 197, 0.95)']]
        fig3d.add_trace(go.Surface(z=Z_diseno, x=X, y=Y, colorscale=gray_scale, opacity=0.95, name='Diseño (Vía)', showscale=False))
        
        if not np.isnan(Z_terreno).all():
            fig3d.add_trace(go.Surface(z=Z_terreno, x=X, y=Y, colorscale='YlOrBr', opacity=0.75, name='Terreno', showscale=False))
            
        fig3d.update_layout(
            scene=dict(
                xaxis_title='Transversal (m)',
                yaxis_title='Abscisa (K)',
                zaxis_title='Cota (m)',
                aspectmode='manual',
                aspectratio=dict(x=1, y=2.5, z=0.5) 
            ),
            margin=dict(l=0, r=0, b=0, t=0),
            height=550
        )
        st.plotly_chart(fig3d, use_container_width=True)

        if st.button("🚀 4. Procesar y Calcular Cubicaje Final", type="primary", use_container_width=True):
            try:
                res_df, metricas = calcular_cubicaje_total(df_calculado)
                st.session_state.df_vol_calc = res_df
                st.session_state.met_vol = metricas
                st.session_state.calc_vol = True
            except Exception as e:
                st.error(f"❌ Completa las lecturas numéricas. Detalle: {e}")

    if st.session_state.calc_vol:
        st.success("✅ ¡Cubicaje y Áreas Medias calculadas con éxito!")
        met = st.session_state.met_vol
        
        colA, colB, colC = st.columns(3)
        colA.metric("🔴 Volumen de Corte Total", f"{met['Corte_Total']:.3f} m³")
        colB.metric("🟢 Volumen de Relleno Total", f"{met['Relleno_Total']:.3f} m³")
        colC.metric("⚖️ Balance de Volumen Neto", f"{met['Volumen_Neto']:.3f} m³", delta="Sobra material" if met['Volumen_Neto']>0 else "Falta material", delta_color="off")
        
        st.subheader("📋 Cuadro de Movimiento de Tierras (Cubicaje)")
        st.dataframe(st.session_state.df_vol_calc.style.format("{:.3f}"), use_container_width=True)
        
        st.markdown("---")
        st.subheader("📈 Perfiles Transversales con Áreas Sombreadas")
        
        abs_plot = st.selectbox("Seleccione Abscisa a Visualizar:", df_calculado['Abscisa (K)'].unique())
        
        df_plot = df_calculado[df_calculado['Abscisa (K)'] == abs_plot].copy()
        df_plot = df_plot.dropna(subset=['Cota Terreno (m)', 'Cota Diseño (m)'])
        df_plot = df_plot.sort_values(by='Distancia Eje (m)').reset_index(drop=True)
        
        if not df_plot.empty:
            x_vals = df_plot['Distancia Eje (m)'].values.tolist()
            y_dis = df_plot['Cota Diseño (m)'].values.tolist()
            y_ter = df_plot['Cota Terreno (m)'].values.tolist()
            
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
            
            x_final = np.array(x_final)
            y_dis_final = np.array(y_dis_final)
            y_ter_final = np.array(y_ter_final)

            y_min = np.minimum(y_dis_final, y_ter_final)
            y_max = np.maximum(y_dis_final, y_ter_final)
            
            fig_sec = go.Figure()
            fig_sec.add_trace(go.Scatter(x=x_final, y=y_dis_final, mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
            fig_sec.add_trace(go.Scatter(x=x_final, y=y_max, mode='none', fill='tonexty', fillcolor='rgba(220, 53, 69, 0.35)', name='Área de Corte (Excavación)'))
            fig_sec.add_trace(go.Scatter(x=x_final, y=y_min, mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
            fig_sec.add_trace(go.Scatter(x=x_final, y=y_dis_final, mode='none', fill='tonexty', fillcolor='rgba(40, 167, 69, 0.35)', name='Área de Relleno (Terraplén)'))
            fig_sec.add_trace(go.Scatter(x=x_vals, y=y_ter, mode='lines+markers', name='Terreno Natural', line=dict(color='#8D6E63', width=3), marker=dict(size=6, color='#5D4037')))
            fig_sec.add_trace(go.Scatter(x=x_vals, y=y_dis, mode='lines+markers', name='Diseño Vial', line=dict(color='#343A40', width=3), marker=dict(size=6, color='#212529')))
            
            fig_sec.update_layout(
                title=f'Sección Transversal K{abs_plot:.3f}',
                xaxis_title='Distancia Transversal (m)',
                yaxis_title='Elevación (m.s.n.m)',
                hovermode='x unified',
                height=550,
                plot_bgcolor='rgba(245, 245, 245, 0.8)'
            )
            st.plotly_chart(fig_sec, use_container_width=True)
            
            # Botón LaTeX para volúmenes
            st.markdown("---")
            with st.expander("📥 Descargar Reporte Matemático"):
                try:
                    ruta_plano_vol = "Seccion_Transversal.png"
                    fig_sec.write_image(ruta_plano_vol, width=1200, height=600, scale=2)
                except ValueError as e:
                    if "kaleido" in str(e).lower():
                        st.warning("⚠️ Instale 'kaleido' para exportar la gráfica al PDF.")
                        ruta_plano_vol = None
                    else:
                        ruta_plano_vol = None
                        
                autores = ["Kevin Stiven Cubillos Ramirez", "Sergio Eduardo Barbosa Torres"]
                tutor = "Ing. Edgar Ladino"
                tex_vol = generar_reporte_volumenes_latex(st.session_state.df_vol_calc, st.session_state.met_vol, autores, tutor, ruta_plano_vol)
                st.download_button(label="📄 Reporte LaTeX (.TEX)", data=tex_vol, file_name=f"Cubicaje_{st.session_state.get('proyecto_actual')}.tex", mime="text/plain")

# ------------------ MÓDULOS DE NIVELACIÓN NORMAL ------------------
elif st.session_state.modo_app in ["Niv_Cerrada", "Niv_Abierta"]:
    renderizar_banner_proyecto() # LLAMADA EXPLÍCITA AL BANNER
            
    if st.session_state.modo_app == "Niv_Cerrada":
        st.title("🔄 Nivelación Geométrica Cerrada")
        st.header("1. Datos de Arranque (Datum)")
        st.session_state.niv_cota_datum_c = st.number_input("Elevación Inicial (Cota del BM de Partida)", value=st.session_state.niv_cota_datum_c, format="%.3f")
        cota_datum = st.session_state.niv_cota_datum_c
        cota_llegada = None 
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
    
    st.session_state.df_niv_campo = st.data_editor(st.session_state.df_niv_campo, num_rows="dynamic", use_container_width=True)

    estaciones_con_foto_niv = st.session_state.df_niv_campo[st.session_state.df_niv_campo["📸 Tomar_Fotos"] == True]["Estaca / Punto"].unique()
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
                        dir_fotos = os.path.join("Fotos_Nivelacion", st.session_state.get("proyecto_actual") or "Sin_Proyecto", str(est))
                        os.makedirs(dir_fotos, exist_ok=True)
                        nombre = f"{est}_{secuencia_fotos[paso_actual]['paso']}_{secuencia_fotos[paso_actual]['sufijo']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        with open(os.path.join(dir_fotos, nombre), "wb") as f: f.write(foto.getbuffer())
                        st.session_state[estado_paso] += 1
                        st.rerun()
                else: st.success(f"🎉 Registro completado.")

    if st.button("🚀 Calcular Nivelación", type="primary"):
        try:
            puntos = st.session_state.df_niv_campo["Estaca / Punto"].tolist()
            v_atras = st.session_state.df_niv_campo["Vista Atrás (V+)"].tolist()
            v_intermedia = st.session_state.df_niv_campo["Vista Intermedia (V-)"].tolist()
            v_adelante = st.session_state.df_niv_campo["Vista Adelante (V-)"].tolist()
            
            res_df, metricas = calcular_cartera_nivelacion(puntos, v_atras, v_intermedia, v_adelante, cota_datum, cota_llegada)
            st.session_state.df_niv_calc = res_df
            st.session_state.met_niv = metricas
            st.session_state.calc_niv = True
        except Exception as e:
            st.error(f"❌ Error en el cálculo: {e}")

    if st.session_state.calc_niv:
        st.success("✅ ¡Cálculo y Compensación de Cotas ejecutado con éxito!")
        met = st.session_state.met_niv
        
        st.subheader("📋 Reporte Técnico de Cierre Altimétrico")
        df_rep_niv = pd.DataFrame({
            "Parámetro Evaluado": ["Sumatoria Vista Atrás (ΣV+)", "Sumatoria Vista Adelante (ΣV-)", "Cota Final Cruda (Sin Ajuste)", "Cota Teórica Esperada", "Error de Cierre Altimétrico (m)", "Error de Cierre Altimétrico (mm)"],
            "Valor Obtenido": [f"{met['sum_vista_atras']:.3f} m", f"{met['sum_vista_adelante']:.3f} m", f"{met['cota_final_cruda']:.3f} m", f"{met['cota_teorica_final']:.3f} m", f"{met['error_cierre_m']:.4f} m", f"{met['error_cierre_mm']:.1f} mm"]
        })
        st.table(df_rep_niv)
        
        st.subheader("📋 Cartera Altimétrica Compensada")
        st.dataframe(st.session_state.df_niv_calc, use_container_width=True)
        
        st.markdown("---")
        st.subheader("📈 Perfil Topográfico de Nivelación")
        df_plot = st.session_state.df_niv_calc[['Estaca / Punto', 'Cota Ajustada']].copy()
        df_plot['Cota Ajustada'] = df_plot['Cota Ajustada'].astype(float)
        
        fig_perf = go.Figure()
        fig_perf.add_trace(go.Scatter(x=df_plot['Estaca / Punto'], y=df_plot['Cota Ajustada'], mode='lines+markers', line=dict(color='#FF8C00', width=3), marker=dict(size=10)))
        fig_perf.update_layout(xaxis_title='Estaciones / Puntos Visados', yaxis_title='Elevación Ajustada (msnm)', height=450)
        st.plotly_chart(fig_perf, use_container_width=True)


# ===================================================================
# ENTORNO DE CÁLCULO DE POLIGONALES (PLANIMETRÍA)
# ===================================================================
elif st.session_state.modo_app in ["Cerrada", "Abierta"]:
    renderizar_banner_proyecto() # LLAMADA EXPLÍCITA AL BANNER
    
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
    
    # ------------------ FORMULARIO CERRADA ------------------
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

    # ------------------ FORMULARIO ABIERTA ------------------
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

    # MÓDULO FOTOGRÁFICO DE POLIGONALES
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
                        dir_fotos = os.path.join("Fotos_Cartera", st.session_state.get("proyecto_actual") or "Sin_Proyecto", str(est))
                        os.makedirs(dir_fotos, exist_ok=True)
                        nombre = f"{est}_{secuencia_fotos[paso_actual]['paso']}_{secuencia_fotos[paso_actual]['sufijo']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        with open(os.path.join(dir_fotos, nombre), "wb") as f: f.write(foto.getbuffer())
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
                st.session_state.df_ajuste_cerrada, st.session_state.metricas_cerrada, st.session_state.calc_cerrada = res_a, res_m, True
            else:
                res_c, res_a, res_m = poligonal_abierta_control(
                    estacionado, punto_obs, ang_h, ang_z, d_inc, hi, hr, 
                    (st.session_state.a_e_ini, st.session_state.a_n_ini, st.session_state.a_z_ini), 
                    (st.session_state.a_e_fin, st.session_state.a_n_fin, st.session_state.a_z_fin), 
                    (st.session_state.a_e_ref_arr, st.session_state.a_n_ref_arr, st.session_state.a_z_ref_arr) if st.session_state.a_tipo_amarre_arr == "Dos Coordenadas Conocidas" else None, 
                    azimut_arr_input, 
                    (st.session_state.a_e_ref_lleg, st.session_state.a_n_ref_lleg, st.session_state.a_z_ref_lleg) if st.session_state.a_tipo_amarre_lleg == "Dos Coordenadas Conocidas" else None, 
                    azimut_lleg_input)
                st.session_state.df_ajuste_abierta, st.session_state.metricas_abierta, st.session_state.calc_abierta = res_a, res_m, True
                
        except Exception as e:
            st.error(f"❌ Error en el cálculo: {e}")

    # Variables dinámicas para reporte según el modo
    calc_done = st.session_state.calc_cerrada if st.session_state.modo_app == "Cerrada" else st.session_state.calc_abierta
    
    if calc_done:
        st.success("✅ ¡Cálculo y Ajuste ejecutado con éxito!")
        met = st.session_state.metricas_cerrada if st.session_state.modo_app == "Cerrada" else st.session_state.metricas_abierta
        df_ajuste = st.session_state.df_ajuste_cerrada if st.session_state.modo_app == "Cerrada" else st.session_state.df_ajuste_abierta
        df_campo = st.session_state.df_cerrada_campo if st.session_state.modo_app == "Cerrada" else st.session_state.df_abierta_campo
        
        st.subheader("📋 1. Reporte Técnico de Cierre")
        df_comparativo = pd.DataFrame({
            "Parámetro de Cierre": ["Error Angular", "Error Este (X)", "Error Norte (Y)", "Error Horizontal", "Error Vertical (Z)", "Precisión Horizontal", "Precisión Vertical"],
            "Antes del Ajuste": [decimal_a_dms(met["err_ang_ant"]), f"{met['err_e_ant']:.5f} m", f"{met['err_n_ant']:.5f} m", f"{met['err_h_ant']:.5f} m", f"{met['err_v_ant']:.5f} m", f"1 en {int(met['prec_h']) if met['prec_h'] != 0 else 0}", f"1 en {int(met['prec_v']) if met['prec_v'] != 0 else 0}"],
            "Después del Ajuste": [decimal_a_dms(met["err_ang_des"]), f"{met['err_e_des']:.5f} m", f"{met['err_n_des']:.5f} m", f"{met['err_h_des']:.5f} m", f"{met['err_v_des']:.5f} m", "Exacta (Compensada)", "Exacta (Compensada)"]
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
            ruta_plano_export = "Plano_Exportado.png"
            fig_plano.savefig(ruta_plano_export, dpi=300, bbox_inches='tight')
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
            
            dir_fotos_proy = os.path.join("Fotos_Cartera", st.session_state.get("proyecto_actual") or "Sin_Proyecto")
            fotos_tomadas = glob.glob(f"{dir_fotos_proy}/*/*.jpg")
            
            autores = ["Kevin Stiven Cubillos Ramirez", "Sergio Eduardo Barbosa Torres"]
            tutor = "Ing. Edgar Ladino"
            
            data_tex = generar_reporte_poligonal_latex(
                df_campo, df_ajuste, met, st.session_state.modo_app, autores, tutor,
                path_grafico=ruta_plano_export, fotos_paths=fotos_tomadas
            )
            
            # Compilación In Situ
            pdf_bytes, pdf_path = compilar_latex_a_pdf(data_tex, output_dir="Reportes_PDF", filename=f"Reporte_{st.session_state.get('proyecto_actual') or 'Poli'}")
            
            if pdf_bytes:
                st.success("✅ Reporte PDF compilado automáticamente con el motor LaTeX del sistema.")
                import base64
                b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
            
            with col_kml: st.download_button(label="🌍 Google Earth (.KML)", data=data_kml, file_name=f"{st.session_state.get('proyecto_actual') or 'Poli'}_Plano.kml", mime="application/vnd.google-earth.kml+xml", use_container_width=True)
            with col_dxf: st.download_button(label="📐 AutoCAD (.DXF)", data=data_dxf, file_name=f"{st.session_state.get('proyecto_actual') or 'Poli'}_CAD.dxf", mime="application/dxf", use_container_width=True)
            with col_shp: st.download_button(label="🗺️ Shapefile (.ZIP)", data=data_shp, file_name=f"{st.session_state.get('proyecto_actual') or 'Poli'}_GIS.zip", mime="application/zip", use_container_width=True)
            with col_tex: 
                if pdf_bytes:
                    st.download_button(label="📄 Descargar PDF Oficial", data=pdf_bytes, file_name=f"Reporte_{st.session_state.get('proyecto_actual') or 'Poli'}.pdf", mime="application/pdf", use_container_width=True)
                else:
                    st.warning("⚠️ No se encontró la herramienta 'pdflatex' localmente. Se generó el código base .TEX.")
                    st.download_button(label="📄 Descargar Código LaTeX (.TEX)", data=data_tex, file_name=f"Reporte_{st.session_state.get('proyecto_actual') or 'Poli'}.tex", mime="text/plain", use_container_width=True)

        st.markdown("---")
        st.subheader(f"🗺️ Visualización Espacial Oficial ({nombre_proyeccion})")
        
        opciones_mapa = {
            "🛰️ ESRI Satélite (Alta Resolución)": {"tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", "attr": "Esri"},
            "🌍 Google Híbrido (Satélite + Calles)": {"tiles": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", "attr": "Google"},
            "🗺️ OpenStreetMap (Clásico)": {"tiles": "OpenStreetMap", "attr": None},
            "🌙 Modo Oscuro (CartoDB)": {"tiles": "CartoDB dark_matter", "attr": None}
        }
        
        tipo_mapa = st.selectbox("Selecciona la Capa Base del Mapa:", list(opciones_mapa.keys()))
        t_tiles = opciones_mapa[tipo_mapa]["tiles"]
        t_attr = opciones_mapa[tipo_mapa]["attr"]
        
        coordenadas_mapa, latitudes, longitudes = [], [], []
        
        for idx, row in df_ajuste.iterrows():
            lon_wgs, lat_wgs = trans_to_wgs.transform(row['X_Estacion'], row['Y_Estacion'])
            coordenadas_mapa.append((lat_wgs, lon_wgs))
            latitudes.append(lat_wgs)
            longitudes.append(lon_wgs)
            
        centro_lat = sum(latitudes)/len(latitudes)
        centro_lon = sum(longitudes)/len(longitudes)
        
        if t_attr: mapa = folium.Map(location=[centro_lat, centro_lon], zoom_start=19, max_zoom=21, tiles=t_tiles, attr=t_attr)
        else: mapa = folium.Map(location=[centro_lat, centro_lon], zoom_start=19, max_zoom=21, tiles=t_tiles)
            
        folium.PolyLine(locations=coordenadas_mapa, color="yellow", weight=3, opacity=0.8).add_to(mapa)
        
        for idx, row in df_ajuste.iterrows():
            if st.session_state.modo_app == "Cerrada" and idx == len(df_ajuste)-1 and row['Estacionado'] == df_ajuste.iloc[0]['Estacionado']: continue
            folium.Marker(location=coordenadas_mapa[idx], popup=f"<b>{row['Estacionado']}</b><br>Z: {row['Z_Estacion']:.3f} m", tooltip=row['Estacionado'], icon=folium.Icon(color="red", icon="screenshot", prefix="fa")).add_to(mapa)
        
        st_folium(mapa, width=1100, height=550)