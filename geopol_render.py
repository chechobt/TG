# ===================================================================
# GEOPOL WEB - MÓDULO DE RENDERIZADO LATEX v2
# Reemplaza/complementa las funciones de presentación del motor original.
# ===================================================================
import os
import re
import unicodedata
from datetime import datetime

import numpy as np
import pandas as pd


# ===================================================================
# 1. ESCAPADO Y LIMPIEZA  (corrige el bug del backslash)
# ===================================================================
# Un diccionario recorrido en bucle NO sirve: al reemplazar "\" por
# "\textbackslash{}" las llaves recién insertadas se volverían a escapar en la
# siguiente iteración. Hay que sustituir en UNA SOLA PASADA con regex.
_MAPA_ESCAPE = {
    # --- Caracteres reservados de LaTeX ---
    "\\": r"\textbackslash{}",
    "{": r"\{", "}": r"\}", "&": r"\&", "%": r"\%", "$": r"\$",
    "#": r"\#", "_": r"\_",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    "<": r"\textless{}", ">": r"\textgreater{}", "|": r"\textbar{}",
    # --- Símbolos habituales en topografía: se TRANSLITERAN, no se borran ---
    "\u00b0": r"\textdegree{}",          # grado
    "\u00b1": r"$\pm$",                  # mas/menos
    "\u00b2": r"\textsuperscript{2}",    # cuadrado
    "\u00b3": r"\textsuperscript{3}",    # cubico
    "\u00d7": r"$\times$", "\u00f7": r"$\div$",
    "\u00b5": r"$\mu$",
    "\u2206": r"$\Delta$", "\u0394": r"$\Delta$", "\u03a3": r"$\Sigma$",
    "\u03b1": r"$\alpha$", "\u03b2": r"$\beta$", "\u03b3": r"$\gamma$",
    "\u03b8": r"$\theta$", "\u03c6": r"$\varphi$", "\u03c0": r"$\pi$",
    "\u2248": r"$\approx$", "\u2264": r"$\leq$", "\u2265": r"$\geq$",
    "\u2260": r"$\neq$", "\u221a": r"$\sqrt{}$",
    "\u2013": "--", "\u2014": "---",
    "\u2018": "`", "\u2019": "'", "\u201c": "``", "\u201d": "''",
    "\u2032": r"$'$", "\u2033": r"$''$",   # minutos y segundos de arco
    "\u2212": r"$-$", "\u2026": r"\ldots{}", "\u00a0": "~",
    "\u00bd": r"$1/2$", "\u00bc": r"$1/4$", "\u2030": r"\textperthousand{}",
}
_RE_ESCAPE = re.compile("|".join(re.escape(k) for k in _MAPA_ESCAPE))

# Rangos de emoji / pictogramas que pdfLaTeX no puede representar.
_RE_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF"   # emoticones, pictogramas, transporte, simbolos
    "\U00002600-\U000027BF"    # simbolos misceláneos y dingbats
    "\U0001F1E6-\U0001F1FF"    # banderas
    "\U0000FE00-\U0000FE0F"    # selectores de variación
    "\U00002190-\U000021FF"    # flechas
    "\U00002B00-\U00002BFF]+"  # flechas y formas
)


def limpiar_emojis(texto):
    """
    Elimina SOLO emojis y pictogramas irrepresentables en pdfLaTeX.
    A diferencia de un filtro por categoría Unicode, conserva el ASCII
    completo (^, |, $) y los símbolos técnicos (°, ±, m², Delta), que se
    transliteran después en escapar_latex().

    Resuelve de forma general el caso de columnas como '📸 Tomar_Fotos',
    en lugar de depender de que el nombre coincida exactamente.
    """
    if not isinstance(texto, str):
        texto = str(texto)
    texto = _RE_EMOJI.sub("", texto)
    texto = "".join(ch for ch in texto
                    if ord(ch) < 128 or unicodedata.category(ch)
                    not in ("Cc", "Cf", "Cs", "Co", "Cn"))
    return re.sub(r"\s+", " ", texto).strip()


