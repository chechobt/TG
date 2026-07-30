# ===================================================================
# GEOPOL WEB - REPORTES v2
# Reemplazo directo de generar_reporte_poligonal_latex(),
# generar_reporte_volumenes_latex() y generar_reporte_nivelacion_latex().
#
# Las firmas conservan los parámetros originales y añaden argumentos
# OPCIONALES: si no los pasas, el informe sale igual que antes pero con
# el formato nuevo; si los pasas, aparecen las secciones técnicas nuevas.
# ===================================================================
import pandas as pd

import geopol_analisis as ga
import geopol_render as gr


# -------------------------------------------------------------------
# Contenido narrativo (versión ampliada de obtener_contenido_informe)
# -------------------------------------------------------------------
def obtener_contenido_informe(tipo_trabajo):
    c = {}
    if "Poligonal" in tipo_trabajo:
        c["intro"] = (
            r"El presente informe documenta el establecimiento de una red de apoyo "
            r"planimétrico. La materialización de estos vértices constituye la base "
            r"fundamental para el levantamiento de detalles, garantizando que la "
            r"cartografía resultante cumpla con las precisiones requeridas para el "
            r"diseño geométrico y la estructuración de proyectos de ingeniería.")
        c["objetivos"] = (
            r"\begin{itemize}[leftmargin=1.2em,itemsep=2pt]"
            r"\item \textbf{General:} calcular y compensar la red planimétrica "
            r"obtenida en campo para determinar las coordenadas definitivas."
            r"\item \textbf{Específicos:}"
            r"\begin{itemize}[itemsep=1pt]"
            r"\item Cuantificar el error de cierre angular y lineal del circuito "
            r"y contrastarlo contra la tolerancia admisible."
            r"\item Aplicar el ajuste correspondiente según la tolerancia permitida."
            r"\item Determinar el factor de escala combinado y reducir las "
            r"distancias de terreno al plano de proyección."
            r"\item Vincular el levantamiento al sistema oficial de coordenadas."
            r"\end{itemize}\end{itemize}")
        c["marco"] = (
            r"El procesamiento se rige por las especificaciones técnicas del "
            r"\textbf{Instituto Geográfico Agustín Codazzi (IGAC)}. Toda la "
            r"información espacial se encuentra referida al sistema oficial de "
            r"Colombia, \textbf{MAGNA-SIRGAS (Origen Nacional, EPSG:9377)}, en "
            r"cumplimiento de la Resolución 471 de 2020~\cite{igac2020}. "
            r"Por tratarse de una proyección Transversa de Mercator con factor de "
            r"escala en el meridiano central $k_0 = 0{,}9992$, las distancias "
            r"medidas sobre el terreno deben reducirse al plano de proyección "
            r"mediante el factor de escala combinado antes de cualquier "
            r"comparación de cierre~\cite{wolf2015}. Los errores de cierre se "
            r"evalúan frente a tolerancias del tipo $T_a = k\,a\sqrt{n}$.")
    elif "Nivelacion" in tipo_trabajo or "Altimetria" in tipo_trabajo:
        c["intro"] = (
            r"El control vertical es un componente crítico en el desarrollo de "
            r"infraestructura. Este documento detalla el procedimiento de "
            r"nivelación geométrica ejecutado para trasladar y establecer cotas "
            r"de alta precisión en los puntos de control del proyecto.")
        c["objetivos"] = (
            r"\begin{itemize}[leftmargin=1.2em,itemsep=2pt]"
            r"\item \textbf{General:} determinar las elevaciones ajustadas a "
            r"partir de un Banco de Nivel (BM) de cota conocida."
            r"\item \textbf{Específicos:}"
            r"\begin{itemize}[itemsep=1pt]"
            r"\item Verificar el cuadre aritmético de la cartera antes de "
            r"evaluar el error de campo."
            r"\item Calcular el error de cierre y contrastarlo con la tolerancia "
            r"del orden de nivelación exigido."
            r"\item Distribuir el error proporcionalmente y reportar la "
            r"corrección aplicada punto por punto."
            r"\item Generar el perfil altimétrico y las pendientes de diseño."
            r"\end{itemize}\end{itemize}")
        c["marco"] = (
            r"La metodología altimétrica se basa en la nivelación diferencial "
            r"geométrica. El error de cierre se evalúa mediante "
            r"$e_{tol} = k\sqrt{K}$, con $K$ en kilómetros y $k$ dependiente del "
            r"orden de nivelación. En visuales largas se considera la corrección "
            r"conjunta por curvatura y refracción, $C\!\&\!R = 0{,}0675\,K^2$ "
            r"metros. El control riguroso de cotas es de estricto cumplimiento "
            r"para el diseño de sistemas por gravedad: en redes de alcantarillado "
            r"y acueducto las pendientes mínimas y máximas están estipuladas en "
            r"el \textbf{Reglamento Técnico del Sector de Agua Potable y "
            r"Saneamiento Básico (RAS)}~\cite{ras2017}.")
    elif "Volumen" in tipo_trabajo or "Cubicaje" in tipo_trabajo:
        c["intro"] = (
            r"La cuantificación del movimiento de tierras es determinante para la "
            r"viabilidad financiera y logística de una obra. Este informe expone "
            r"las memorias de cálculo volumétrico, analizando las áreas "
            r"transversales, la compensación longitudinal de masas y el balance "
            r"real de material una vez consideradas las propiedades del suelo.")
        c["objetivos"] = (
            r"\begin{itemize}[leftmargin=1.2em,itemsep=2pt]"
            r"\item \textbf{General:} calcular los volúmenes de corte y relleno "
            r"requeridos para la conformación del proyecto."
            r"\item \textbf{Específicos:}"
            r"\begin{itemize}[itemsep=1pt]"
            r"\item Cuantificar el área transversal en cada abscisa."
            r"\item Contrastar el método de áreas medias contra el prismoidal."
            r"\item Corregir el balance por esponjamiento y contracción."
            r"\item Construir el diagrama de masas y determinar distancias "
            r"medias de transporte, sobreacarreo, préstamo y botadero."
            r"\end{itemize}\end{itemize}")
        c["marco"] = (
            r"El cálculo volumétrico se realiza bajo el \textbf{Método de las "
            r"Áreas Medias}, $V = \frac{L}{2}(A_1 + A_2)$, contrastado con el "
            r"\textbf{método prismoidal}, $V = \frac{L}{6}(A_1 + 4A_m + A_2)$, "
            r"cuya diferencia se reporta explícitamente. El volumen geométrico no "
            r"corresponde al volumen real transportado: el material de corte se "
            r"mide en banco y se transporta suelto (esponjamiento), mientras que "
            r"el relleno se recibe compactado (contracción). Los criterios de "
            r"compensación, acarreo libre y disposición de sobrantes se alinean "
            r"con las Especificaciones Generales de Construcción de Carreteras "
            r"del \textbf{INVÍAS}~\cite{invias2022}; cuando el movimiento "
            r"involucra excavaciones para cimentaciones se atiende el Título H de "
            r"la \textbf{NSR-10}~\cite{nsr10}.")
    return c


