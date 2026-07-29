# ===================================================================
# GEOPORTAL WEB - VERSIÓN FINAL (1.0 RELEASE CANDIDATE)
# Novedades: 
# 1. UI de Cartera Optimizada: Resaltado del Eje Central en Amarillo.
# 2. Motor 3D Civil: Paleta Asfalto/Tierra para máximo contraste.
# 3. Hatch 2D Automático: Sombreado Rojo (Corte) y Verde (Relleno).
# ===================================================================
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
import base64
from datetime import datetime
from streamlit_geolocation import streamlit_geolocation
import plotly.graph_objects as go
import numpy as np
import pyproj 

from motor_grafico_poligonal import generar_plano_profesional
from motor_v2_5 import poligonal_3d_v2_5, decimal_a_dms
from motor_abierta import poligonal_abierta_control
from motor_altimetria import calcular_cartera_nivelacion
from motor_proyecciones import MotorCoordenadasIGAC_V2
from motor_volumenes import generar_malla_vacia, calcular_cotas_seccion, calcular_cubicaje_total

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
if "df_malla_vol" not in st.session_state: st.session_state.df_malla_vol = None
if "calc_vol" not in st.session_state: st.session_state.calc_vol = False

if "nav" in st.query_params:
    nav_target = st.query_params["nav"]
    if nav_target in ["Inicio", "Menu_Poligonales", "Menu_Altimetria", "Cerrada", "Abierta", "Niv_Cerrada", "Niv_Abierta", "Volumenes"]:
        st.session_state.modo_app = nav_target
        st.session_state.calculado = False
        st.session_state.calc_niv = False
        st.session_state.calc_vol = False
    st.query_params.clear()

# Variables Planimétricas de Memoria
for key, val in [("c_n_ini", 102340.641), ("c_e_ini", 87677.229), ("c_z_ini", 100.0), 
                 ("c_n_ref", 102295.280), ("c_e_ref", 87588.109), ("c_z_ref", 100.0),
                 ("a_n_ini", 102562.748), ("a_e_ini", 86138.390), ("a_z_ini", 2565.979),
                 ("a_n_ref_arr", 102578.559), ("a_e_ref_arr", 86236.815), ("a_z_ref_arr", 2569.150),
                 ("a_n_fin", 102379.463), ("a_e_fin", 85957.573), ("a_z_fin", 2565.807),
                 ("a_n_ref_lleg", 102478.065), ("a_e_ref_lleg", 86007.693), ("a_z_ref_lleg", 2566.112)]:
    if key not in st.session_state: st.session_state[key] = val