def escapar_latex(texto):
    """
    Escapa texto arbitrario para LaTeX en UNA sola pasada.
    Seguro con barras invertidas, llaves, emojis y símbolos técnicos.
    """
    if texto is None:
        return "---"
    if not isinstance(texto, str):
        texto = str(texto)
    texto = limpiar_emojis(texto)
    return _RE_ESCAPE.sub(lambda m: _MAPA_ESCAPE[m.group(0)], texto)


def limpiar_columnas_df(df):
    """Quita columnas de widgets/emoji y normaliza los encabezados."""
    df = df.copy()
    a_borrar = [c for c in df.columns
                if limpiar_emojis(str(c)).lower() in ("tomar_fotos", "tomar fotos", "")]
    if a_borrar:
        df = df.drop(columns=a_borrar, errors="ignore")
    df.columns = [limpiar_emojis(str(c)) for c in df.columns]
    return df


# ===================================================================
# 2. FORMATO NUMÉRICO POR COLUMNA
# ===================================================================
# En lugar de forzar 3 decimales a TODO (abscisas, ángulos, coordenadas y
# volúmenes necesitan precisiones distintas), se define un perfil por columna.
FORMATOS_POR_DEFECTO = {
    # patrón regex en el nombre de columna -> (decimales, formato siunitx)
    r"abscis|pk|k\d":                (2, "4.2"),
    r"norte|este|coord|^n$|^e$":     (3, "7.3"),
    r"cota|elevaci|z$|altura":       (3, "4.3"),
    r"^dist|distanc|longitud":       (3, "4.3"),
    r"area|área":                    (2, "4.2"),
    r"volumen|vol_|corte|relleno":   (2, "6.2"),
    r"azimut|ángulo|angulo|rumbo":   (4, "3.4"),
    r"correc|error":                 (4, "1.4"),
    r"pendiente|%|porcent":          (2, "3.2"),
}


def decidir_formato(nombre_col, formatos=None):
    """Devuelve (decimales, table-format) para una columna dada."""
    tabla = dict(FORMATOS_POR_DEFECTO)
    if formatos:
        tabla.update(formatos)
    nombre = str(nombre_col).lower()
    for patron, val in tabla.items():
        if re.search(patron, nombre):
            return val
    return (3, "5.3")


def numero_plano(val, decimales=3):
    """
    Número con punto decimal, SIN separador de miles.
    siunitx se encarga de mostrarlo como 1.234,567 (formato colombiano).
    Esto reemplaza el hack .replace(',','X').replace('.',',').replace('X','.')
    """
    try:
        return f"{float(val):.{decimales}f}"
    except (TypeError, ValueError):
        return "{---}"