# ===================================================================
# 1. POLIGONAL
# ===================================================================
def generar_reporte_poligonal_latex(df_campo, df_ajuste, metricas, tipo_poligonal,
                                    autores, tutor, path_grafico=None, fotos_paths=None,
                                    # --- nuevos, todos opcionales ---
                                    equipo=None, metadatos=None, lados=None,
                                    coords_poligono=None, vertices=None,
                                    precision_exigida=10000, factor_tolerancia=2.0,
                                    este_referencia=None, altura_elipsoidal=None,
                                    lat_referencia=4.65, ruta_logo="Iconos/logo_geopol.png"):
    tex = [gr.preambulo_v2(ruta_logo=ruta_logo)]
    tex.append(gr.portada_v2(tipo_poligonal, autores, tutor,
                             subtitulo="Red de apoyo planimétrico"))

    # ---------- Ficha de trazabilidad ----------
    meta = dict(gr.EJEMPLO_METADATOS)
    if equipo:
        meta.update(gr.ficha_equipo_a_metadatos(equipo))
    if metadatos:
        meta.update(metadatos)
    tex.append(gr.ficha_metadatos(meta))

    # ---------- Cálculos de tolerancia ----------
    n_vert = len(df_ajuste) if df_ajuste is not None else 0
    prec_eq = float((equipo or {}).get("precision_angular_seg", 5.0))
    perimetro = float(metricas.get("perimetro", 0.0)) or None

    proy = ga.tabla_proyecciones(lados) if lados else None
    if proy and not perimetro:
        perimetro = proy["resumen"]["perimetro"]

    ang = ga.evaluar_cierre_angular(metricas.get("err_ang_ant", 0),
                                    prec_eq, n_vert, factor_tolerancia)
    err_h = float(metricas.get("err_h_ant", 0.0))
    lin = (ga.evaluar_cierre_lineal(err_h, perimetro, precision_exigida)
           if perimetro else None)
    azi = ga.azimut_error_cierre(metricas.get("err_e_ant", 0.0),
                                 metricas.get("err_n_ant", 0.0))
    area = ga.area_gauss(coords_poligono) if coords_poligono else None
    fe = (ga.factor_escala_combinado(este_referencia, altura_elipsoidal, lat_referencia)
          if este_referencia and altura_elipsoidal is not None else None)

    # ---------- Panel de indicadores ----------
    kpis = []
    prec_h = float(metricas.get("prec_h", 0) or 0)
    kpis.append({"titulo": "Precisión planimétrica",
                 "valor": f"1:{int(prec_h)}" if prec_h else "---",
                 "sub": f"exigida 1:{precision_exigida}",
                 "estado": (lin or {}).get("estado", "alerta")})
    kpis.append({"titulo": "Error angular", "valor": ang["error_dms"],
                 "sub": f"tolerancia {ang['tolerancia_dms']}", "estado": ang["estado"]})
    kpis.append({"titulo": "Error lineal de cierre",
                 "valor": gr.numero_plano(err_h, 4).replace(".", ",") + " m",
                 "sub": (f"azimut {azi['azimut_dms']}" if azi["azimut_grados"] is not None
                         else ""), "estado": "neutro"})
    if area:
        kpis.append({"titulo": "Área del polígono",
                     "valor": f"{area['area_ha']:.4f}".replace(".", ",") + " ha",
                     "sub": f"{area['area_fanegadas']:.3f}".replace(".", ",")
                            + " fanegadas", "estado": "neutro"})
        kpis.append({"titulo": "Perímetro",
                     "valor": f"{area['perimetro_m']:.3f}".replace(".", ",") + " m",
                     "sub": f"{area['n_vertices']} vértices", "estado": "neutro"})
    if fe:
        kpis.append({"titulo": "Factor combinado",
                     "valor": f"{fe['factor_combinado']:.7f}".replace(".", ","),
                     "sub": f"{fe['ppm']:.1f} ppm".replace(".", ","), "estado": "neutro"})
    tex.append(gr.panel_kpi(kpis, columnas=3))
    tex.append(r"\newpage")

    textos = obtener_contenido_informe("Poligonal")
    tex.append(r"\section{Introducción}")
    tex.append(textos["intro"])
    tex.append(r"\subsection{Objetivos del Procesamiento}")
    tex.append(textos["objetivos"])
    tex.append(r"\section{Marco Teórico y Referencia Normativa}")
    tex.append(textos["marco"])
    tex.append(r"\subsection{Metodología de Procesamiento Automático}")
    tex.append(r"El conjunto de datos brutos fue sometido a rutinas de depuración y "
               r"compensación matricial a través del motor algorítmico de "
               r"\textbf{GeoPol}.")

    # ---------- Campo ----------
    tex.append(r"\section{Trabajo de Campo: Registro de Observaciones}")
    tex.append(gr.tabla_larga(df_campo, "Cartera de observaciones brutas", "campo"))

    if fotos_paths:
        tex.append(_mosaico_fotos(fotos_paths,
                                  "Mosaico de registro fotográfico de estaciones",
                                  "Registro Fotográfico Panorámico"))

    # ---------- Errores y tolerancias ----------
    tex.append(r"\section{Cálculo, Análisis de Errores y Compensación}")

    filas_cumpl = [{"criterio": "Cierre angular", "obtenido": ang["error_dms"],
                    "tolerancia": ang["tolerancia_dms"], "estado": ang["estado"],
                    "norma": f"Ta = {factor_tolerancia:g}·{prec_eq:g}\"·√{n_vert}"}]
    if lin:
        filas_cumpl.append({"criterio": "Cierre lineal",
                            "obtenido": f"{lin['error_m']:.4f} m".replace(".", ","),
                            "tolerancia": f"{lin['tolerancia_m']:.4f} m".replace(".", ","),
                            "estado": lin["estado"],
                            "norma": f"1:{precision_exigida}"})
    tex.append(gr.tabla_cumplimiento(filas_cumpl))

    tex.append(_tabla_metricas_cierre(metricas))

    if lin:
        cuerpo = (f"Se obtuvo una precisión relativa de 1:{int(lin['precision_obtenida'])} "
                  f"frente a la exigencia de 1:{precision_exigida}. "
                  f"El vector de error de cierre tiene magnitud "
                  f"\\SI{{{azi['magnitud']:.4f}}}{{\\metre}}")
        if azi["azimut_grados"] is not None:
            cuerpo += f" y azimut {gr.escapar_latex(azi['azimut_dms'])}"
        cuerpo += "."
        if lados:
            susp = ga.lado_sospechoso(metricas.get("err_e_ant", 0),
                                      metricas.get("err_n_ant", 0),
                                      {L["lado"]: L["azimut"] for L in lados})
            if susp:
                cuerpo += (" Los lados con azimut concordante con esa dirección "
                           f"({gr.escapar_latex(', '.join(s['lado'] for s in susp[:3]))}) "
                           "deben verificarse por posible error de distancia.")
        tex.append(gr.caja_dictamen("Dictamen sobre la precisión planimétrica",
                                    cuerpo, lin["estado"]))

    # ---------- Memoria de proyecciones ----------
    if proy:
        tex.append(r"\subsection{Memoria de proyecciones y compensación}")
        df_p = pd.DataFrame([{
            "Lado": f["lado"], "Distancia": f["distancia"], "Azimut": f["azimut"],
            "Delta Este": f["delta_e"], "Delta Norte": f["delta_n"],
            "Correccion Este": f["corr_e"], "Correccion Norte": f["corr_n"],
            "Delta Este ajustado": f["delta_e_aj"],
            "Delta Norte ajustado": f["delta_n_aj"]} for f in proy["filas"]])
        tex.append(gr.tabla_larga(
            df_p, f"Proyecciones y compensación — {proy['metodo']}", "proyecciones",
            notas="Las correcciones se distribuyen proporcionalmente a la longitud "
                  "de cada lado. La suma de proyecciones ajustadas debe ser nula."))

        est = ga.estadisticos_red([L["distancia"] for L in lados])
        tex.append(r"\begin{itemize}[leftmargin=1.2em,itemsep=1pt]")
        tex.append(r"\item Lados: " + str(est["n_lados"])
                   + r"; longitud total \SI{" + f"{est['longitud_total']:.3f}"
                   + r"}{\metre}; lado medio \SI{" + f"{est['lado_medio']:.3f}"
                   + r"}{\metre}.")
        tex.append(r"\item Relación lado máximo/mínimo: "
                   + f"{est['relacion_max_min']:.2f}".replace(".", ",")
                   + r" (valores altos indican geometría desfavorable).")
        tex.append(r"\end{itemize}")

    # ---------- Factor de escala ----------
    if fe:
        tex.append(r"\subsection{Reducción al plano de proyección}")
        tex.append(r"Factor de escala de cuadrícula "
                   + f"{fe['factor_cuadricula']:.8f}".replace(".", ",")
                   + r", factor de elevación "
                   + f"{fe['factor_elevacion']:.8f}".replace(".", ",")
                   + r", \textbf{factor combinado} "
                   + f"{fe['factor_combinado']:.8f}".replace(".", ",")
                   + f" ({fe['ppm']:.1f} ppm). ".replace(".", ",")
                   + r"Este factor multiplica la distancia de terreno para "
                     r"obtener la distancia de cuadrícula.")
        if lados:
            pares = ga.aplicar_factor_escala([L["distancia"] for L in lados],
                                             fe["factor_combinado"])
            df_fe = pd.DataFrame([{"Lado": lados[i]["lado"],
                                   "Distancia terreno": p[0],
                                   "Distancia cuadricula": p[1],
                                   "Diferencia": p[2]} for i, p in enumerate(pares)])
            tex.append(gr.tabla_larga(df_fe,
                                      "Reducción de distancias de terreno a cuadrícula",
                                      "factor_escala"))

    # ---------- Área ----------
    if area:
        tex.append(r"\subsection{Área y perímetro}")
        tex.append(r"Área calculada por el método de Gauss: \SI{"
                   + f"{area['area_m2']:.3f}" + r"}{\square\metre} "
                   + r"($\equiv$ \num{" + f"{area['area_ha']:.4f}" + r"} ha "
                   + r"$\equiv$ \num{" + f"{area['area_fanegadas']:.4f}"
                   + r"} fanegadas). Perímetro \SI{"
                   + f"{area['perimetro_m']:.3f}" + r"}{\metre}. "
                   + f"Sentido de digitalización: {area['sentido']}.")

    tex.append(r"\subsection{Cartera Final de Coordenadas Ajustadas}")
    tex.append(gr.tabla_larga(df_ajuste, "Coordenadas compensadas de la red", "ajuste"))

    if vertices:
        tex.append(gr.monografia_vertices(vertices))

    if path_grafico:
        tex.append(_figura(path_grafico, f"Plano As-Built de la {tipo_poligonal}",
                           "Esquema Geométrico de la Red Planimétrica"))

    # ---------- Conclusiones ----------
    tex.append(r"\section{Conclusiones y Dictamen Técnico}")
    tex.append(r"\begin{itemize}[leftmargin=1.2em,itemsep=3pt]")
    tex.append(r"\item " + evaluar_precision(prec_h))
    tex.append(r"\item " + ("El cierre angular se encuentra dentro de la tolerancia "
                            if ang["cumple"] else
                            "El cierre angular EXCEDE la tolerancia admisible ")
               + r"($" + f"{ang['razon_uso']*100:.0f}" + r"\%$ de la tolerancia).")
    if fe:
        tex.append(r"\item Las distancias fueron reducidas al plano de proyección "
                   r"EPSG:9377 con un factor combinado de "
                   + f"{fe['factor_combinado']:.8f}".replace(".", ",") + r".")
    tex.append(r"\item El procesamiento fue automatizado mediante \textbf{GeoPol Web}, "
               r"garantizando la trazabilidad requerida en interventoría.")
    tex.append(r"\end{itemize}")

    tex.append(gr.bloque_firmas())
    tex.append(gr.cierre_bibliografia())
    tex.append(r"\end{document}")
    return "\n".join(tex)


