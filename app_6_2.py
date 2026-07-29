# ===================================================================
# GEOPORTAL WEB - VERSIÓN DEFINITIVA (ARQUITECTURA FIEL A V2)
# Novedades: 
# 1. Importación estricta y respeto absoluto a motor_proyecciones_2.py.
# 2. Corrección del error de 51cm mostrando el GPS con 9 decimales.
# 3. Transformador inverso de Folium generado al vuelo (sin tocar la clase).
# ===================================================================
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
import base64
from datetime import datetime
from streamlit_geolocation import streamlit_geolocation
import altair as alt
import pyproj  # Necesario para crear la inversa del mapa sin alterar tu motor

from motor_v2_5 import poligonal_3d_v2_5, decimal_a_dms
from motor_abierta import poligonal_abierta_control
from motor_altimetria import calcular_cartera_nivelacion

# IMPORTACIÓN EXACTA DEL ARCHIVO QUE SUBISTE (SIN MODIFICACIONES)
from motor_proyecciones import MotorCoordenadasIGAC_V2

st.set_page_config(page_title="Geoportal Topográfico", layout="wide", page_icon="🌍")

# ===================================================================
# INICIALIZACIÓN DE MOTORES Y MEMORIA
# ===================================================================
@st.cache_resource
def iniciar_motor_coordenadas():
    return MotorCoordenadasIGAC_V2()

motor_igac = iniciar_motor_coordenadas()

if "modo_app" not in st.session_state: st.session_state.modo_app = "Inicio"
if "calculado" not in st.session_state: st.session_state.calculado = False
if "calc_niv" not in st.session_state: st.session_state.calc_niv = False

if "nav" in st.query_params:
    nav_target = st.query_params["nav"]
    if nav_target in ["Inicio", "Menu_Poligonales", "Menu_Altimetria", "Cerrada", "Abierta", "Niv_Cerrada", "Niv_Abierta"]:
        st.session_state.modo_app = nav_target
        st.session_state.calculado = False
        st.session_state.calc_niv = False
    st.query_params.clear()

if "c_n_ini" not in st.session_state: st.session_state.c_n_ini = 102340.641
if "c_e_ini" not in st.session_state: st.session_state.c_e_ini = 87677.229
if "c_z_ini" not in st.session_state: st.session_state.c_z_ini = 100.000
if "c_n_ref" not in st.session_state: st.session_state.c_n_ref = 102295.280
if "c_e_ref" not in st.session_state: st.session_state.c_e_ref = 87588.109
if "c_z_ref" not in st.session_state: st.session_state.c_z_ref = 100.000

if "a_n_ini" not in st.session_state: st.session_state.a_n_ini = 102562.748
if "a_e_ini" not in st.session_state: st.session_state.a_e_ini = 86138.390
if "a_z_ini" not in st.session_state: st.session_state.a_z_ini = 2565.979
if "a_n_ref_arr" not in st.session_state: st.session_state.a_n_ref_arr = 102578.559
if "a_e_ref_arr" not in st.session_state: st.session_state.a_e_ref_arr = 86236.815
if "a_z_ref_arr" not in st.session_state: st.session_state.a_z_ref_arr = 2569.150
if "a_n_fin" not in st.session_state: st.session_state.a_n_fin = 102379.463
if "a_e_fin" not in st.session_state: st.session_state.a_e_fin = 85957.573
if "a_z_fin" not in st.session_state: st.session_state.a_z_fin = 2565.807
if "a_n_ref_lleg" not in st.session_state: st.session_state.a_n_ref_lleg = 102478.065
if "a_e_ref_lleg" not in st.session_state: st.session_state.a_e_ref_lleg = 86007.693
if "a_z_ref_lleg" not in st.session_state: st.session_state.a_z_ref_lleg = 2566.112