# ===================================================================
# 3. TABLAS: longtable + siunitx (reemplaza dividir_y_generar_tablas)
# ===================================================================
def tabla_larga(df, caption, label, formatos=None, notas=None,
                max_col_portrait=8, forzar_landscape=False):
    """
    Genera una tabla que:
      - se parte sola entre páginas y REPITE el encabezado (longtable)
      - alinea los números por el punto decimal (siunitx, columnas S)
      - rota a horizontal automáticamente si tiene demasiadas columnas

    Sustituye a dividir_y_generar_tablas(): ya no hace falta cortar el
    DataFrame a mano en bloques de 4 columnas.
    """
    df = limpiar_columnas_df(df)
    if df.empty:
        return "\\textit{Sin registros para mostrar.}\n"

    cols = list(df.columns)
    es_numerica = {c: pd.api.types.is_numeric_dtype(df[c]) for c in cols}

    especificacion = []
    for c in cols:
        if es_numerica[c]:
            _, tf = decidir_formato(c, formatos)
            especificacion.append(f"S[table-format={tf}]")
        else:
            especificacion.append("l")

    landscape = forzar_landscape or (len(cols) > max_col_portrait)

    out = []
    if landscape:
        out.append(r"\begin{landscape}")

    out.append(r"\begingroup")
    out.append(r"\footnotesize")
    out.append(r"\setlength{\tabcolsep}{4pt}")
    out.append(r"\begin{longtable}{" + " ".join(especificacion) + "}")
    out.append(f"  \\caption{{{escapar_latex(caption)}}}\\label{{tab:{label}}} \\\\")
    out.append(r"  \toprule")

    # Encabezado: en columnas S el texto debe ir entre llaves
    heads = []
    for c in cols:
        txt = f"\\textcolor{{white}}{{\\bfseries {escapar_latex(c)}}}"
        heads.append("{" + txt + "}")
    fila_head = "  \\rowcolor{GeoBlue}\n  " + " & ".join(heads) + r" \\"

    out.append(fila_head)
    out.append(r"  \midrule")
    out.append(r"  \endfirsthead")
    out.append(r"  \multicolumn{" + str(len(cols)) + r"}{l}{\footnotesize\itshape "
               r"Continuación de la tabla \thetable} \\")
    out.append(r"  \toprule")
    out.append(fila_head)
    out.append(r"  \midrule")
    out.append(r"  \endhead")
    out.append(r"  \midrule")
    out.append(r"  \multicolumn{" + str(len(cols)) + r"}{r}{\footnotesize\itshape "
               r"Continúa en la página siguiente} \\")
    out.append(r"  \endfoot")
    out.append(r"  \bottomrule")
    if notas:
        out.append(r"  \multicolumn{" + str(len(cols)) + r"}{p{0.9\linewidth}}{\footnotesize "
                   + escapar_latex(notas) + r"} \\")
    out.append(r"  \endlastfoot")

    # CUERPO: enumerate() en vez de idx % 2  -> ya no depende del índice
    for i, (_, row) in enumerate(df.iterrows()):
        celdas = []
        for c in cols:
            val = row[c]
            if pd.isna(val):
                celdas.append("{---}" if es_numerica[c] else "---")
            elif es_numerica[c]:
                dec, _ = decidir_formato(c, formatos)
                celdas.append(numero_plano(val, dec))
            else:
                celdas.append(escapar_latex(val))
        color = r"\rowcolor{GeoBlue!5}" if i % 2 == 0 else r"\rowcolor{white}"
        out.append(f"  {color}")
        out.append("  " + " & ".join(celdas) + r" \\")

    out.append(r"\end{longtable}")
    out.append(r"\endgroup")
    if landscape:
        out.append(r"\end{landscape}")
    return "\n".join(out) + "\n"


# ===================================================================
# 4. CAJAS DE DICTAMEN (semáforo)
# ===================================================================
_ESTILO_CAJA = {"ok": "cajaOk", "alerta": "cajaAlerta", "critico": "cajaCritico"}
_ETIQUETA = {"ok": "CUMPLE", "alerta": "CUMPLE CON OBSERVACIONES", "critico": "NO CUMPLE"}


def caja_dictamen(titulo, cuerpo, estado="ok", etiqueta=None):
    """
    Caja coloreada con el veredicto. Reemplaza el 'texto en negrita dentro
    de un itemize' que hoy usa evaluar_precision().
    estado: 'ok' | 'alerta' | 'critico'
    """
    env = _ESTILO_CAJA.get(estado, "cajaAlerta")
    tag = etiqueta or _ETIQUETA.get(estado, "")
    head = f"{escapar_latex(titulo)} \\hfill \\normalfont\\small [{escapar_latex(tag)}]"
    return (f"\\begin{{{env}}}{{{head}}}\n"
            f"{cuerpo}\n"
            f"\\end{{{env}}}\n")