# ===================================================================
# 2. NIVELACIÓN
# ===================================================================
def generar_reporte_nivelacion_latex(df_calc, metricas, tipo_nivelacion, autores, tutor,
                                     path_grafico=None, fotos_paths=None,
                                     # --- nuevos, opcionales ---
                                     equipo=None, metadatos=None,
                                     longitud_km=None, orden="Tercer orden",
                                     dist_atras=None, dist_adelante=None,
                                     puntos_correccion=None, puntos_pendiente=None,
                                     bm_partida=None,
                                     ruta_logo="Iconos/logo_geopol.png"):
    tex = [gr.preambulo_v2(ruta_logo=ruta_logo)]
    tex.append(gr.portada_v2(f"Informe Técnico de Altimetría", autores, tutor,
                             subtitulo=tipo_nivelacion))

    meta = dict(gr.EJEMPLO_METADATOS)
    if equipo:
        meta.update(gr.ficha_equipo_a_metadatos(equipo))
    if bm_partida:
        meta["Punto de amarre"] = (f"{bm_partida.get('codigo','')} — cota "
                                   f"{bm_partida.get('cota','')} m")
        meta["Fuente del amarre"] = bm_partida.get("entidad", "")
    if metadatos:
        meta.update(metadatos)
    tex.append(gr.ficha_metadatos(meta))

    # ---------- Análisis ----------
    err_mm = float(metricas.get("error_cierre_mm", 0.0))
    bal = (ga.balance_visuales(dist_atras, dist_adelante)
           if dist_atras and dist_adelante else None)
    K = longitud_km if longitud_km is not None else (bal["longitud_total_km"] if bal else 0.0)
    niv = ga.evaluar_cierre_altimetrico(err_mm, K, orden)
    chq = ga.chequeo_aritmetico_cartera(
        metricas.get("sum_vista_atras", 0), metricas.get("sum_vista_adelante", 0),
        metricas.get("cota_inicial", metricas.get("cota_teorica_final", 0)),
        metricas.get("cota_final_cruda", 0))

    kpis = [
        {"titulo": "Error de cierre",
         "valor": f"{err_mm:.1f} mm".replace(".", ","),
         "sub": f"tolerancia {niv['tolerancia_mm']:.1f} mm".replace(".", ","),
         "estado": niv["estado"]},
        {"titulo": "Orden de nivelación", "valor": f"k = {niv['k']:g}",
         "sub": niv["orden"], "estado": "neutro"},
        {"titulo": "Longitud nivelada",
         "valor": f"{niv['K_km']:.3f} km".replace(".", ","),
         "sub": "K en la fórmula de tolerancia", "estado": "neutro"},
        {"titulo": "Cuadre aritmético",
         "valor": ("correcto" if chq["cuadra"] else "incorrecto"),
         "sub": f"discrepancia {chq['discrepancia']*1000:.2f} mm".replace(".", ","),
         "estado": chq["estado"]},
    ]
    if bal:
        kpis.append({"titulo": "Balance de visuales",
                     "valor": f"{bal['desbalance_pct']:.2f} %".replace(".", ","),
                     "sub": f"desbalance {bal['desbalance_m']:.1f} m".replace(".", ","),
                     "estado": bal["estado"]})
    tex.append(gr.panel_kpi(kpis, columnas=3))
    tex.append(r"\newpage")

    textos = obtener_contenido_informe("Nivelacion")
    tex.append(r"\section{Introducción}")
    tex.append(textos["intro"])
    tex.append(r"\subsection{Objetivos}")
    tex.append(textos["objetivos"])
    tex.append(r"\section{Marco Teórico y Normativo}")
    tex.append(textos["marco"])
    if "Cerrada" in tipo_nivelacion:
        tex.append(r"Al tratarse de una nivelación cerrada, el circuito inicia y "
                   r"termina en el mismo punto de control, por lo que el error de "
                   r"cierre corresponde a la discrepancia respecto a la cota de partida.")
    else:
        tex.append(r"Al tratarse de una nivelación abierta con control, la línea "
                   r"inicia en un Banco de Nivel conocido y cierra sobre un Banco "
                   r"de Nivel distinto de cota igualmente conocida.")

    tex.append(r"\section{Cartera Altimétrica Compensada}")
    tex.append(gr.tabla_larga(df_calc, "Cartera de nivelación procesada", "nivelacion"))

    if fotos_paths:
        tex.append(_mosaico_fotos(fotos_paths,
                                  "Mosaico de registro fotográfico de placas y BMs",
                                  "Registro Fotográfico de Puntos Verticales"))

    # ---------- Verificaciones ----------
    tex.append(r"\section{Análisis de Errores y Compensación Altimétrica}")
    filas = [
        {"criterio": "Cuadre aritmético de cartera",
         "obtenido": f"{chq['discrepancia']*1000:.2f} mm".replace(".", ","),
         "tolerancia": "0,10 mm", "estado": chq["estado"],
         "norma": "ΣV+ − ΣV− = ΔCota"},
        {"criterio": "Error de cierre altimétrico",
         "obtenido": f"{err_mm:.1f} mm".replace(".", ","),
         "tolerancia": f"{niv['tolerancia_mm']:.1f} mm".replace(".", ","),
         "estado": niv["estado"], "norma": f"e = k√K — {orden}"},
    ]
    if bal:
        filas.append({"criterio": "Balance de visuales atrás/adelante",
                      "obtenido": f"{bal['desbalance_pct']:.2f} %".replace(".", ","),
                      "tolerancia": "2,00 %", "estado": bal["estado"],
                      "norma": "Control de colimación"})
    tex.append(gr.tabla_cumplimiento(filas))

    tex.append(gr.caja_dictamen(
        "Verificación aritmética de la cartera",
        gr.escapar_latex(chq["mensaje"]) + r" $\Sigma V^{+} = \SI{"
        + f"{chq['sigma_mas']:.3f}" + r"}{\metre}$, $\Sigma V^{-} = \SI{"
        + f"{chq['sigma_menos']:.3f}" + r"}{\metre}$.", chq["estado"]))

    tex.append(gr.caja_dictamen(
        f"Dictamen sobre el cierre altimétrico ({gr.escapar_latex(orden)})",
        f"El error de cierre de \\SI{{{abs(err_mm):.1f}}}{{\\milli\\metre}} representa el "
        f"{niv['razon_uso']*100:.0f}\\% de la tolerancia admisible de "
        f"\\SI{{{niv['tolerancia_mm']:.1f}}}{{\\milli\\metre}} para una longitud "
        f"nivelada de \\SI{{{niv['K_km']:.3f}}}{{\\kilo\\metre}}.",
        niv["estado"]))

    if bal:
        tex.append(r"\subsection{Control de colimación y visuales}")
        tex.append(r"\begin{itemize}[leftmargin=1.2em,itemsep=1pt]")
        tex.append(r"\item Suma de distancias vista atrás: \SI{"
                   + f"{bal['suma_atras']:.1f}" + r"}{\metre}; vista adelante: \SI{"
                   + f"{bal['suma_adelante']:.1f}" + r"}{\metre}.")
        tex.append(r"\item Desbalance: \SI{" + f"{bal['desbalance_m']:.1f}"
                   + r"}{\metre} (" + f"{bal['desbalance_pct']:.2f}".replace(".", ",")
                   + r"\%). Un desbalance reducido minimiza la propagación del "
                     r"error de colimación.")
        tex.append(r"\item Visual más larga: \SI{"
                   + f"{max(bal['visual_max_atras'], bal['visual_max_adelante']):.1f}"
                   + r"}{\metre}; corrección por curvatura y refracción asociada: \SI{"
                   + f"{ga.correccion_curvatura_refraccion(max(bal['visual_max_atras'], bal['visual_max_adelante'])):.5f}"
                   + r"}{\metre}.")
        tex.append(r"\end{itemize}")

    if puntos_correccion:
        det = ga.distribuir_error_altimetrico(puntos_correccion,
                                              float(metricas.get("error_cierre_m", 0.0)))
        tex.append(r"\subsection{Distribución del error punto por punto}")
        df_c = pd.DataFrame([{"Punto": d["punto"],
                              "Distancia acumulada": d["distancia_acum"],
                              "Cota cruda": d["cota_cruda"],
                              "Correccion mm": d["correccion_mm"],
                              "Cota ajustada": d["cota_ajustada"]} for d in det])
        tex.append(gr.tabla_larga(df_c, "Corrección altimétrica aplicada por punto",
                                  "correcciones",
                                  notas="La corrección se distribuye proporcionalmente "
                                        "a la distancia acumulada."))

    if puntos_pendiente:
        pend = ga.pendientes_entre_puntos(puntos_pendiente)
        tex.append(r"\subsection{Pendientes resultantes}")
        df_pe = pd.DataFrame([{"Tramo": p["tramo"],
                               "Distancia horizontal": p["dist_horizontal"],
                               "Desnivel": p["desnivel"],
                               "Pendiente %": p["pendiente_pct"],
                               "Sentido": p["sentido"]} for p in pend])
        tex.append(gr.tabla_larga(df_pe, "Pendientes entre puntos consecutivos",
                                  "pendientes",
                                  notas="Verificar contra las pendientes mínima y "
                                        "máxima admisibles del RAS para diseño por "
                                        "gravedad."))

    if path_grafico:
        tex.append(_figura(path_grafico,
                           "Perfil altimétrico de la línea de nivelación compensada "
                           "(exageración vertical aplicada)",
                           "Perfil Topográfico de Nivelación"))

    tex.append(r"\section{Conclusiones}")
    tex.append(r"\begin{itemize}[leftmargin=1.2em,itemsep=3pt]")
    tex.append(r"\item " + gr.escapar_latex(chq["mensaje"]))
    tex.append(r"\item " + ("El cierre altimétrico cumple la tolerancia del "
                            if niv["cumple"] else
                            "El cierre altimétrico NO cumple la tolerancia del ")
               + gr.escapar_latex(orden) + r".")
    tex.append(r"\item El ajuste se distribuyó proporcionalmente en los puntos de "
               r"cambio, obteniendo cotas definitivas aptas para obra civil.")
    tex.append(r"\end{itemize}")

    tex.append(gr.bloque_firmas())
    tex.append(gr.cierre_bibliografia())
    tex.append(r"\end{document}")
    return "\n".join(tex)


