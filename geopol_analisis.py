# ===================================================================
# GEOPOL WEB - MÓDULO DE ANÁLISIS TÉCNICO
# Cálculos numéricos puros (sin LaTeX) que alimentan los informes.
# Todas las funciones devuelven dicts listos para renderizar.
# ===================================================================
import math
import numpy as np

# -------------------------------------------------------------------
# CONSTANTES GEODÉSICAS
# -------------------------------------------------------------------
GRS80_A = 6378137.0                 # Semieje mayor GRS80 / WGS84 [m]
GRS80_F = 1.0 / 298.257222101       # Achatamiento GRS80
GRS80_E2 = 2 * GRS80_F - GRS80_F ** 2

# MAGNA-SIRGAS / Origen Nacional (EPSG:9377) - Transversa de Mercator
EPSG_9377 = {
    "nombre": "MAGNA-SIRGAS / Origen-Nacional",
    "epsg": 9377,
    "lat_origen": 4.0,          # grados N
    "meridiano_central": -73.0,  # grados
    "k0": 0.9992,
    "falso_este": 5_000_000.0,
    "falso_norte": 2_000_000.0,
}

M2_POR_FANEGADA = 6400.0    # Fanegada catastral (Cundinamarca / Bogotá)
M2_POR_HECTAREA = 10000.0


# ===================================================================
# 1. UTILIDADES ANGULARES
# ===================================================================
def dms_a_segundos(valor):
    """
    Convierte un ángulo a segundos de arco. Acepta:
      - float/int  -> se interpreta como GRADOS decimales
      - "12 34 56.7", "12-34-56.7", "12:34:56.7"
      - "12°34'56.7\"" (con o sin símbolos)
    Devuelve float (segundos). Conserva el signo.
    """
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float, np.number)):
        return float(valor) * 3600.0

    txt = str(valor).strip()
    if not txt:
        return 0.0
    signo = -1.0 if txt.lstrip().startswith("-") else 1.0
    # Normaliza cualquier separador a espacio
    limpio = (txt.replace("°", " ").replace("º", " ").replace("'", " ")
                 .replace('"', " ").replace("’", " ").replace("”", " ")
                 .replace("-", " ").replace(":", " ").replace("d", " ")
                 .replace("m", " ").replace("s", " "))
    partes = [p for p in limpio.split() if p]
    try:
        nums = [abs(float(p)) for p in partes]
    except ValueError:
        return 0.0
    if not nums:
        return 0.0
    g = nums[0] if len(nums) > 0 else 0.0
    m = nums[1] if len(nums) > 1 else 0.0
    s = nums[2] if len(nums) > 2 else 0.0
    if len(nums) == 1:
        # Un solo número: se asume grados decimales
        return signo * g * 3600.0
    return signo * (g * 3600.0 + m * 60.0 + s)