def panel_kpi(items, columnas=3):
    """
    Tarjetas de indicadores para la primera página (después del índice).
    items: lista de dicts {'titulo','valor','sub'(opc),'estado'(opc)}
    """
    mapa = {"ok": "GeoGreen", "alerta": "GeoAmber", "critico": "GeoRed"}
    out = [r"\begin{tcbraster}[raster columns=" + str(columnas) +
           r", raster equal height, raster row skip=3mm, raster column skip=3mm]"]
    for it in items:
        color = mapa.get(it.get("estado", "neutro"), "GeoBlue")
        sub = it.get("sub", "")
        out.append(r"\begin{tcolorbox}[kpi={" + color + "}]")
        out.append(r"{\footnotesize\bfseries " + escapar_latex(it["titulo"]) + r"}\\[2pt]")
        out.append(r"{\LARGE\bfseries " + it["valor"] + r"}")
        if sub:
            out.append(r"\\[2pt]{\scriptsize " + escapar_latex(sub) + r"}")
        out.append(r"\end{tcolorbox}")
    out.append(r"\end{tcbraster}")
    return "\n".join(out) + "\n"


def tabla_cumplimiento(filas, caption="Verificación de cumplimiento normativo"):
    """
    Checklist con semáforo.
    filas: lista de dicts {'criterio','obtenido','tolerancia','estado','norma'}
    """
    simbolo = {"ok": r"\textcolor{GeoGreen}{$\blacksquare$ Cumple}",
               "alerta": r"\textcolor{GeoAmber}{$\blacksquare$ Observación}",
               "critico": r"\textcolor{GeoRed}{$\blacksquare$ No cumple}"}
    out = [r"\begin{table}[H]", r"  \centering",
           f"  \\caption{{{escapar_latex(caption)}}}",
           r"  \small",
           r"  \begin{tabular}{p{4.6cm} r r l l}",
           r"    \toprule",
           r"    \rowcolor{GeoBlue}",
           r"    \textcolor{white}{\bfseries Criterio} & "
           r"\textcolor{white}{\bfseries Obtenido} & "
           r"\textcolor{white}{\bfseries Tolerancia} & "
           r"\textcolor{white}{\bfseries Estado} & "
           r"\textcolor{white}{\bfseries Referencia} \\",
           r"    \midrule"]
    for i, f in enumerate(filas):
        if i % 2 == 0:
            out.append(r"    \rowcolor{GeoBlue!5}")
        out.append("    " + " & ".join([
            escapar_latex(f.get("criterio", "")),
            escapar_latex(f.get("obtenido", "")),
            escapar_latex(f.get("tolerancia", "")),
            simbolo.get(f.get("estado", "alerta"), ""),
            escapar_latex(f.get("norma", "")),
        ]) + r" \\")
    out += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}"]
    return "\n".join(out) + "\n"


# ===================================================================
# 5. BLOQUES NUEVOS DE CONTENIDO
# ===================================================================
def ficha_metadatos(meta):
    """
    Ficha de trazabilidad al inicio del informe. Es lo que sustenta la frase
    'garantizando la trazabilidad requerida en interventoría'.
    meta: dict con claves libres; se recomiendan las de EJEMPLO_METADATOS.
    """
    out = [r"\section*{Ficha técnica del levantamiento}",
           r"\addcontentsline{toc}{section}{Ficha técnica del levantamiento}",
           r"\begin{tcolorbox}[ficha]",
           r"\begin{description}[leftmargin=!,labelwidth=4.2cm,style=nextline,"
           r"font=\bfseries\color{GeoBlue},itemsep=1pt]"]
    for k, v in meta.items():
        out.append(f"  \\item[{escapar_latex(k)}] {escapar_latex(v)}")
    out += [r"\end{description}", r"\end{tcolorbox}"]
    return "\n".join(out) + "\n"