# ===================================================================
# 3. VOLÚMENES
# ===================================================================
def generar_reporte_volumenes_latex(df_cubicaje, metricas, autores, tutor,
                                    path_grafico=None, path_masas=None,
                                    paths_secciones=None,
                                    # --- nuevos, opcionales ---
                                    equipo=None, metadatos=None,
                                    material="Material común", secciones=None,
                                    abscisas=None, volumenes_netos=None,
                                    acarreo_libre=100.0, estacion_m=20.0,
                                    capacidad_volqueta=7.0,
                                    ruta_logo="Iconos/logo_geopol.png"):
    tex = [gr.preambulo_v2(ruta_logo=ruta_logo)]
    tex.append(gr.portada_v2("Memorias de Cálculo y Diseño Vial", autores, tutor,
                             subtitulo="Cubicaje de volúmenes y movimiento de tierras"))

    meta = dict(gr.EJEMPLO_METADATOS)
    meta["Material predominante"] = material
    if equipo:
        meta.update(gr.ficha_equipo_a_metadatos(equipo))
    if metadatos:
        meta.update(metadatos)
    tex.append(gr.ficha_metadatos(meta))

    corte = float(metricas.get("Corte_Total", 0.0))
    relleno = float(metricas.get("Relleno_Total", 0.0))
    bal = ga.balance_volumetrico_corregido(corte, relleno, material)
    viaj = ga.viajes_volqueta(bal["corte_suelto"], capacidad_volqueta)
    cmp_ = ga.comparar_metodos_volumen(secciones) if secciones else None
    cm = (ga.curva_masa(abscisas, volumenes_netos)
          if abscisas and volumenes_netos else None)
    acar = (ga.analisis_acarreo(cm["abscisas"], cm["acumulado"], acarreo_libre, estacion_m)
            if cm else None)

    tex.append(gr.panel_kpi([
        {"titulo": "Corte (banco)",
         "valor": f"{corte:,.0f}".replace(",", ".") + " m³", "estado": "neutro"},
        {"titulo": "Relleno (compactado)",
         "valor": f"{relleno:,.0f}".replace(",", ".") + " m³", "estado": "neutro"},
        {"titulo": "Balance real",
         "valor": f"{bal['balance_real']:,.0f}".replace(",", ".") + " m³",
         "sub": ("excedente a botadero" if bal["balance_real"] > 0
                 else "requiere préstamo"),
         "estado": "alerta" if abs(bal["balance_real"]) > 0.05 * max(corte, 1) else "ok"},
        {"titulo": "Corte suelto a transportar",
         "valor": f"{bal['corte_suelto']:,.0f}".replace(",", ".") + " m³",
         "sub": f"esponjamiento {bal['esponjamiento']*100:.0f} %", "estado": "neutro"},
        {"titulo": "Viajes de volqueta", "valor": f"{viaj['viajes']:,}".replace(",", "."),
         "sub": f"capacidad {capacidad_volqueta:g} m³", "estado": "neutro"},
        {"titulo": "Balance geométrico",
         "valor": f"{bal['balance_geometrico']:,.0f}".replace(",", ".") + " m³",
         "sub": "sin corregir (referencia)", "estado": "neutro"},
    ], columnas=3))
    tex.append(r"\newpage")

    textos = obtener_contenido_informe("Volumen")
    tex.append(r"\section{Introducción}")
    tex.append(textos["intro"])
    tex.append(r"\subsection{Objetivos}")
    tex.append(textos["objetivos"])
    tex.append(r"\section{Marco Teórico y Normativo}")
    tex.append(textos["marco"])

    # ---------- Balance corregido ----------
    tex.append(r"\section{Balance Volumétrico Real}")
    tex.append(gr.caja_dictamen(
        f"Corrección por esponjamiento y contracción — {gr.escapar_latex(material)}",
        f"El balance geométrico (\\SI{{{bal['balance_geometrico']:.2f}}}{{\\cubic\\metre}}) "
        f"no representa el material realmente movido. Con un esponjamiento de "
        f"{bal['esponjamiento']*100:.0f}\\%, los "
        f"\\SI{{{bal['corte_banco']:.2f}}}{{\\cubic\\metre}} de corte en banco equivalen a "
        f"\\SI{{{bal['corte_suelto']:.2f}}}{{\\cubic\\metre}} sueltos para transporte. "
        f"Con una contracción de {bal['contraccion']*100:.0f}\\%, conformar "
        f"\\SI{{{bal['relleno_compactado']:.2f}}}{{\\cubic\\metre}} compactados exige "
        f"\\SI{{{bal['relleno_en_banco']:.2f}}}{{\\cubic\\metre}} en banco. "
        f"El \\textbf{{balance real}} es de "
        f"\\SI{{{bal['balance_real']:.2f}}}{{\\cubic\\metre}}: "
        + ("excedente a disponer en botadero." if bal["balance_real"] > 0
           else "déficit que exige material de préstamo."),
        estado="alerta"))

    tex.append(r"\begin{itemize}[leftmargin=1.2em,itemsep=2pt]")
    tex.append(r"\item Factor de compactación aplicado: "
               + f"{bal['factor_compactacion']:.4f}".replace(".", ",") + r".")
    tex.append(r"\item Volumen a botadero: \SI{" + f"{bal['volumen_botadero']:.2f}"
               + r"}{\cubic\metre}; material de préstamo: \SI{"
               + f"{bal['volumen_prestamo']:.2f}" + r"}{\cubic\metre}.")
    tex.append(r"\item Transporte estimado: " + f"{viaj['viajes']:,}".replace(",", ".")
               + r" viajes de volqueta de \SI{" + f"{viaj['capacidad_nominal']:.1f}"
               + r"}{\cubic\metre} (factor de llenado "
               + f"{viaj['factor_llenado']:.2f}".replace(".", ",") + r").")
    tex.append(r"\item Diferencia frente al balance geométrico: \SI{"
               + f"{bal['diferencia_vs_geometrico']:.2f}" + r"}{\cubic\metre}.")
    tex.append(r"\end{itemize}")

    tex.append(r"\section{Cuadro de Movimiento de Tierras}")
    tex.append(gr.tabla_larga(df_cubicaje, "Cuadro generalizado de cubicaje", "cubicaje"))

    # ---------- Métodos ----------
    if cmp_:
        tex.append(r"\section{Contraste de Métodos de Cálculo}")
        tex.append(r"Diferencia entre áreas medias y método prismoidal: \SI{"
                   + f"{cmp_['diferencia_m3']:.2f}" + r"}{\cubic\metre} ("
                   + f"{cmp_['diferencia_pct']:.2f}".replace(".", ",")
                   + r"\%). Método más conservador: \textbf{"
                   + gr.escapar_latex(cmp_["metodo_conservador"]) + r"}.")
        df_m = pd.DataFrame(cmp_["detalle"]).rename(columns={
            "desde": "Abscisa inicial", "hasta": "Abscisa final",
            "longitud": "Longitud", "v_areas_medias": "Volumen areas medias",
            "v_prismoidal": "Volumen prismoidal", "diferencia": "Diferencia"})
        tex.append(gr.tabla_larga(df_m, "Áreas medias frente a método prismoidal",
                                  "metodos"))

        pp = ga.puntos_de_paso(secciones)
        if pp:
            tex.append(r"\subsection{Puntos de paso}")
            df_pp = pd.DataFrame([{"Abscisa": p["abscisa"], "Transición": p["tipo"],
                                   "Entre abscisas": p.get("entre", "")} for p in pp])
            tex.append(gr.tabla_larga(
                df_pp, "Abscisas de transición entre corte y relleno", "puntos_paso",
                notas="Abscisas de control en obra: la cota roja se anula."))

    # ---------- Curva masa y acarreo ----------
    if path_masas:
        tex.append(r"\section{Diagrama de Masas (Curva Masa)}")
        tex.append(r"Evolución del volumen acumulado en función de la abscisa.")
        tex.append(_figura(path_masas,
                           "Diagrama de masas para compensación longitudinal", None))

    if acar:
        tex.append(r"\section{Análisis de Acarreo}")
        tex.append(r"Distancia de acarreo libre considerada: \SI{"
                   + f"{acarreo_libre:.0f}" + r"}{\metre}. "
                   + f"Se identificaron {acar['resumen']['n_lazos']} lazos de "
                   + f"compensación y {len(acar['puntos_compensacion'])} puntos de "
                   + r"compensación.")
        df_a = pd.DataFrame(acar["lazos"]).rename(columns={
            "desde": "Abscisa inicial", "hasta": "Abscisa final",
            "longitud": "Longitud", "tipo": "Tipo",
            "volumen_compensado": "Volumen compensado",
            "area_diagrama": "Area diagrama",
            "distancia_media_transporte": "Distancia media transporte",
            "excede_acarreo_libre": "Excede acarreo libre",
            "sobreacarreo_m3_m": "Sobreacarreo m3-m",
            "sobreacarreo_m3_estacion": "Sobreacarreo m3-estacion"})
        tex.append(gr.tabla_larga(
            df_a, "Análisis de acarreo por lazos del diagrama de masas", "acarreo",
            notas="La distancia media de transporte es el cociente entre el área "
                  "del lazo y su volumen compensado. El sobreacarreo corresponde "
                  "al transporte que excede la distancia de acarreo libre.",
            forzar_landscape=True))
        tex.append(gr.caja_dictamen(
            "Resumen de acarreo y disposición de material",
            f"Volumen total compensado: "
            f"\\SI{{{acar['resumen']['volumen_total_compensado']:.2f}}}{{\\cubic\\metre}}. "
            f"Sobreacarreo acumulado: "
            f"\\num{{{acar['resumen']['sobreacarreo_total_m3_estacion']:.2f}}} "
            f"m\\textsuperscript{{3}}-estación de \\SI{{{estacion_m:.0f}}}{{\\metre}}. "
            f"Volumen a botadero: "
            f"\\SI{{{acar['resumen']['volumen_botadero']:.2f}}}{{\\cubic\\metre}}; "
            f"material de préstamo: "
            f"\\SI{{{acar['resumen']['volumen_prestamo']:.2f}}}{{\\cubic\\metre}}.",
            estado="alerta"))

    if path_grafico:
        tex.append(_figura(path_grafico, "Planta del alineamiento del proyecto",
                           "Alineamiento del Proyecto"))

    tex.append(r"\section{Conclusiones y Dictamen Técnico}")
    tex.append(r"\begin{itemize}[leftmargin=1.2em,itemsep=3pt]")
    tex.append(r"\item " + evaluar_volumen(bal["balance_real"], corte, relleno))
    tex.append(r"\item El balance corregido difiere del geométrico en \SI{"
               + f"{bal['diferencia_vs_geometrico']:.2f}" + r"}{\cubic\metre}; "
               r"emplear el balance geométrico subestimaría la necesidad de material.")
    if cmp_:
        tex.append(r"\item La diferencia entre métodos de cálculo es de "
                   + f"{cmp_['diferencia_pct']:.2f}".replace(".", ",") + r"\%.")
    tex.append(r"\item El \textbf{diagrama de masas} identifica los puntos críticos "
               r"y la distribución longitudinal del material.")
    tex.append(r"\end{itemize}")

    # ---------- Anexo de secciones ----------
    if paths_secciones:
        tex.append(_anexo_secciones(paths_secciones))

    tex.append(gr.bloque_firmas())
    tex.append(gr.cierre_bibliografia())
    tex.append(r"\end{document}")
    return "\n".join(tex)