def segundos_a_dms(segundos, decimales=1):
    """Formatea segundos de arco como G° MM' SS.s\" (texto plano, sin LaTeX)."""
    signo = "-" if segundos < 0 else ""
    seg = abs(float(segundos))
    g = int(seg // 3600)
    m = int((seg - g * 3600) // 60)
    s = seg - g * 3600 - m * 60
    return f"{signo}{g}° {m:02d}' {s:0{4 + decimales}.{decimales}f}\""


# ===================================================================
# 2. POLIGONAL: TOLERANCIAS Y DICTAMEN
# ===================================================================
def tolerancia_angular(precision_equipo_seg, n_vertices, factor=2.0):
    """
    Tolerancia angular Ta = k * a * sqrt(n)
      precision_equipo_seg : precisión angular nominal del equipo ["], p.ej. 5
      n_vertices           : número de vértices (estaciones) del circuito
      factor k             : 1.0 exigente, 2.0 estándar en obra civil, 3.0 expedito
    """
    n = max(int(n_vertices), 1)
    return float(factor) * float(precision_equipo_seg) * math.sqrt(n)


def evaluar_cierre_angular(err_angular, precision_equipo_seg=5.0,
                           n_vertices=1, factor=2.0):
    """
    Compara el error angular observado contra la tolerancia calculada.
    'err_angular' puede venir como string DMS o como grados decimales.
    """
    err_seg = dms_a_segundos(err_angular)
    tol_seg = tolerancia_angular(precision_equipo_seg, n_vertices, factor)
    cumple = abs(err_seg) <= tol_seg
    razon = abs(err_seg) / tol_seg if tol_seg > 0 else float("inf")
    return {
        "error_seg": err_seg,
        "error_dms": segundos_a_dms(err_seg),
        "tolerancia_seg": tol_seg,
        "tolerancia_dms": segundos_a_dms(tol_seg),
        "cumple": cumple,
        "razon_uso": razon,          # <1 cumple; 0.5 = usa la mitad de la tolerancia
        "estado": "ok" if razon <= 0.7 else ("alerta" if cumple else "critico"),
        "formula": r"T_a = k \cdot a \sqrt{n}",
        "parametros": {"k": factor, "a": precision_equipo_seg, "n": int(n_vertices)},
    }


def evaluar_cierre_lineal(err_lineal, perimetro, precision_exigida=10000):
    """
    Evalúa el cierre lineal contra una precisión relativa exigida (1:P).
    Devuelve también la tolerancia lineal equivalente en metros.
    """
    perimetro = float(perimetro)
    tol_m = perimetro / float(precision_exigida) if precision_exigida > 0 else 0.0
    prec_obtenida = (perimetro / abs(err_lineal)) if err_lineal else float("inf")
    cumple = abs(err_lineal) <= tol_m
    return {
        "error_m": float(err_lineal),
        "tolerancia_m": tol_m,
        "precision_obtenida": prec_obtenida,
        "precision_exigida": precision_exigida,
        "cumple": cumple,
        "estado": "ok" if cumple else "critico",
    }


def azimut_error_cierre(err_e, err_n):
    """
    Azimut (desde el Norte, sentido horario) del vector de error de cierre.
    Indica la DIRECCIÓN del error: un lado con azimut similar es sospechoso
    de tener la distancia mal medida.
    """
    if abs(err_e) < 1e-12 and abs(err_n) < 1e-12:
        return {"azimut_grados": None, "azimut_dms": "---", "magnitud": 0.0}
    az = math.degrees(math.atan2(float(err_e), float(err_n))) % 360.0
    mag = math.hypot(float(err_e), float(err_n))
    return {
        "azimut_grados": az,
        "azimut_dms": segundos_a_dms(az * 3600.0),
        "magnitud": mag,
    }


def lado_sospechoso(err_e, err_n, azimutes_lados, tolerancia_grados=8.0):
    """
    azimutes_lados: dict {nombre_lado: azimut_en_grados}
    Devuelve los lados cuyo azimut (o su recíproco) coincide con la dirección
    del error de cierre. Técnica clásica de detección de error de distancia.
    """
    info = azimut_error_cierre(err_e, err_n)
    if info["azimut_grados"] is None or not azimutes_lados:
        return []
    az_err = info["azimut_grados"]
    candidatos = []
    for nombre, az in azimutes_lados.items():
        for az_test in (float(az) % 360.0, (float(az) + 180.0) % 360.0):
            dif = abs((az_test - az_err + 180.0) % 360.0 - 180.0)
            if dif <= tolerancia_grados:
                candidatos.append({"lado": nombre, "azimut": float(az), "desviacion": dif})
                break
    return sorted(candidatos, key=lambda d: d["desviacion"])


# ===================================================================
# 3. FACTOR DE ESCALA COMBINADO (crítico para EPSG:9377)
# ===================================================================
def radio_medio_curvatura(lat_grados):
    """Radio medio de curvatura Rm = sqrt(M*N) del elipsoide GRS80."""
    lat = math.radians(float(lat_grados))
    s2 = math.sin(lat) ** 2
    w = math.sqrt(1 - GRS80_E2 * s2)
    N = GRS80_A / w                              # radio primer vertical
    M = GRS80_A * (1 - GRS80_E2) / (w ** 3)      # radio meridiano
    return math.sqrt(M * N)


def factor_escala_combinado(este, altura_elipsoidal, lat_grados=4.0, proy=EPSG_9377):
    """
    Factor combinado = factor de escala de cuadrícula x factor de elevación.
    Convierte DISTANCIA DE TERRENO -> DISTANCIA DE CUADRÍCULA:
        D_cuadricula = D_terreno * factor_combinado

    este                : coordenada Este de la zona de trabajo [m]
    altura_elipsoidal   : altura sobre el elipsoide [m] (h = H + N_ondulacion)
    """
    Rm = radio_medio_curvatura(lat_grados)
    x = (float(este) - proy["falso_este"]) / proy["k0"]
    k_cuadricula = proy["k0"] * (1.0 + x ** 2 / (2.0 * Rm ** 2)
                                + x ** 4 / (24.0 * Rm ** 4))
    k_elevacion = Rm / (Rm + float(altura_elipsoidal))
    k_comb = k_cuadricula * k_elevacion
    return {
        "radio_medio": Rm,
        "distancia_meridiano_central": x,
        "factor_cuadricula": k_cuadricula,
        "factor_elevacion": k_elevacion,
        "factor_combinado": k_comb,
        "ppm": (k_comb - 1.0) * 1e6,
        "proyeccion": proy["nombre"],
        "epsg": proy["epsg"],
    }


def aplicar_factor_escala(distancias_terreno, factor_combinado):
    """Devuelve lista de tuplas (D_terreno, D_cuadricula, delta)."""
    out = []
    for d in distancias_terreno:
        dg = float(d) * factor_combinado
        out.append((float(d), dg, dg - float(d)))
    return out


# ===================================================================
# 4. GEOMETRÍA: ÁREA, PERÍMETRO, PROYECCIONES
# ===================================================================
def area_gauss(coords):
    """
    Área por el método de Gauss (dobles áreas / shoelace).
    coords: lista de (este, norte) en orden del polígono, sin repetir el 1er punto.
    """
    pts = [(float(e), float(n)) for e, n in coords]
    if len(pts) < 3:
        return {"area_m2": 0.0, "area_ha": 0.0, "area_fanegadas": 0.0,
                "perimetro_m": 0.0, "sentido": "indefinido"}
    doble = 0.0
    perim = 0.0
    n_p = len(pts)
    for i in range(n_p):
        e1, n1 = pts[i]
        e2, n2 = pts[(i + 1) % n_p]
        doble += (e1 * n2 - e2 * n1)
        perim += math.hypot(e2 - e1, n2 - n1)
    area = abs(doble) / 2.0
    return {
        "area_m2": area,
        "area_ha": area / M2_POR_HECTAREA,
        "area_fanegadas": area / M2_POR_FANEGADA,
        "perimetro_m": perim,
        "sentido": "antihorario" if doble > 0 else "horario",
        "n_vertices": n_p,
    }


def tabla_proyecciones(lados):
    """
    Memoria de cálculo de proyecciones y compensación por regla de la brújula
    (Bowditch). Es la tabla que un interventor pide para auditar el ajuste.

    lados: lista de dicts {'lado': 'A-B', 'distancia': 45.32, 'azimut': 128.5432}
           (azimut en GRADOS decimales)
    Devuelve dict con 'filas' y 'resumen'.
    """
    filas = []
    sum_d = 0.0
    for L in lados:
        d = float(L["distancia"])
        az = math.radians(float(L["azimut"]))
        de = d * math.sin(az)
        dn = d * math.cos(az)
        sum_d += d
        filas.append({"lado": L.get("lado", ""), "distancia": d,
                      "azimut": float(L["azimut"]), "delta_e": de, "delta_n": dn})

    err_e = sum(f["delta_e"] for f in filas)
    err_n = sum(f["delta_n"] for f in filas)

    for f in filas:
        prop = f["distancia"] / sum_d if sum_d > 0 else 0.0
        f["corr_e"] = -err_e * prop
        f["corr_n"] = -err_n * prop
        f["delta_e_aj"] = f["delta_e"] + f["corr_e"]
        f["delta_n_aj"] = f["delta_n"] + f["corr_n"]

    return {
        "filas": filas,
        "resumen": {
            "perimetro": sum_d,
            "error_e": err_e,
            "error_n": err_n,
            "error_lineal": math.hypot(err_e, err_n),
            "suma_corr_e": sum(f["corr_e"] for f in filas),
            "suma_corr_n": sum(f["corr_n"] for f in filas),
            "delta_e_aj_total": sum(f["delta_e_aj"] for f in filas),
            "delta_n_aj_total": sum(f["delta_n_aj"] for f in filas),
        },
        "metodo": "Regla de la Brújula (Bowditch)",
    }


def estadisticos_red(distancias):
    """Indicadores baratos de calidad geométrica de la red."""
    d = [float(x) for x in distancias if x is not None and float(x) > 0]
    if not d:
        return {}
    return {
        "n_lados": len(d),
        "longitud_total": sum(d),
        "lado_medio": float(np.mean(d)),
        "lado_min": min(d),
        "lado_max": max(d),
        "relacion_max_min": max(d) / min(d),
        "desv_std": float(np.std(d, ddof=1)) if len(d) > 1 else 0.0,
    }


# ===================================================================
# 5. NIVELACIÓN
# ===================================================================
# mm por sqrt(K en km). VERIFICAR contra la especificación IGAC vigente
# antes de usar en producción; se dejan configurables a propósito.
ORDENES_NIVELACION = {
    "Primer orden - Clase I":  4.0,
    "Primer orden - Clase II": 5.0,
    "Segundo orden - Clase I": 6.0,
    "Segundo orden - Clase II": 8.0,
    "Tercer orden":            12.0,
    "Expedito / configuración": 20.0,
}


def tolerancia_nivelacion(longitud_km, orden="Tercer orden"):
    """Tolerancia e = k * sqrt(K) [mm], con K en kilómetros."""
    k = ORDENES_NIVELACION.get(orden, 12.0)
    K = max(float(longitud_km), 0.0)
    return {"k": k, "K_km": K, "tolerancia_mm": k * math.sqrt(K), "orden": orden}


def evaluar_cierre_altimetrico(error_cierre_mm, longitud_km, orden="Tercer orden"):
    tol = tolerancia_nivelacion(longitud_km, orden)
    err = abs(float(error_cierre_mm))
    cumple = err <= tol["tolerancia_mm"]
    razon = err / tol["tolerancia_mm"] if tol["tolerancia_mm"] > 0 else float("inf")
    return {
        "error_mm": float(error_cierre_mm),
        "tolerancia_mm": tol["tolerancia_mm"],
        "orden": orden,
        "k": tol["k"],
        "K_km": tol["K_km"],
        "cumple": cumple,
        "razon_uso": razon,
        "estado": "ok" if razon <= 0.7 else ("alerta" if cumple else "critico"),
        "formula": r"e_{tol} = k \sqrt{K}",
    }


def chequeo_aritmetico_cartera(sum_vista_atras, sum_vista_adelante,
                               cota_inicial, cota_final_cruda, tol=1e-4):
    """
    Control clásico de revisión de cartera:
        Sigma(V+) - Sigma(V-) debe ser igual a (Cota final - Cota inicial)
    Si no cierra, hay un error de transcripción o de suma, NO de campo.
    """
    lado_izq = float(sum_vista_atras) - float(sum_vista_adelante)
    lado_der = float(cota_final_cruda) - float(cota_inicial)
    dif = lado_izq - lado_der
    return {
        "sigma_mas": float(sum_vista_atras),
        "sigma_menos": float(sum_vista_adelante),
        "diferencia_sumatorias": lado_izq,
        "diferencia_cotas": lado_der,
        "discrepancia": dif,
        "cuadra": abs(dif) <= tol,
        "estado": "ok" if abs(dif) <= tol else "critico",
        "mensaje": ("La cartera cuadra aritméticamente." if abs(dif) <= tol else
                    "La cartera NO cuadra: existe un error de suma o transcripción, "
                    "independiente del error de cierre de campo."),
    }


def correccion_curvatura_refraccion(distancia_m):
    """
    C&R = 0.0675 * K^2  [m], con K en km. Se resta a la lectura de mira.
    Solo relevante en visuales largas (> ~100 m).
    """
    K = float(distancia_m) / 1000.0
    return 0.0675 * K ** 2


def balance_visuales(dist_atras, dist_adelante):
    """
    El desbalance entre distancias atrás/adelante es lo que deja pasar el
    error de colimación. Se busca desbalance ~ 0.
    """
    sa = sum(float(x) for x in dist_atras)
    sd = sum(float(x) for x in dist_adelante)
    total = sa + sd
    desb = sa - sd
    return {
        "suma_atras": sa,
        "suma_adelante": sd,
        "desbalance_m": desb,
        "desbalance_pct": (abs(desb) / total * 100.0) if total > 0 else 0.0,
        "longitud_total_m": total,
        "longitud_total_km": total / 1000.0,
        "visual_max_atras": max((float(x) for x in dist_atras), default=0.0),
        "visual_max_adelante": max((float(x) for x in dist_adelante), default=0.0),
        "estado": "ok" if total > 0 and abs(desb) / total <= 0.02 else "alerta",
    }


def distribuir_error_altimetrico(puntos, error_cierre_m, modo="distancia"):
    """
    Reparte el error de cierre y devuelve la corrección PUNTO POR PUNTO
    (es lo que hoy falta en el informe: se dice que se distribuyó, pero no
    cuánto le tocó a cada punto).

    puntos: lista de dicts {'punto': 'BM-1', 'cota_cruda': 2550.123,
                            'distancia_acum': 120.5}
    modo  : 'distancia' (proporcional a la distancia acumulada)
            'estaciones' (proporcional al número de cambios)
    """
    n = len(puntos)
    if n == 0:
        return []
    if modo == "distancia":
        total = float(puntos[-1].get("distancia_acum", 0.0)) or 1.0
        pesos = [float(p.get("distancia_acum", 0.0)) / total for p in puntos]
    else:
        pesos = [(i + 1) / n for i in range(n)]

    salida = []
    for p, w in zip(puntos, pesos):
        corr = -float(error_cierre_m) * w
        salida.append({
            "punto": p.get("punto", ""),
            "distancia_acum": float(p.get("distancia_acum", 0.0)),
            "cota_cruda": float(p.get("cota_cruda", 0.0)),
            "peso": w,
            "correccion_m": corr,
            "correccion_mm": corr * 1000.0,
            "cota_ajustada": float(p.get("cota_cruda", 0.0)) + corr,
        })
    return salida


def pendientes_entre_puntos(puntos):
    """
    Pendiente (%) entre puntos consecutivos. Es el dato que conecta el informe
    de nivelación con el diseño por gravedad (RAS: alcantarillado / acueducto).
    puntos: lista de dicts {'punto','cota','distancia_acum'}
    """
    out = []
    for a, b in zip(puntos, puntos[1:]):
        dh = float(b.get("distancia_acum", 0.0)) - float(a.get("distancia_acum", 0.0))
        dz = float(b.get("cota", 0.0)) - float(a.get("cota", 0.0))
        pend = (dz / dh * 100.0) if dh else 0.0
        out.append({
            "tramo": f"{a.get('punto','')} - {b.get('punto','')}",
            "dist_horizontal": dh,
            "desnivel": dz,
            "pendiente_pct": pend,
            "sentido": "descendente" if dz < 0 else ("ascendente" if dz > 0 else "plano"),
        })
    return out


# ===================================================================
# 6. VOLÚMENES / MOVIMIENTO DE TIERRAS
# ===================================================================
# Valores orientativos. Deben ajustarse con el estudio geotécnico del proyecto.
FACTORES_MATERIAL = {
    "Material común":  {"esponjamiento": 0.25, "contraccion": 0.10},
    "Arcilla":         {"esponjamiento": 0.35, "contraccion": 0.10},
    "Arena / grava":   {"esponjamiento": 0.12, "contraccion": 0.05},
    "Conglomerado":    {"esponjamiento": 0.30, "contraccion": 0.08},
    "Roca fracturada": {"esponjamiento": 0.50, "contraccion": 0.00},
    "Roca maciza":     {"esponjamiento": 0.60, "contraccion": 0.00},
}


def balance_volumetrico_corregido(corte_banco, relleno_compactado,
                                  material="Material común",
                                  factores=None):
    """
    El balance geométrico (corte - relleno) NO es el balance real:
      - El corte se mide en BANCO y se transporta SUELTO (esponja).
      - El relleno se mide COMPACTADO y exige más volumen de banco (contrae).

    Devuelve el volumen de banco realmente necesario y el balance real.
    """
    f = factores or FACTORES_MATERIAL.get(material, FACTORES_MATERIAL["Material común"])
    esp = float(f["esponjamiento"])
    con = float(f["contraccion"])

    corte_banco = float(corte_banco)
    relleno_compactado = float(relleno_compactado)

    corte_suelto = corte_banco * (1.0 + esp)
    # Banco necesario para conformar el relleno compactado
    factor_compactacion = 1.0 / (1.0 - con) if con < 1.0 else 1.0
    relleno_en_banco = relleno_compactado * factor_compactacion

    balance_geom = corte_banco - relleno_compactado
    balance_real = corte_banco - relleno_en_banco

    return {
        "material": material,
        "esponjamiento": esp,
        "contraccion": con,
        "factor_compactacion": factor_compactacion,
        "corte_banco": corte_banco,
        "corte_suelto": corte_suelto,
        "relleno_compactado": relleno_compactado,
        "relleno_en_banco": relleno_en_banco,
        "balance_geometrico": balance_geom,
        "balance_real": balance_real,
        "volumen_botadero": max(balance_real, 0.0),
        "volumen_prestamo": max(-balance_real, 0.0),
        "diferencia_vs_geometrico": balance_real - balance_geom,
    }


def viajes_volqueta(volumen_suelto_m3, capacidad_m3=7.0, factor_llenado=0.90):
    """Número de viajes de volqueta. El dato más usado en obra."""
    cap_efectiva = float(capacidad_m3) * float(factor_llenado)
    if cap_efectiva <= 0:
        return {"viajes": 0, "capacidad_efectiva": 0.0}
    viajes = math.ceil(float(volumen_suelto_m3) / cap_efectiva)
    return {
        "volumen_suelto": float(volumen_suelto_m3),
        "capacidad_nominal": float(capacidad_m3),
        "factor_llenado": float(factor_llenado),
        "capacidad_efectiva": cap_efectiva,
        "viajes": int(viajes),
    }


def volumen_areas_medias(a1, a2, longitud):
    """V = L/2 * (A1 + A2)"""
    return float(longitud) / 2.0 * (float(a1) + float(a2))


def volumen_prismoidal(a1, am, a2, longitud):
    """V = L/6 * (A1 + 4*Am + A2). Requiere el área de la sección MEDIA real."""
    return float(longitud) / 6.0 * (float(a1) + 4.0 * float(am) + float(a2))


def correccion_prismoidal(longitud, h1, h2, w1, w2):
    """
    Corrección prismoidal clásica (se RESTA al volumen por áreas medias):
        Cp = (L/12) * (h1 - h2) * (w1 - w2)
    h = cota roja (altura en el eje), w = ancho de la sección.
    """
    return float(longitud) / 12.0 * (float(h1) - float(h2)) * (float(w1) - float(w2))


def comparar_metodos_volumen(secciones):
    """
    Compara Áreas Medias vs Prismoidal y reporta la diferencia porcentual.
    Justifica técnicamente el método elegido ante interventoría.

    secciones: lista de dicts {'abscisa','area','area_media'(opc),
                               'cota_roja'(opc),'ancho'(opc)}
    """
    v_medias = 0.0
    v_prism = 0.0
    detalle = []
    for s1, s2 in zip(secciones, secciones[1:]):
        L = abs(float(s2["abscisa"]) - float(s1["abscisa"]))
        a1, a2 = float(s1["area"]), float(s2["area"])
        vm = volumen_areas_medias(a1, a2, L)

        if s1.get("area_media") is not None:
            vp = volumen_prismoidal(a1, float(s1["area_media"]), a2, L)
        elif all(k in s1 and k in s2 for k in ("cota_roja", "ancho")):
            vp = vm - correccion_prismoidal(L, s1["cota_roja"], s2["cota_roja"],
                                            s1["ancho"], s2["ancho"])
        else:
            vp = vm  # sin datos suficientes, coinciden

        v_medias += vm
        v_prism += vp
        detalle.append({"desde": s1["abscisa"], "hasta": s2["abscisa"],
                        "longitud": L, "v_areas_medias": vm, "v_prismoidal": vp,
                        "diferencia": vm - vp})

    dif = v_medias - v_prism
    return {
        "detalle": detalle,
        "total_areas_medias": v_medias,
        "total_prismoidal": v_prism,
        "diferencia_m3": dif,
        "diferencia_pct": (dif / v_medias * 100.0) if v_medias else 0.0,
        "metodo_conservador": "Áreas Medias" if v_medias >= v_prism else "Prismoidal",
    }


def puntos_de_paso(secciones):
    """
    Abscisas donde la sección cambia de corte a relleno (cota roja = 0).
    Se obtienen por interpolación lineal. Son abscisas de control en obra.
    secciones: lista de dicts {'abscisa','cota_roja'}  (+ corte, - relleno)
    """
    out = []
    for s1, s2 in zip(secciones, secciones[1:]):
        h1, h2 = float(s1["cota_roja"]), float(s2["cota_roja"])
        if h1 == 0.0:
            out.append({"abscisa": float(s1["abscisa"]), "tipo": "cota roja nula"})
        if h1 * h2 < 0:
            x1, x2 = float(s1["abscisa"]), float(s2["abscisa"])
            absc = x1 + (x2 - x1) * abs(h1) / (abs(h1) + abs(h2))
            out.append({
                "abscisa": absc,
                "tipo": "corte a relleno" if h1 > 0 else "relleno a corte",
                "entre": f"{x1:.2f} - {x2:.2f}",
            })
    return out


def curva_masa(abscisas, volumenes_netos):
    """
    Volumen acumulado. volumenes_netos: (+) corte, (-) relleno por tramo.
    Devuelve listas alineadas (abscisa, acumulado).
    """
    acum = []
    total = 0.0
    for v in volumenes_netos:
        total += float(v)
        acum.append(total)
    return {"abscisas": [float(a) for a in abscisas],
            "acumulado": acum,
            "ordenada_final": total,
            "maximo": max(acum) if acum else 0.0,
            "minimo": min(acum) if acum else 0.0}


def analisis_acarreo(abscisas, acumulado, distancia_acarreo_libre=100.0,
                     estacion_m=20.0):
    """
    Análisis de acarreo sobre el diagrama de masas. Esto es lo que se PAGA:
      - Puntos de compensación (cruces por cero del acumulado)
      - Volumen compensado por lazo
      - Distancia media de transporte = área del lazo / volumen del lazo
      - Sobreacarreo = (dist. media - acarreo libre) * volumen  [m3-estación]

    estacion_m: longitud de la estación de sobreacarreo (INVÍAS suele usar
                m3-km o m3-estación; ajustar al pliego del contrato).
    """
    x = [float(a) for a in abscisas]
    y = [float(v) for v in acumulado]
    if len(x) < 2:
        return {"lazos": [], "resumen": {}}

    # Cruces por cero -> puntos de compensación
    cruces = [x[0]]
    for i in range(len(y) - 1):
        if y[i] == 0.0:
            cruces.append(x[i])
        elif y[i] * y[i + 1] < 0:
            t = abs(y[i]) / (abs(y[i]) + abs(y[i + 1]))
            cruces.append(x[i] + (x[i + 1] - x[i]) * t)
    cruces.append(x[-1])
    cruces = sorted(set(round(c, 4) for c in cruces))

    lazos = []
    for a, b in zip(cruces, cruces[1:]):
        # Sub-muestreo del lazo
        xs = [a] + [xi for xi in x if a < xi < b] + [b]
        ys = [float(np.interp(xi, x, y)) for xi in xs]
        if len(xs) < 2:
            continue
        area = float(np.trapezoid(np.abs(ys), xs)) if hasattr(np, "trapezoid") \
            else float(np.trapz(np.abs(ys), xs))
        vol = max(abs(v) for v in ys)
        if vol < 1e-9:
            continue
        dist_media = area / vol
        sobre = max(dist_media - float(distancia_acarreo_libre), 0.0)
        lazos.append({
            "desde": a, "hasta": b, "longitud": b - a,
            "tipo": "corte compensa relleno" if max(ys) > 0 else "relleno alimentado por corte",
            "volumen_compensado": vol,
            "area_diagrama": area,
            "distancia_media_transporte": dist_media,
            "excede_acarreo_libre": sobre > 0,
            "sobreacarreo_m3_m": sobre * vol,
            "sobreacarreo_m3_estacion": (sobre * vol / estacion_m) if estacion_m else 0.0,
        })

    ord_final = y[-1]
    return {
        "puntos_compensacion": cruces[1:-1],
        "lazos": lazos,
        "resumen": {
            "n_lazos": len(lazos),
            "volumen_total_compensado": sum(l["volumen_compensado"] for l in lazos),
            "sobreacarreo_total_m3_estacion": sum(l["sobreacarreo_m3_estacion"] for l in lazos),
            "distancia_acarreo_libre": float(distancia_acarreo_libre),
            "ordenada_final": ord_final,
            "volumen_botadero": max(ord_final, 0.0),
            "volumen_prestamo": max(-ord_final, 0.0),
        },
    }