EJEMPLO_METADATOS = {
    "Proyecto": "",
    "Localización": "",
    "Fecha de levantamiento": "",
    "Cuadrilla": "",
    "Condiciones climáticas": "",
    "Equipo utilizado": "",
    "Serie / calibración": "",
    "Precisión angular nominal": "",
    "Precisión EDM": "",
    "Sistema de referencia": "MAGNA-SIRGAS / Origen Nacional (EPSG:9377)",
    "Datum vertical": "Nivel medio del mar - Buenaventura",
    "Unidad angular": "Grados sexagesimales",
    "Punto de amarre": "",
    "Fuente del amarre": "",
    "Versión GeoPol": "",
    "Huella del conjunto de datos": "",
}


def ficha_equipo_a_metadatos(equipo):
    """Convierte un dict de equipo en las claves de la ficha."""
    return {
        "Equipo utilizado": f"{equipo.get('marca','')} {equipo.get('modelo','')}".strip(),
        "Serie / calibración": (f"S/N {equipo.get('serie','---')} - certificado "
                                f"{equipo.get('fecha_calibracion','sin registro')}"),
        "Precisión angular nominal": f"{equipo.get('precision_angular_seg','---')}\"",
        "Precisión EDM": (f"{equipo.get('edm_a_mm','---')} mm + "
                          f"{equipo.get('edm_b_ppm','---')} ppm"),
    }


def bloque_firmas(roles=None):
    """Espacio de firmas y aprobación. Un informe técnico sin esto no se radica."""
    roles = roles or ["Elaboró (Topógrafo)", "Revisó (Director de Proyecto)",
                      "Aprobó (Interventoría)"]
    out = [r"\vspace{1.5cm}", r"\noindent"]
    ancho = round(0.94 / len(roles), 3)
    for r_ in roles:
        out.append(r"\begin{minipage}[t]{" + str(ancho) + r"\textwidth}")
        out.append(r"  \centering \vspace{1.2cm} \rule{0.9\linewidth}{0.4pt}\\[2pt]")
        out.append(r"  {\footnotesize " + escapar_latex(r_) + r"}\\[1pt]")
        out.append(r"  {\scriptsize Nombre / M.P.\ / Fecha}")
        out.append(r"\end{minipage}\hfill")
    return "\n".join(out) + "\n"


def control_versiones(filas):
    """filas: lista de dicts {'version','fecha','descripcion','autor'}"""
    out = [r"\begin{table}[H]", r"  \centering \small",
           r"  \caption{Control de versiones del documento}",
           r"  \begin{tabular}{c c p{7cm} l}", r"    \toprule",
           r"    \rowcolor{GeoBlue}",
           r"    \textcolor{white}{\bfseries Ver.} & \textcolor{white}{\bfseries Fecha} & "
           r"\textcolor{white}{\bfseries Descripción} & \textcolor{white}{\bfseries Autor} \\",
           r"    \midrule"]
    for i, f in enumerate(filas):
        if i % 2 == 0:
            out.append(r"    \rowcolor{GeoBlue!5}")
        out.append("    " + " & ".join([escapar_latex(f.get("version", "")),
                                        escapar_latex(f.get("fecha", "")),
                                        escapar_latex(f.get("descripcion", "")),
                                        escapar_latex(f.get("autor", ""))]) + r" \\")
    out += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}"]
    return "\n".join(out) + "\n"