# ===================================================================
# FUNCIÓN MAESTRA DE RENDERIZADO VISUAL
# ===================================================================
def mostrar_icono(nombre_archivo, fallback_emoji, width=120, hover_effect=True, shadow=True, border_radius="30px", link_nav=None):
    ruta = os.path.join("Iconos", nombre_archivo)
    if not os.path.exists(ruta):
        ruta_alt = ruta.replace(".png", ".svg") if nombre_archivo.endswith(".png") else ruta.replace(".svg", ".png")
        if os.path.exists(ruta_alt):
            ruta = ruta_alt
            nombre_archivo = os.path.basename(ruta_alt)

    css_class = f"icono-app-{nombre_archivo.replace('.','-')}"
    shadow_css = "box-shadow: 0 8px 16px rgba(0,0,0,0.2);" if shadow else ""
    hover_css = ""
    if hover_effect:
        hover_shadow = "box-shadow: 0 12px 20px rgba(0,0,0,0.3);" if shadow else ""
        hover_css = f".{css_class}:hover {{ transform: scale(1.05) translateY(-5px); {hover_shadow} }}"
    
    html_base = f"<style>.{css_class} {{ width: {width}px; max-width: 100%; border-radius: {border_radius}; {shadow_css} transition: transform 0.3s ease, box-shadow 0.3s ease; display: block; margin: 0 auto; cursor: {'pointer' if link_nav else 'default'}; }} {hover_css} </style>"

    if os.path.exists(ruta):
        with open(ruta, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        mime_type = "image/svg+xml" if nombre_archivo.endswith(".svg") else "image/png"
        img_html = f'<img src="data:{mime_type};base64,{b64}" class="{css_class}">'
    else:
        img_html = f"<div class='{css_class}' style='text-align: center; font-size: {width * 0.7}px; line-height: 1;'>{fallback_emoji}</div>"

    if link_nav:
        final_html = f'{html_base}<div style="text-align: center;"><a href="?nav={link_nav}" target="_self" style="text-decoration: none;">{img_html}</a></div><br>'
    else:
        final_html = f'{html_base}<div style="text-align: center;">{img_html}</div><br>'
        
    st.markdown(final_html, unsafe_allow_html=True)


# ===================================================================
# BARRA DE NAVEGACIÓN LATERAL (SIDEBAR)
# ===================================================================
with st.sidebar:
    mostrar_icono("logo_geopol.svg", "🌐 Geoportal", width=220, hover_effect=False, shadow=False, border_radius="0px", link_nav="Inicio")
    st.markdown("---")
    st.markdown("### Navegación Rápida")
    
    if st.button("🏠 Pantalla de Inicio", use_container_width=True):
        st.session_state.modo_app = "Inicio"
        st.rerun()
    if st.button("📐 Módulo Planimetría", use_container_width=True):
        st.session_state.modo_app = "Menu_Poligonales"
        st.rerun()
    if st.button("⛰️ Módulo Altimetría", use_container_width=True):
        st.session_state.modo_app = "Menu_Altimetria"
        st.rerun()
        
    st.markdown("---")
    mostrar_icono("logo_udistrital.png", "🎓", width=160, hover_effect=False, shadow=False, border_radius="0px")
    st.markdown("<p style='text-align:center; font-size:12px; color:gray;'>Desarrollado por:<br>Kevin Cubillos & Sergio Barbosa</p>", unsafe_allow_html=True)


# ===================================================================
# ENCABEZADO INSTITUCIONAL FIJO (CUERPO PRINCIPAL)
# ===================================================================
col_logo, col_info = st.columns([1, 4])
with col_logo:
    mostrar_icono("logo_udistrital.png", "🎓", width=180, hover_effect=False, shadow=False, border_radius="0px")

with col_info:
    st.markdown("""
    ## **UNIVERSIDAD DISTRITAL FRANCISCO JOSÉ DE CALDAS**
    #### **Facultad de Medio Ambiente y Recursos Naturales - Ingeniería Topográfica / Civil**
    **Trabajo de Grado:** Desarrollo de un Geoportal Web para la Automatización del Cálculo de Poligonales  
    **Tutor:** Ing. Edgar Ladino  
    **Autores:** Kevin Stiven Cubillos Ramirez y Sergio Eduardo Barbosa Torres
    """)
st.markdown("---")


# ===================================================================
# NIVEL 1: PANTALLA PRINCIPAL (DISCIPLINAS)
# ===================================================================
if st.session_state.modo_app == "Inicio":
    st.markdown("<h3 style='text-align: center; color: #4A4A4A;'>Seleccione la Disciplina Topográfica</h3><br>", unsafe_allow_html=True)
    col_disc1, col_disc2 = st.columns(2)
    with col_disc1:
        mostrar_icono("planimetria.png", "📐", width=273, link_nav="Menu_Poligonales")
        st.info("📐 **Módulo de Planimetría:** Procesamiento de poligonales mediante circuitos cerrados y abiertos con control geodésico. *(Clic en la imagen)*")
    with col_disc2:
        mostrar_icono("altimetria.png", "⛰️", width=500, link_nav="Menu_Altimetria")
        st.success("⛰️ **Módulo de Altimetría:** Procesamiento de datos verticales (Cotas Z) mediante nivelaciones geométricas de precisión. *(Clic en la imagen)*")

# ===================================================================
# NIVEL 2A: SUBMENÚ POLIGONALES
# ===================================================================
elif st.session_state.modo_app == "Menu_Poligonales":
    mostrar_icono("planimetria.png", "📐", width=90, hover_effect=False, shadow=False)
    st.markdown("<h3 style='text-align: center; color: #4A4A4A; margin-top: -20px;'>Módulo de Poligonales (Planimetría)</h3><br>", unsafe_allow_html=True)
    colA, colB = st.columns(2)
    with colA:
        mostrar_icono("poligonal_cerrada.png", "🔄", width=240, link_nav="Cerrada")
        st.info("🔄 **Circuito Cerrado:** Inicia y termina en el mismo punto físico. *(Clic en la imagen)*")
    with colB:
        mostrar_icono("poligonal_abierta.png", "🛤️", width=240, link_nav="Abierta")
        st.success("🛤️ **Poligonal Enlazada:** Inicia en un control y cierra en otro distinto. *(Clic en la imagen)*")

# ===================================================================
# NIVEL 2B: SUBMENÚ ALTIMETRÍA
# ===================================================================
elif st.session_state.modo_app == "Menu_Altimetria":
    mostrar_icono("altimetria.png", "⛰️", width=190, hover_effect=False, shadow=False)
    st.markdown("<h3 style='text-align: center; color: #4A4A4A; margin-top: -20px;'>Módulo de Altimetría (Nivelación Geométrica)</h3><br>", unsafe_allow_html=True)
    colA, colB = st.columns(2)
    with colA:
        mostrar_icono("niv_cerrada.png", "🔄", width=252, link_nav="Niv_Cerrada")
        st.info("🔄 **Nivelación Cerrada:** Circuito altimétrico que regresa al mismo BM de partida. *(Clic en la imagen)*")
    with colB:
        mostrar_icono("niv_abierta.png", "🛤️", width=500, link_nav="Niv_Abierta")
        st.success("🛤️ **Nivelación Abierta:** Línea que parte de un BM conocido y cierra sobre un BM final. *(Clic en la imagen)*")


# ===================================================================
# NIVEL 3B: ENTORNO DE NIVELACIONES (ALTIMETRÍA)
# ===================================================================
elif st.session_state.modo_app in ["Niv_Cerrada", "Niv_Abierta"]:
    col_back, _ = st.columns([1, 3])
    with col_back:
        if st.button("⬅️ Volver a Altimetría"):
            st.session_state.modo_app = "Menu_Altimetria"
            st.rerun()
    st.markdown("---")
    
    if st.session_state.modo_app == "Niv_Cerrada":
        st.title("🔄 Nivelación Geométrica Cerrada")
        st.markdown("Calcula las Alturas Instrumentales (HI) y compensa el error de cierre altimétrico de tu circuito.")
        
        st.header("1. Datos de Arranque (Datum)")
        cota_datum = st.number_input("Elevación Inicial (Cota del BM de Partida)", value=100.000, format="%.3f")
        cota_llegada = None 
        
        df_niv_plantilla = pd.DataFrame({
            "Estaca / Punto": ["BM-1", "K0+000", "K0+010", "PC-1", "K0+020", "BM-1"],
            "Vista Atrás (V+)": [1.250, None, None, 1.420, None, None],
            "Vista Intermedia (V-)": [None, 1.100, 1.550, None, 1.320, None],
            "Vista Adelante (V-)": [None, None, None, 0.980, None, 1.685],
            "📸 Tomar_Fotos": [False, False, False, False, False, False]
        })
    else:
        st.title("🛤️ Nivelación Geométrica Abierta (Con Control)")
        st.markdown("Calcula el perfil altimétrico enlazando un BM de partida con un BM de llegada conocido.")
        
        col1, col2 = st.columns(2)
        with col1:
            st.header("1. Arranque (Datum)")
            cota_datum = st.number_input("Elevación Inicial (BM de Partida)", value=500.000, format="%.3f")
        with col2:
            st.header("2. Control Final (Llegada)")
            cota_llegada = st.number_input("Elevación Conocida (BM de Llegada)", value=499.520, format="%.3f")

        df_niv_plantilla = pd.DataFrame({
            "Estaca / Punto": ["BM-INICIO", "K0+000", "PC-1", "K0+010", "BM-LLEGADA"],
            "Vista Atrás (V+)": [1.500, None, 1.620, None, None],
            "Vista Intermedia (V-)": [None, 1.200, None, 1.450, None],
            "Vista Adelante (V-)": [None, None, 1.100, None, 2.505],
            "📸 Tomar_Fotos": [False, False, False, False, False]
        })

    st.header("3. Ingreso de Cartera de Nivelación")
    st.info("💡 **Tip de campo:** Deja vacías las celdas donde no hiciste lectura. Marca la casilla de foto para capturar el registro del punto.")
    df_niv_editado = st.data_editor(df_niv_plantilla, num_rows="dynamic", use_container_width=True)
    
    estaciones_con_foto = df_niv_editado[df_niv_editado["📸 Tomar_Fotos"] == True]["Estaca / Punto"].unique()
    if len(estaciones_con_foto) > 0:
        st.markdown("---")
        st.header("📸 4. Registro Fotográfico de Puntos Verticales")
        tabs = st.tabs([f"Estación {est}" for est in estaciones_con_foto])
        secuencia_fotos = [{"paso": 1, "sufijo": "Placa/Punto"}, {"paso": 2, "sufijo": "Norte"}, {"paso": 3, "sufijo": "Este"}, {"paso": 4, "sufijo": "Sur"}, {"paso": 5, "sufijo": "Oeste"}]
        
        for i, est in enumerate(estaciones_con_foto):
            with tabs[i]:
                estado_paso = f"paso_foto_niv_{est}"
                if estado_paso not in st.session_state: st.session_state[estado_paso] = 0
                paso_actual = st.session_state[estado_paso]
                if paso_actual < 5:
                    st.progress(paso_actual / 5.0)
                    foto = st.camera_input(f"Capturar {secuencia_fotos[paso_actual]['sufijo']}", key=f"cam_niv_{est}_{paso_actual}")
                    if foto is not None:
                        os.makedirs(os.path.join("Fotos_Nivelacion", est), exist_ok=True)
                        nombre = f"{est}_{secuencia_fotos[paso_actual]['paso']}_{secuencia_fotos[paso_actual]['sufijo']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        with open(os.path.join("Fotos_Nivelacion", est, nombre), "wb") as f: f.write(foto.getbuffer())
                        st.session_state[estado_paso] += 1
                        st.rerun()
                else: st.success(f"🎉 Registro completado en `Fotos_Nivelacion/{est}/`")

    st.markdown("---")
    if st.button("🚀 Calcular Nivelación", type="primary"):
        try:
            puntos = df_niv_editado["Estaca / Punto"].tolist()
            v_atras = df_niv_editado["Vista Atrás (V+)"].tolist()
            v_intermedia = df_niv_editado["Vista Intermedia (V-)"].tolist()
            v_adelante = df_niv_editado["Vista Adelante (V-)"].tolist()
            
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
        
        if abs(met['error_cierre_mm']) < 0.1:
            st.success(f"🎯 El circuito cerró perfectamente. La cota ajustada final es exactamente {met['cota_final_ajustada']:.3f} m.")
        
        st.markdown("---")
        st.subheader("📈 Perfil Topográfico de Nivelación")
        df_plot = st.session_state.df_niv_calc[['Estaca / Punto', 'Cota Ajustada']].copy()
        df_plot['Cota Ajustada'] = df_plot['Cota Ajustada'].astype(float)
        
        perfil_chart = alt.Chart(df_plot).mark_line(point=alt.OverlayMarkDef(color="red", size=80), color="#FF8C00", strokeWidth=3).encode(
            x=alt.X('Estaca / Punto', sort=None, title='Estaciones / Puntos Visados'), 
            y=alt.Y('Cota Ajustada', scale=alt.Scale(zero=False, padding=1), title='Elevación Ajustada (m.s.n.m)'), 
            tooltip=['Estaca / Punto', 'Cota Ajustada']
        ).properties(height=450).interactive()
        st.altair_chart(perfil_chart, use_container_width=True)


# ===================================================================
# NIVEL 3A: ENTORNO DE CÁLCULO DE POLIGONALES (PLANIMETRÍA)
# ===================================================================
elif st.session_state.modo_app in ["Cerrada", "Abierta"]:
    
    col_back, col_crs = st.columns([1, 3])
    with col_back:
        if st.button("⬅️ Volver a Poligonales"):
            st.session_state.modo_app = "Menu_Poligonales"
            st.rerun()
            
    with col_crs:
        # Extraemos las llaves DIRECTAS de tu clase V2 sin alterarla
        lista_proyecciones_disp = list(motor_igac.transformadores.keys())
        nombre_proyeccion = st.selectbox("📍 Sistema de Coordenadas (Estándar IGAC):", lista_proyecciones_disp)

    st.subheader(f"🛰️ Centro de Captura GPS -> Proyectando a: {nombre_proyeccion}")
    col_gps1, col_gps2 = st.columns([1, 2])
    with col_gps1: location = streamlit_geolocation()
    
    with col_gps2:
        if location and location['latitude'] is not None:
            lat_gps, lon_gps, alt_gps = location['latitude'], location['longitude'], location['altitude'] or 100.0
            
            # --- USO ESTRICTO DE TU MÉTODO ---
            # Pasamos lat y lon a tu función exacta. El resultado ya viene formateado.
            resultados_conversion = motor_igac.convertir_coordenada(lat_gps, lon_gps)
            
            x_plana = resultados_conversion[nombre_proyeccion]["Este"]
            y_plana = resultados_conversion[nombre_proyeccion]["Norte"]
            
            # FORMATO DE PANTALLA: 9 decimales obligatorios para evitar pérdida de precisión al copiar
            st.success(f"Satélite Vinculado: Lat {lat_gps:.9f}°, Lon {lon_gps:.9f}°")
            st.caption("*(💡 Copia estos 9 decimales exactos en MAGNA PRO para comprobar la matemática)*")
            
            if st.session_state.modo_app == "Cerrada": opciones_destino = ["Punto Ocupado (Arranque)", "Punto de Referencia (Visual)"]
            else: opciones_destino = ["Ocupado Inicial (Arranque)", "Referencia Atrás (Visual Arranque)", "Ocupado Final (Llegada)", "Referencia Adelante (Visual Llegada)"]
                
            destino = st.selectbox("¿A qué punto desea asignar esta coordenada plana?", opciones_destino)
            if st.button("📥 Aplicar Coordenada a Casilla", type="primary"):
                # Sobreescribiendo llaves visuales y variables de memoria
                if destino == "Punto Ocupado (Arranque)": 
                    st.session_state.input_c_e_ini, st.session_state.input_c_n_ini, st.session_state.input_c_z_ini = x_plana, y_plana, alt_gps
                    st.session_state.c_e_ini, st.session_state.c_n_ini, st.session_state.c_z_ini = x_plana, y_plana, alt_gps
                elif destino == "Punto de Referencia (Visual)": 
                    st.session_state.input_c_e_ref, st.session_state.input_c_n_ref, st.session_state.input_c_z_ref = x_plana, y_plana, alt_gps
                    st.session_state.c_e_ref, st.session_state.c_n_ref, st.session_state.c_z_ref = x_plana, y_plana, alt_gps
                elif destino == "Ocupado Inicial (Arranque)": 
                    st.session_state.input_a_e_ini, st.session_state.input_a_n_ini, st.session_state.input_a_z_ini = x_plana, y_plana, alt_gps
                    st.session_state.a_e_ini, st.session_state.a_n_ini, st.session_state.a_z_ini = x_plana, y_plana, alt_gps
                elif destino == "Referencia Atrás (Visual Arranque)": 
                    st.session_state.input_a_e_ref_arr, st.session_state.input_a_n_ref_arr, st.session_state.input_a_z_ref_arr = x_plana, y_plana, alt_gps
                    st.session_state.a_e_ref_arr, st.session_state.a_n_ref_arr, st.session_state.a_z_ref_arr = x_plana, y_plana, alt_gps
                elif destino == "Ocupado Final (Llegada)": 
                    st.session_state.input_a_e_fin, st.session_state.input_a_n_fin, st.session_state.input_a_z_fin = x_plana, y_plana, alt_gps
                    st.session_state.a_e_fin, st.session_state.a_n_fin, st.session_state.a_z_fin = x_plana, y_plana, alt_gps
                elif destino == "Referencia Adelante (Visual Llegada)": 
                    st.session_state.input_a_e_ref_lleg, st.session_state.input_a_n_ref_lleg, st.session_state.input_a_z_ref_lleg = x_plana, y_plana, alt_gps
                    st.session_state.a_e_ref_lleg, st.session_state.a_n_ref_lleg, st.session_state.a_z_ref_lleg = x_plana, y_plana, alt_gps
                st.rerun() 
        else: st.caption("Esperando activación del sensor GPS...")

    st.markdown("---")

    if st.session_state.modo_app == "Cerrada":
        st.header("1. Datos de Arranque (Amarre)")
        tipo_amarre = st.radio("Método de orientación inicial:", ["Dos Coordenadas Conocidas", "Una Coordenada y Azimut"])
        col1, col2, col3 = st.columns(3)
        with col1:
            st.subheader("📍 Punto Ocupado")
            n_ini = st.number_input("Norte (Y)", value=st.session_state.c_n_ini, format="%.3f", key="input_c_n_ini")
            e_ini = st.number_input("Este (X)", value=st.session_state.c_e_ini, format="%.3f", key="input_c_e_ini")
            z_ini = st.number_input("Cota (Z)", value=st.session_state.c_z_ini, format="%.3f", key="input_c_z_ini")
        with col2:
            if tipo_amarre == "Dos Coordenadas Conocidas":
                st.subheader("🎯 Punto de Referencia")
                n_ref = st.number_input("Norte Ref (Y)", value=st.session_state.c_n_ref, format="%.3f", key="input_c_n_ref")
                e_ref = st.number_input("Este Ref (X)", value=st.session_state.c_e_ref, format="%.3f", key="input_c_e_ref")
                z_ref = st.number_input("Cota Ref (Z)", value=st.session_state.c_z_ref, format="%.3f", key="input_c_z_ref")
                azimut_input = None
            else:
                st.subheader("🧭 Azimut de Partida")
                az_g = st.number_input("Grados (°)", value=243, step=1)
                az_m = st.number_input("Minutos (')", value=1, step=1)
                az_s = st.number_input("Segundos (\")", value=28.00, format="%.2f")
                azimut_input = (az_g, az_m, az_s)
                e_ref, n_ref, z_ref = None, None, None
        with col3:
            st.subheader("⚙️ Configuración")
            tipo_ang = st.selectbox("Orientación de Ángulos", ["exterior", "interior"])
            
        df_plantilla = pd.DataFrame({
            "Estacionado": ['GPS-11', 'P1', 'P2', 'P3', 'P4', 'P5', 'GPS-11'], "Pto_Obs": ['P1', 'P2', 'P3', 'P4', 'P5', 'GPS-11', 'P1'],
            "Hz_G": [275, 249, 191, 281, 246, 188, 282], "Hz_M": [43, 53, 47, 3, 35, 26, 14], "Hz_S": [41.0, 14.0, 17.0, 0.0, 32.0, 50.0, 12.0],
            "Z_G": [89, 90, 90, 89, 89, 89, 89], "Z_M": [40, 0, 13, 50, 58, 21, 40], "Z_S": [53.0, 14.0, 6.0, 53.0, 3.0, 11.0, 46.0],
            "Dist_Inc": [69.249, 50.148, 57.843, 61.563, 75.728, 31.260, 69.250],
            "hi": [1.617, 1.596, 1.575, 1.551, 1.597, 1.541, 1.615], "hr": [1.700, 1.700, 1.700, 1.700, 1.700, 1.700, 1.700],
            "📸 Tomar_Fotos": [False]*7
        })

    else:
        st.header("1. Datos de Control Geodésico")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🏁 Arranque")
            tipo_amarre_arr = st.radio("Orientación de Entrada:", ["Dos Coordenadas Conocidas", "Una Coordenada y Azimut"], key="t_arr")
            st.markdown("**Punto Ocupado Inicial (GPS-09)**")
            n_ini = st.number_input("Norte (Y) Arranque", value=st.session_state.a_n_ini, format="%.3f", key="input_a_n_ini")
            e_ini = st.number_input("Este (X) Arranque", value=st.session_state.a_e_ini, format="%.3f", key="input_a_e_ini")
            z_ini = st.number_input("Cota (Z) Arranque", value=st.session_state.a_z_ini, format="%.3f", key="input_a_z_ini")
            
            if tipo_amarre_arr == "Dos Coordenadas Conocidas":
                st.markdown("**Referencia Atrás (GPS-10)**")
                n_ref_arr = st.number_input("Norte (Y) Ref. Atrás", value=st.session_state.a_n_ref_arr, format="%.3f", key="input_a_n_ref_arr")
                e_ref_arr = st.number_input("Este (X) Ref. Atrás", value=st.session_state.a_e_ref_arr, format="%.3f", key="input_a_e_ref_arr")
                z_ref_arr = st.number_input("Cota (Z) Ref. Atrás", value=st.session_state.a_z_ref_arr, format="%.3f", key="input_a_z_ref_arr")
                azimut_arr_input = None
            else:
                st.markdown("**🧭 Azimut de Partida**")
                azA_g = st.number_input("Grados (°)", value=76, step=1, key="azA_g")
                azA_m = st.number_input("Minutos (')", value=56, step=1, key="azA_m")
                azA_s = st.number_input("Segundos (\")", value=32.00, format="%.2f", key="azA_s")
                azimut_arr_input = (azA_g, azA_m, azA_s)
                n_ref_arr, e_ref_arr, z_ref_arr = None, None, None

        with col2:
            st.subheader("🎯 Llegada")
            tipo_amarre_lleg = st.radio("Orientación de Salida:", ["Dos Coordenadas Conocidas", "Una Coordenada y Azimut"], key="t_lleg")
            st.markdown("**Punto Ocupado Final (GPS-06)**")
            n_fin = st.number_input("Norte (Y) Llegada", value=st.session_state.a_n_fin, format="%.3f", key="input_a_n_fin")
            e_fin = st.number_input("Este (X) Llegada", value=st.session_state.a_e_fin, format="%.3f", key="input_a_e_fin")
            z_fin = st.number_input("Cota (Z) Llegada", value=st.session_state.a_z_fin, format="%.3f", key="input_a_z_fin")
            
            if tipo_amarre_lleg == "Dos Coordenadas Conocidas":
                st.markdown("**Referencia Adelante (GPS-05)**")
                n_ref_lleg = st.number_input("Norte (Y) Ref. Adelante", value=st.session_state.a_n_ref_lleg, format="%.3f", key="input_a_n_ref_lleg")
                e_ref_lleg = st.number_input("Este (X) Ref. Adelante", value=st.session_state.a_e_ref_lleg, format="%.3f", key="input_a_e_ref_lleg")
                z_ref_lleg = st.number_input("Cota (Z) Ref. Adelante", value=st.session_state.a_z_ref_lleg, format="%.3f", key="input_a_z_ref_lleg")
                azimut_lleg_input = None
            else:
                st.markdown("**🧭 Azimut de Llegada**")
                azL_g = st.number_input("Grados (°)", value=250, step=1, key="azL_g")
                azL_m = st.number_input("Minutos (')", value=15, step=1, key="azL_m")
                azL_s = st.number_input("Segundos (\")", value=10.00, format="%.2f", key="azL_s")
                azimut_lleg_input = (azL_g, azL_m, azL_s)
                n_ref_lleg, e_ref_lleg, z_ref_lleg = None, None, None

        df_plantilla = pd.DataFrame({
            "Estacionado": ['GPS-09', 'C-1', 'C-2', 'C-3', 'C-4', 'C-5', 'C-6', 'C-7', 'GPS-06'],
            "Pto_Obs":     ['C-1', 'C-2', 'C-3', 'C-4', 'C-5', 'C-6', 'C-7', 'GPS-06', 'GPS-05'],
            "Hz_G": [76, 246, 135, 223, 205, 197, 162, 180, 180], "Hz_M": [56, 58, 51, 25, 20, 17, 49, 0, 0], "Hz_S": [32.0, 41.0, 53.0, 11.0, 14.0, 36.0, 57.0, 0.0, 0.0],
            "Z_G": [81, 89, 89, 89, 90, 89, 90, 90, 90], "Z_M": [4, 45, 30, 39, 14, 43, 33, 0, 0], "Z_S": [20.0, 10.0, 13.0, 21.0, 0.0, 33.0, 19.0, 0.0, 0.0],
            "Dist_Inc": [20.119, 73.699, 116.226, 96.228, 47.085, 32.462, 58.209, 50.000, 50.000],
            "hi": [1.398, 1.470, 1.528, 1.537, 1.534, 1.563, 1.550, 1.500, 1.500], "hr": [1.800, 1.800, 1.800, 1.800, 1.800, 1.800, 1.800, 1.800, 1.800],
            "📸 Tomar_Fotos": [False]*9
        })

    st.header("2. Ingreso de Cartera de Campo")
    df_editado = st.data_editor(df_plantilla, num_rows="dynamic", use_container_width=True)

    estaciones_con_foto = df_editado[df_editado["📸 Tomar_Fotos"] == True]["Estacionado"].unique()
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
                        os.makedirs(os.path.join("Fotos_Cartera", est), exist_ok=True)
                        nombre = f"{est}_{secuencia_fotos[paso_actual]['paso']}_{secuencia_fotos[paso_actual]['sufijo']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        with open(os.path.join("Fotos_Cartera", est, nombre), "wb") as f: f.write(foto.getbuffer())
                        st.session_state[estado_paso] += 1
                        st.rerun()
                else: st.success(f"🎉 Registro completado en `Fotos_Cartera/{est}/`")

    st.markdown("---")
    
    if st.button("🚀 Calcular Levantamiento", type="primary"):
        try:
            estacionado, punto_obs = df_editado["Estacionado"].tolist(), df_editado["Pto_Obs"].tolist()
            ang_h = list(zip(df_editado["Hz_G"], df_editado["Hz_M"], df_editado["Hz_S"]))
            ang_z = list(zip(df_editado["Z_G"], df_editado["Z_M"], df_editado["Z_S"]))
            d_inc, hi, hr = df_editado["Dist_Inc"].tolist(), df_editado["hi"].tolist(), df_editado["hr"].tolist()
            
            if st.session_state.modo_app == "Cerrada":
                res_c, res_a, res_m = poligonal_3d_v2_5(estacionado, punto_obs, ang_h, ang_z, d_inc, hi, hr, (e_ini, n_ini, z_ini), (e_ref, n_ref, z_ref) if tipo_amarre == "Dos Coordenadas Conocidas" else None, azimut_input if tipo_amarre != "Dos Coordenadas Conocidas" else None, tipo_ang)
            else:
                res_c, res_a, res_m = poligonal_abierta_control(estacionado, punto_obs, ang_h, ang_z, d_inc, hi, hr, (e_ini, n_ini, z_ini), (e_fin, n_fin, z_fin), (e_ref_arr, n_ref_arr, z_ref_arr) if tipo_amarre_arr == "Dos Coordenadas Conocidas" else None, azimut_arr_input, (e_ref_lleg, n_ref_lleg, z_ref_lleg) if tipo_amarre_lleg == "Dos Coordenadas Conocidas" else None, azimut_lleg_input)
                
            st.session_state.df_campo, st.session_state.df_ajuste, st.session_state.metricas, st.session_state.calculado = res_c, res_a, res_m, True
        except Exception as e:
            st.error(f"❌ Error en el cálculo: {e}")

    if st.session_state.calculado:
        st.success("✅ ¡Cálculo y Ajuste ejecutado con éxito!")
        met = st.session_state.metricas
        
        st.subheader("📋 1. Reporte Técnico de Cierre")
        df_comparativo = pd.DataFrame({
            "Parámetro de Cierre": ["Error Angular", "Error Este (X)", "Error Norte (Y)", "Error Horizontal", "Error Vertical (Z)", "Precisión Horizontal", "Precisión Vertical"],
            "Antes del Ajuste": [decimal_a_dms(met["err_ang_ant"]), f"{met['err_e_ant']:.5f} m", f"{met['err_n_ant']:.5f} m", f"{met['err_h_ant']:.5f} m", f"{met['err_v_ant']:.5f} m", f"1 en {int(met['prec_h']) if met['prec_h'] != 0 else 0}", f"1 en {int(met['prec_v']) if met['prec_v'] != 0 else 0}"],
            "Después del Ajuste": [decimal_a_dms(met["err_ang_des"]), f"{met['err_e_des']:.5f} m", f"{met['err_n_des']:.5f} m", f"{met['err_h_des']:.5f} m", f"{met['err_v_des']:.5f} m", "Exacta (Compensada)", "Exacta (Compensada)"]
        })
        st.table(df_comparativo)
        
        colA, colB = st.columns(2)
        with colA: st.dataframe(st.session_state.df_campo, use_container_width=True)
        with colB: st.dataframe(st.session_state.df_ajuste, use_container_width=True)

        st.subheader(f"🗺️ Visualización Espacial Oficial ({nombre_proyeccion} a MAGNA-SIRGAS)")
        df_aj = st.session_state.df_ajuste
        coordenadas_mapa, latitudes, longitudes = [], [], []
        
        # INVERSO CREADO AL VUELO PARA NO MODIFICAR TU CLASE
        # Usamos el target_crs del transformador directo para crear uno que devuelva a Geográficas
        crs_destino_local = motor_igac.transformadores[nombre_proyeccion].target_crs
        trans_to_wgs = pyproj.Transformer.from_crs(crs_destino_local, motor_igac.crs_geodesico, always_xy=True)
        
        for idx, row in df_aj.iterrows():
            lon_wgs, lat_wgs = trans_to_wgs.transform(row['X_Estacion'], row['Y_Estacion'])
            coordenadas_mapa.append((lat_wgs, lon_wgs))
            latitudes.append(lat_wgs)
            longitudes.append(lon_wgs)
            
        mapa = folium.Map(location=[sum(latitudes)/len(latitudes), sum(longitudes)/len(longitudes)], zoom_start=18, tiles="CartoDB dark_matter")
        folium.PolyLine(locations=coordenadas_mapa, color="yellow", weight=3, opacity=0.8).add_to(mapa)
        
        for idx, row in df_aj.iterrows():
            if st.session_state.modo_app == "Cerrada" and idx == len(df_aj)-1 and row['Estacionado'] == df_aj.iloc[0]['Estacionado']: continue
            folium.Marker(location=coordenadas_mapa[idx], popup=f"<b>{row['Estacionado']}</b><br>Z: {row['Z_Estacion']:.3f} m", tooltip=row['Estacionado'], icon=folium.Icon(color="red", icon="screenshot", prefix="fa")).add_to(mapa)
        st_folium(mapa, width=1100, height=550)