def mostrar_icono(nombre_archivo, fallback_emoji, width=120, hover_effect=True, shadow=True, border_radius="30px", link_nav=None):
    ruta = os.path.join("Iconos", nombre_archivo)
    if not os.path.exists(ruta):
        ruta_alt = ruta.replace(".png", ".svg") if nombre_archivo.endswith(".png") else ruta.replace(".svg", ".png")
        if os.path.exists(ruta_alt):
            ruta = ruta_alt
            nombre_archivo = os.path.basename(ruta_alt)

    css_class = f"icono-app-{nombre_archivo.replace('.','-')}"
    shadow_css = "box-shadow: 0 8px 16px rgba(0,0,0,0.2);" if shadow else ""
    hover_css = f".{css_class}:hover {{ transform: scale(1.05) translateY(-5px); box-shadow: 0 12px 20px rgba(0,0,0,0.3); }}" if hover_effect and shadow else ""
    
    html_base = f"<style>.{css_class} {{ width: {width}px; max-width: 100%; border-radius: {border_radius}; {shadow_css} transition: transform 0.3s ease, box-shadow 0.3s ease; display: block; margin: 0 auto; cursor: {'pointer' if link_nav else 'default'}; }} {hover_css} </style>"

    if os.path.exists(ruta):
        with open(ruta, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        mime_type = "image/svg+xml" if nombre_archivo.endswith(".svg") else "image/png"
        img_html = f'<img src="data:{mime_type};base64,{b64}" class="{css_class}">'
    else:
        img_html = f"<div class='{css_class}' style='text-align: center; font-size: {width * 0.7}px; line-height: 1;'>{fallback_emoji}</div>"

    if link_nav:
        st.markdown(f'{html_base}<div style="text-align: center;"><a href="?nav={link_nav}" target="_self" style="text-decoration: none;">{img_html}</a></div><br>', unsafe_allow_html=True)
    else:
        st.markdown(f'{html_base}<div style="text-align: center;">{img_html}</div><br>', unsafe_allow_html=True)


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

col_logo, col_info = st.columns([1, 4])
with col_logo:
    mostrar_icono("logo_udistrital.png", "🎓", width=180, hover_effect=False, shadow=False, border_radius="0px")
with col_info:
    st.markdown("## **UNIVERSIDAD DISTRITAL FRANCISCO JOSÉ DE CALDAS**\n#### **Facultad de Medio Ambiente y Recursos Naturales - Ingeniería Topográfica / Civil**\n**Trabajo de Grado:** Desarrollo de un Geoportal Web para la Automatización del Cálculo de Poligonales\n**Tutor:** Ing. Edgar Ladino\n**Autores:** Kevin Stiven Cubillos Ramirez y Sergio Eduardo Barbosa Torres")
st.markdown("---")


# ===================================================================
# ENRUTAMIENTO PRINCIPAL DE MÓDULOS
# ===================================================================
if st.session_state.modo_app == "Inicio":
    st.markdown("<h3 style='text-align: center; color: #4A4A4A;'>Seleccione la Disciplina Topográfica</h3><br>", unsafe_allow_html=True)
    col_disc1, col_disc2 = st.columns(2)
    with col_disc1:
        mostrar_icono("planimetria.png", "📐", width=220, link_nav="Menu_Poligonales")
        st.info("📐 **Módulo de Planimetría:** Procesamiento de poligonales mediante circuitos cerrados y abiertos con control geodésico. *(Clic en la imagen)*")
    with col_disc2:
        mostrar_icono("altimetria.png", "⛰️", width=220, link_nav="Menu_Altimetria")
        st.success("⛰️ **Módulo de Altimetría:** Nivelaciones, control de cotas y cálculo de volúmenes de tierra. *(Clic en la imagen)*")

elif st.session_state.modo_app == "Menu_Poligonales":
    mostrar_icono("planimetria.png", "📐", width=90, hover_effect=False, shadow=False)
    st.markdown("<h3 style='text-align: center; color: #4A4A4A; margin-top: -20px;'>Módulo de Poligonales (Planimetría)</h3><br>", unsafe_allow_html=True)
    colA, colB = st.columns(2)
    with colA:
        mostrar_icono("poligonal_cerrada.png", "🔄", width=240, link_nav="Cerrada")
        st.info("🔄 **Circuito Cerrado:** Inicia y termina en el mismo punto físico.")
    with colB:
        mostrar_icono("poligonal_abierta.png", "🛤️", width=240, link_nav="Abierta")
        st.success("🛤️ **Poligonal Enlazada:** Inicia en un control y cierra en otro distinto.")

elif st.session_state.modo_app == "Menu_Altimetria":
    mostrar_icono("altimetria.png", "⛰️", width=90, hover_effect=False, shadow=False)
    st.markdown("<h3 style='text-align: center; color: #4A4A4A; margin-top: -20px;'>Módulo de Altimetría y Topografía Vertical</h3><br>", unsafe_allow_html=True)
    colA, colB, colC = st.columns(3)
    with colA:
        mostrar_icono("niv_cerrada.png", "🔄", width=180, link_nav="Niv_Cerrada")
        st.info("🔄 **Nivelación Cerrada:** Circuito altimétrico que regresa al mismo BM de partida.")
    with colB:
        mostrar_icono("niv_abierta.png", "🛤️", width=180, link_nav="Niv_Abierta")
        st.success("🛤️ **Nivelación Abierta:** Línea que parte de un BM conocido y cierra sobre un BM final.")
    with colC:
        mostrar_icono("volumenes.png", "🚜", width=180, link_nav="Volumenes")
        st.warning("🚜 **Cálculo de Volúmenes:** Generación de secciones transversales y movimiento de tierras.")


# ===================================================================
# MÓDULO DE VOLÚMENES Y DISEÑO 3D (CIVIL 3D REAL-TIME)
# ===================================================================
elif st.session_state.modo_app in ["Niv_Cerrada", "Niv_Abierta", "Volumenes"]:
    col_back, _ = st.columns([1, 3])
    with col_back:
        if st.button("⬅️ Volver a Altimetría"):
            st.session_state.modo_app = "Menu_Altimetria"
            st.rerun()
    st.markdown("---")
    
    if st.session_state.modo_app == "Volumenes":
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
                # Memoria para recalcular el diseño dinámicamente
                st.session_state.cota_rasante_ini_mem = cota_rasante_ini
                st.session_state.pend_long_mem = pend_long
                st.session_state.abs_ini_mem = abs_ini
                st.session_state.bom_izq_memory = bom_izq
                st.session_state.bom_der_memory = bom_der
                
                st.session_state.df_malla_vol = generar_malla_vacia(abs_ini, abs_fin, int_long, ancho_izq, ancho_der, int_transv, hi_ini)
                
                # INYECCIÓN INTELIGENTE DE DATOS REALISTAS (CON CAMBIO DE ARMADA)
                if abs_fin >= 30.0:
                    idx_30 = st.session_state.df_malla_vol[st.session_state.df_malla_vol['Abscisa (K)'] == 30.0].index
                    if len(idx_30) > 0:
                        st.session_state.df_malla_vol.at[idx_30[0], 'Altura Inst. (HI)'] = 501.000
                
                # Terreno natural aleatorio/suave
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
        if st.session_state.df_malla_vol is not None:
            st.markdown("---")
            st.header("3. Ingreso de Cartera (Cálculos en Vivo)")
            st.info("💡 **Dato Inteligente:** Las filas del Eje Central están resaltadas en 🟡 amarillo. El HI se propaga automáticamente hacia abajo.")
            
            # Captura de edición dinámica
            if "editor_vol_key" in st.session_state:
                cambios = st.session_state["editor_vol_key"]
                if "edited_rows" in cambios:
                    for idx_str, row_changes in cambios["edited_rows"].items():
                        idx = int(idx_str)
                        for col, val in row_changes.items():
                            st.session_state.df_malla_vol.loc[idx, col] = val
                            
            # Cálculo matemático instantáneo
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
            
            # Función para sombrear la fila del Eje
            def highlight_eje(row):
                if row.get('Distancia Eje (m)', 1) == 0.0:
                    return ['background-color: rgba(255, 235, 59, 0.3)'] * len(row)
                return [''] * len(row)
                
            df_styled = st.session_state.df_malla_vol.style.apply(highlight_eje, axis=1)

            # Editor unificado
            df_vol_editado = st.data_editor(
                df_styled, 
                key="editor_vol_key",
                num_rows="dynamic", 
                use_container_width=True,
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

            # =========================================================
            # VISUALIZADOR 3D INTERACTIVO CON COLORES PROFESIONALES
            # =========================================================
            st.markdown("### 🌐 Modelo 3D en Vivo: Superficies de Terreno y Diseño")
            
            pivot_diseno = df_calculado.pivot_table(index='Abscisa (K)', columns='Distancia Eje (m)', values='Cota Diseño (m)', dropna=False)
            X = pivot_diseno.columns.values
            Y = pivot_diseno.index.values
            Z_diseno = pivot_diseno.values
            
            pivot_terreno = df_calculado.pivot_table(index='Abscisa (K)', columns='Distancia Eje (m)', values='Cota Terreno (m)', dropna=False)
            Z_terreno = pivot_terreno.values
            
            fig3d = go.Figure()
            
            # Capa Diseño Vial (Gris Asfalto Sólido)
            gray_scale = [[0, 'rgba(176, 190, 197, 0.95)'], [1, 'rgba(176, 190, 197, 0.95)']]
            fig3d.add_trace(go.Surface(z=Z_diseno, x=X, y=Y, colorscale=gray_scale, opacity=0.95, name='Diseño (Vía)', showscale=False))
            
            # Capa Terreno Natural (Tonos Tierra translúcidos)
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

        # RENDEREADO DE RESULTADOS EXACTOS Y GRÁFICAS DE SECCIÓN (CON HATCH)
        if st.session_state.calc_vol:
            st.success("✅ ¡Cubicaje y Áreas Medias calculadas con éxito!")
            met = st.session_state.met_vol
            
            colA, colB, colC = st.columns(3)
            colA.metric("🔴 Volumen de Corte Total", f"{met['Corte_Total']:.3f} m³")
            colB.metric("🟢 Volumen de Relleno Total", f"{met['Relleno_Total']:.3f} m³")
            colC.metric("⚖️ Balance de Volumen Neto", f"{met['Volumen_Neto']:.3f} m³", delta="Sobra material" if met['Volumen_Neto']>0 else "Falta material", delta_color="off")
            
            st.subheader("📋 Cuadro de Movimiento de Tierras (Cubicaje)")
            st.dataframe(st.session_state.df_vol_calc.style.format("{:.3f}"), use_container_width=True)
            
            # =========================================================
            # VISUALIZADOR DE SECCIONES CON HATCH CORTE/RELLENO
            # (Corregido para interpolación exacta de Puntos de Paso)
            # =========================================================
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
                
                # --- ALGORITMO DE INYECCIÓN DE PUNTOS DE PASO ---
                # Busca intersecciones y las inserta para que el Hatch no se desborde
                x_final, y_dis_final, y_ter_final = [], [], []
                
                for i in range(len(x_vals) - 1):
                    x_final.append(x_vals[i])
                    y_dis_final.append(y_dis[i])
                    y_ter_final.append(y_ter[i])
                    
                    # Verificamos si hay cambio de signo (cruce entre terreno y diseño)
                    diff1 = y_ter[i] - y_dis[i]
                    diff2 = y_ter[i+1] - y_dis[i+1]
                    
                    if diff1 * diff2 < 0:
                        # Semejanza de triángulos para hallar X de intersección exacta
                        dx = x_vals[i+1] - x_vals[i]
                        frac = abs(diff1) / (abs(diff1) + abs(diff2))
                        x_inter = x_vals[i] + (dx * frac)
                        
                        # Calculamos la Y exacta interpolando en la recta de diseño
                        y_inter = y_dis[i] + (y_dis[i+1] - y_dis[i]) * frac
                        
                        # Inyectamos el nuevo punto intermedio
                        x_final.append(x_inter)
                        y_dis_final.append(y_inter)
                        y_ter_final.append(y_inter)
                        
                # Añadimos el último punto
                x_final.append(x_vals[-1])
                y_dis_final.append(y_dis[-1])
                y_ter_final.append(y_ter[-1])
                
                x_final = np.array(x_final)
                y_dis_final = np.array(y_dis_final)
                y_ter_final = np.array(y_ter_final)
                # --------------------------------------------------

                # Matemáticas para identificar techos y pisos de las áreas
                y_min = np.minimum(y_dis_final, y_ter_final)
                y_max = np.maximum(y_dis_final, y_ter_final)
                
                fig_sec = go.Figure()
                
                # 1. HATCH ROJO (ÁREA DE CORTE)
                fig_sec.add_trace(go.Scatter(x=x_final, y=y_dis_final, mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
                fig_sec.add_trace(go.Scatter(x=x_final, y=y_max, mode='none', fill='tonexty', fillcolor='rgba(220, 53, 69, 0.35)', name='Área de Corte (Excavación)'))

                # 2. HATCH VERDE (ÁREA DE RELLENO)
                fig_sec.add_trace(go.Scatter(x=x_final, y=y_min, mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
                fig_sec.add_trace(go.Scatter(x=x_final, y=y_dis_final, mode='none', fill='tonexty', fillcolor='rgba(40, 167, 69, 0.35)', name='Área de Relleno (Terraplén)'))

                # 3. LÍNEAS PRINCIPALES (Usamos los datos originales para los marcadores)
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


    # ------------------ MÓDULOS DE NIVELACIÓN NORMAL ------------------
    elif st.session_state.modo_app in ["Niv_Cerrada", "Niv_Abierta"]:
        if st.session_state.modo_app == "Niv_Cerrada":
            st.title("🔄 Nivelación Geométrica Cerrada")
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
        df_niv_editado = st.data_editor(df_niv_plantilla, num_rows="dynamic", use_container_width=True)

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
            
            st.markdown("---")
            st.subheader("📈 Perfil Topográfico de Nivelación")
            df_plot = st.session_state.df_niv_calc[['Estaca / Punto', 'Cota Ajustada']].copy()
            df_plot['Cota Ajustada'] = df_plot['Cota Ajustada'].astype(float)
            
            fig_perf = go.Figure()
            fig_perf.add_trace(go.Scatter(x=df_plot['Estaca / Punto'], y=df_plot['Cota Ajustada'], mode='lines+markers', line=dict(color='#FF8C00', width=3), marker=dict(size=10)))
            fig_perf.update_layout(xaxis_title='Estaciones / Puntos Visados', yaxis_title='Elevación Ajustada (msnm)', height=450)
            st.plotly_chart(fig_perf, use_container_width=True)

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
        lista_proyecciones_disp = list(motor_igac.transformadores.keys())
        nombre_proyeccion = st.selectbox("📍 Sistema de Coordenadas (Estándar IGAC):", lista_proyecciones_disp)

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
        
        trans_to_wgs = motor_igac.transformadores_inversos[nombre_proyeccion]
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