def monografia_vertices(vertices):
    """
    Monografía por vértice: sin esto las coordenadas no son recuperables en campo.
    vertices: lista de dicts {'nombre','este','norte','cota','lat','lon',
                              'material','monumentacion','descripcion'}
    """
    out = [r"\subsection{Monografía de vértices materializados}"]
    for v in vertices:
        out.append(r"\begin{tcolorbox}[ficha, title={Vértice "
                   + escapar_latex(v.get("nombre", "")) + r"}]")
        out.append(r"\begin{description}[leftmargin=!,labelwidth=3.4cm,"
                   r"font=\bfseries\footnotesize\color{GeoBlue},itemsep=0pt]")
        out.append(r"  \item[Coordenadas planas] E "
                   + numero_plano(v.get("este", 0), 3) + r" m \quad N "
                   + numero_plano(v.get("norte", 0), 3) + r" m")
        if v.get("cota") is not None:
            out.append(r"  \item[Cota] " + numero_plano(v.get("cota", 0), 3) + r" m")
        if v.get("lat") is not None:
            out.append(r"  \item[Coordenadas geográficas] "
                       + escapar_latex(str(v.get("lat"))) + r" / "
                       + escapar_latex(str(v.get("lon"))))
        out.append(r"  \item[Monumentación] " + escapar_latex(v.get("monumentacion", "---")))
        out.append(r"  \item[Material de placa] " + escapar_latex(v.get("material", "---")))
        out.append(r"  \item[Descripción] " + escapar_latex(v.get("descripcion", "---")))
        out.append(r"\end{description}")
        out.append(r"\end{tcolorbox}")
    return "\n".join(out) + "\n"