# ===================================================================
# AUXILIARES DE MAQUETACIÓN
# ===================================================================
def _figura(path, caption, titulo_seccion=None):
    out = []
    if titulo_seccion:
        out.append(r"\section{" + gr.escapar_latex(titulo_seccion) + r"}")
    p = str(path).replace("\\", "/")
    out += [r"\begin{figure}[H]", r"  \centering",
            r"  \includegraphics[width=0.95\textwidth]{" + p + r"}",
            r"  \caption{" + gr.escapar_latex(caption) + r"}",
            r"\end{figure}"]
    return "\n".join(out)


def _mosaico_fotos(fotos_paths, caption, titulo):
    """Mosaico 2xN con minipage: evita el desbordamiento del \\includegraphics suelto."""
    out = [r"\subsection{" + gr.escapar_latex(titulo) + r"}",
           r"\begin{figure}[H]", r"  \centering"]
    for i, p in enumerate(list(fotos_paths)[:6]):
        out.append(r"  \begin{minipage}{0.47\textwidth}\centering")
        out.append(r"    \includegraphics[width=\linewidth, height=5cm, "
                   r"keepaspectratio]{" + str(p).replace("\\", "/") + r"}")
        out.append(r"  \end{minipage}")
        out.append(r"  \\[0.4cm]" if i % 2 == 1 else r"  \hfill")
    out += [r"  \caption{" + gr.escapar_latex(caption) + r"}", r"\end{figure}"]
    return "\n".join(out)