# ===================================================================
# 6. PREÁMBULO v2
# ===================================================================
def preambulo_v2(ruta_logo="Iconos/logo_geopol.png", babel_opciones="spanish,es-tabla"):
    """
    Preámbulo corregido y ampliado. Cambios frente al original:
      + fontenc T1        -> acentos y silabación correctos (faltaba)
      + siunitx           -> alineación decimal y formato 1.234,567 nativo
      + longtable         -> tablas que se parten y repiten encabezado
      + tcolorbox         -> cajas de dictamen y tarjetas KPI
      + titlesec          -> secciones con color e identidad visual
      + pdflscape         -> tablas anchas en horizontal
      + enumitem/microtype/csquotes/threeparttable
      + caption de tabla arriba (convención en español)
    """
    tex = []
    tex.append(r"\documentclass[11pt,letterpaper]{article}")
    tex.append(r"\usepackage[utf8]{inputenc}")
    tex.append(r"\usepackage[T1]{fontenc}")          # <-- FALTABA
    # lmodern mejora los glifos con T1, pero no está en todas las instalaciones:
    # lmodern + microtype con expansión solo si hay fuentes escalables:
    tex.append(r"\IfFileExists{lmodern.sty}"
               r"{\usepackage{lmodern}\usepackage{microtype}}"
               r"{\usepackage[expansion=false]{microtype}}")
    tex.append(r"\usepackage[" + babel_opciones + r"]{babel}")
    tex.append(r"\usepackage[margin=2.5cm]{geometry}")
    tex.append(r"\usepackage{amsmath,amssymb}")
    tex.append(r"\usepackage{booktabs}")
    tex.append(r"\usepackage{longtable}")
    tex.append(r"\usepackage{threeparttable}")
    tex.append(r"\usepackage{lastpage}")
    tex.append(r"\usepackage{pdflscape}")
    tex.append(r"\usepackage{graphicx}")
    tex.append(r"\usepackage{float}")
    tex.append(r"\usepackage{fancyhdr}")
    tex.append(r"\usepackage[table]{xcolor}")
    tex.append(r"\usepackage{tikz}")
    tex.append(r"\usepackage{transparent}")
    tex.append(r"\usepackage{eso-pic}")
    tex.append(r"\usepackage{caption}")
    tex.append(r"\usepackage{enumitem}")
    tex.append(r"\usepackage{csquotes}")
    tex.append(r"\usepackage{titlesec}")
    tex.append(r"\usepackage{siunitx}")
    tex.append(r"\usepackage[most]{tcolorbox}")
    tex.append(r"\usepackage{hyperref}")             # hyperref siempre al final

    # --- Paleta ---
    tex.append(r"\definecolor{GeoOrange}{HTML}{FF8C00}")
    tex.append(r"\definecolor{GeoBlue}{HTML}{0D47A1}")
    tex.append(r"\definecolor{GeoGreen}{HTML}{2E7D32}")
    tex.append(r"\definecolor{GeoAmber}{HTML}{E65100}")
    tex.append(r"\definecolor{GeoRed}{HTML}{C62828}")
    tex.append(r"\definecolor{GeoGray}{HTML}{455A64}")

    # --- Formato numérico colombiano, resuelto por siunitx ---
    tex.append(r"\sisetup{")
    tex.append(r"  output-decimal-marker={,},")
    tex.append(r"  group-separator={.},")
    tex.append(r"  group-minimum-digits=4,")
    tex.append(r"  detect-weight=true, detect-family=true,")
    tex.append(r"  table-align-text-before=false")
    tex.append(r"}")

    # --- Secciones con identidad visual ---
    tex.append(r"\titleformat{\section}[hang]"
               r"{\normalfont\Large\bfseries\color{GeoBlue}}"
               r"{\thesection}{0.7em}{}[{\color{GeoOrange}\titlerule[1.2pt]}]")
    tex.append(r"\titleformat{\subsection}[hang]"
               r"{\normalfont\large\bfseries\color{GeoGray}}{\thesubsection}{0.6em}{}")
    tex.append(r"\titlespacing*{\section}{0pt}{16pt}{8pt}")

    # --- Captions: tabla arriba, figura abajo ---
    tex.append(r"\captionsetup{font=small, labelfont={bf,color=GeoBlue}}")
    tex.append(r"\captionsetup[table]{position=top, skip=4pt}")
    tex.append(r"\captionsetup[figure]{position=bottom}")

    # --- Estilos tcolorbox ---
    tex.append(r"\tcbset{cajabase/.style={enhanced, breakable, sharp corners=downhill,"
               r" boxrule=0.4pt, left=3mm, right=3mm, top=2mm, bottom=2mm,"
               r" fonttitle=\bfseries\color{white}, attach boxed title to top left="
               r"{xshift=3mm, yshift=-2mm}, boxed title style={sharp corners, boxrule=0pt}}}")
    tex.append(r"\newtcolorbox{cajaOk}[1]{cajabase, colback=GeoGreen!4, "
               r"colframe=GeoGreen, coltitle=white, title={#1}, "
               r"boxed title style={colback=GeoGreen}}")
    tex.append(r"\newtcolorbox{cajaAlerta}[1]{cajabase, colback=GeoAmber!5, "
               r"colframe=GeoAmber, coltitle=white, title={#1}, "
               r"boxed title style={colback=GeoAmber}}")
    tex.append(r"\newtcolorbox{cajaCritico}[1]{cajabase, colback=GeoRed!5, "
               r"colframe=GeoRed, coltitle=white, title={#1}, "
               r"boxed title style={colback=GeoRed}}")
    tex.append(r"\tcbset{ficha/.style={enhanced, breakable, colback=GeoBlue!3, "
               r"colframe=GeoBlue!60, boxrule=0.4pt, sharp corners, "
               r"fonttitle=\bfseries\color{white}, coltitle=white, "
               r"colbacktitle=GeoBlue, left=3mm, right=3mm}}")
    tex.append(r"\tcbset{kpi/.style n args={1}{enhanced, sharp corners, "
               r"colback=#1!6, colframe=#1, boxrule=0.9pt, halign=center, "
               r"valign=center, left=1mm, right=1mm, top=2mm, bottom=2mm, "
               r"fontupper=\color{#1!75!black}}}")

    # --- Marca de agua ---
    if ruta_logo and os.path.exists(ruta_logo):
        logo = ruta_logo.replace("\\", "/")
        tex.append(r"\AddToShipoutPictureBG{\AtPageCenter{\makebox[0pt]{"
                   r"\transparent{0.06}\includegraphics[width=12cm]{" + logo + r"}}}}")

    # --- Encabezados ---
    tex.append(r"\hypersetup{colorlinks=true, linkcolor=GeoBlue, urlcolor=GeoOrange,"
               r" citecolor=GeoGray, pdfborder={0 0 0}}")
    tex.append(r"\pagestyle{fancy}")
    tex.append(r"\fancyhf{}")
    tex.append(r"\fancyhead[L]{\footnotesize\textcolor{GeoBlue}{\textbf{GeoPol Web}}"
               r" -- Reporte Técnico}")
    tex.append(r"\fancyhead[R]{\footnotesize Universidad Distrital F.J.C.}")
    tex.append(r"\fancyfoot[C]{\footnotesize\thepage\ de \pageref{LastPage}}")
    tex.append(r"\renewcommand{\headrulewidth}{0.4pt}")
    tex.append(r"\renewcommand{\footrulewidth}{0.4pt}")
    tex.append(r"\setlength{\parskip}{4pt}")
    tex.append(r"\renewcommand{\arraystretch}{1.15}")
    return "\n".join(tex)