def _anexo_secciones(paths_secciones, por_plancha=8):
    """paths_secciones: lista de tuplas (abscisa, ruta_imagen)."""
    out = [r"\newpage",
           r"\section{Anexo Gráfico: Perfiles de Secciones Transversales}"]
    datos = sorted(paths_secciones, key=lambda x: x[0])
    planchas = [datos[i:i + por_plancha] for i in range(0, len(datos), por_plancha)]
    for j, chunk in enumerate(planchas):
        out += [r"\begin{figure}[H]", r"  \centering"]
        for i, (absc, p) in enumerate(chunk):
            out.append(r"  \begin{minipage}{0.47\textwidth}\centering")
            out.append(r"    \includegraphics[width=\linewidth]{"
                       + str(p).replace("\\", "/") + r"}\\")
            out.append(r"    {\scriptsize Abscisa " + gr.escapar_latex(str(absc)) + r"}")
            out.append(r"  \end{minipage}")
            out.append(r"  \\[0.35cm]" if i % 2 == 1 else r"  \hfill")
        out += [r"  \caption{Secciones transversales — plancha " + str(j + 1) + r"}",
                r"\end{figure}"]
        if j < len(planchas) - 1:
            out.append(r"\newpage")
    return "\n".join(out)


# ===================================================================
# DICTÁMENES (versión con \textbf válido dentro de las cajas)
# ===================================================================
def evaluar_precision(prec_h):
    if prec_h <= 0:
        return ("La poligonal presenta un error matemático crítico o no logró cerrar. "
                "Es obligatorio revisar la cartera de campo y garantizar el amarre "
                "correcto de los datos.")
    if prec_h < 1000:
        return (f"Se obtuvo una precisión de 1:{int(prec_h)}, calificada como "
                r"\textbf{DEFICIENTE}. No cumple los estándares mínimos para "
                "levantamientos topográficos convencionales; se recomienda revisar "
                "los ángulos observados o repetir la medición en campo.")
    if prec_h < 5000:
        return (f"Se obtuvo una precisión de 1:{int(prec_h)}, calificada como "
                r"\textbf{BAJA}. Aceptable únicamente para levantamientos rurales "
                "expeditos o estimaciones preliminares.")
    if prec_h < 15000:
        return (f"Se obtuvo una precisión de 1:{int(prec_h)}, calificada como "
                r"\textbf{BUENA}. Cumple los estándares para levantamientos urbanos "
                "y diseño de obras civiles de rigor intermedio.")
    return (f"Se obtuvo una precisión de 1:{int(prec_h)}, calificada como "
            r"\textbf{ALTA}. Aplicable a redes de control de alta exigencia e "
            "infraestructura pesada.")