def portada_v2(titulo, autores, tutor, subtitulo=None, lema=None):
    """Portada con las comillas españolas correctas (antes iban invertidas)."""
    lema = lema or r"\enquote{Máxima precisión al alcance de tus manos}"
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
             "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    fecha = f"{meses[datetime.now().month - 1]} de {datetime.now().year}"

    tex = [r"\begin{document}", r"\begin{titlepage}", r"\thispagestyle{empty}",
           r"\begin{tikzpicture}[remember picture,overlay]",
           r"  \fill[GeoBlue] (current page.north west) rectangle "
           r"([yshift=-4cm]current page.north east);",
           r"  \fill[GeoOrange] ([yshift=-4cm]current page.north west) rectangle "
           r"([yshift=-4.5cm]current page.north east);",
           r"  \fill[GeoBlue!5] (current page.south west) rectangle "
           r"([yshift=4cm]current page.south east);",
           r"\end{tikzpicture}",
           r"\vspace*{-2cm}", r"\begin{center}",
           r"  \textcolor{white}{\Huge\bfseries GEOPORTAL WEB (GeoPol)} \\[0.4cm]",
           r"  \textcolor{white}{\large\itshape " + lema + r"} \\[2.6cm]",
           r"  \vspace{2cm}",
           r"  {\LARGE\bfseries INFORME TÉCNICO DE INGENIERÍA} \\[0.4cm]",
           r"  {\Large\bfseries " + escapar_latex(titulo) + r"} \\[0.3cm]"]
    if subtitulo:
        tex.append(r"  {\large\color{GeoGray} " + escapar_latex(subtitulo) + r"} \\[1.6cm]")
    else:
        tex.append(r"  \vspace{1.6cm}")

    tex += [r"  \begin{flushleft}",
            r"    \Large\bfseries Autores del Procesamiento:\\[0.2cm]"]
    for a in autores:
        tex.append(r"    \large $\bullet$ " + escapar_latex(a) + r" \\[0.1cm]")
    tex += [r"    \vspace{0.8cm}",
            r"    \Large\bfseries Tutor -- Director de Proyecto:\\[0.2cm]",
            r"    \large $\bullet$ " + escapar_latex(tutor),
            r"  \end{flushleft}", r"  \vfill",
            r"  \textbf{UNIVERSIDAD DISTRITAL FRANCISCO JOSÉ DE CALDAS}\\[0.2cm]",
            r"  Facultad Tecnológica \\ Ingeniería Civil \\[0.2cm]",
            f"  Bogotá D.C. -- {fecha}",
            r"\end{center}", r"\end{titlepage}",
            r"\tableofcontents", r"\newpage"]
    return "\n".join(tex)


def cierre_bibliografia():
    return "\n".join([r"\section{Referencias Bibliográficas}",
                      r"\nocite{*}",
                      r"\bibliographystyle{apalike}",
                      r"\bibliography{referencias}"])