def evaluar_volumen(neto, corte, relleno):
    if neto > 0:
        return ("El balance volumétrico exige transporte de material excedentario "
                "hacia un sitio de disposición final (botadero).")
    if neto < 0:
        return ("El diseño requiere importación de material de préstamo, dado que "
                "el relleno supera el material obtenido por excavación.")
    return ("El diseño presenta compensación volumétrica prácticamente perfecta, "
            "optimizando costos de movimiento de tierras y transporte.")


def _tabla_metricas_cierre(metricas):
    out = [r"\begin{table}[H]", r"  \centering \small",
           r"  \caption{Métricas de cierre geométrico previas al ajuste}",
           r"  \begin{tabular}{l S[table-format=2.5]}", r"    \toprule",
           r"    \rowcolor{GeoBlue}",
           r"    \textcolor{white}{\bfseries Parámetro analizado} & "
           r"{\textcolor{white}{\bfseries Magnitud}} \\", r"    \midrule"]
    filas = [
        (r"Error horizontal Este ($e_x$) [m]", metricas.get("err_e_ant", 0)),
        (r"Error horizontal Norte ($e_y$) [m]", metricas.get("err_n_ant", 0)),
        (r"Error vertical ($\Delta Z$) [m]", metricas.get("err_v_ant", 0)),
        (r"Error lineal de cierre ($e_L$) [m]", metricas.get("err_h_ant", 0)),
    ]
    for i, (nombre, val) in enumerate(filas):
        if i % 2 == 0:
            out.append(r"    \rowcolor{GeoBlue!5}")
        out.append(f"    {nombre} & {gr.numero_plano(val, 5)} \\\\")
    out.append(r"    \midrule")
    out.append(r"    Error angular bruto & {"
               + gr.escapar_latex(str(metricas.get("err_ang_ant", "---"))) + r"} \\")
    out.append(r"    \rowcolor{GeoBlue!5}")
    out.append(r"    Precisión planimétrica & {1:"
               + str(int(metricas.get("prec_h", 0) or 0)) + r"} \\")
    out.append(r"    Precisión vertical & {1:"
               + str(int(metricas.get("prec_v", 0) or 0)) + r"} \\")
    out += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}"]
    return "\n".join(out)
