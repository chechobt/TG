# ===================================================================
# GEOPOL WEB - COMPILADOR LATEX ROBUSTO
# Reemplaza a compilar_latex_a_pdf(). Cambios clave:
#   - Si BibTeX falla, ADVIERTE pero sigue compilando (antes abortaba el PDF)
#   - Quita -halt-on-error de las pasadas intermedias
#   - Extrae los errores reales del .log en vez de volcar 1500 caracteres
#   - Limpia archivos auxiliares al terminar
# ===================================================================
import os
import re
import shutil
import subprocess

# pdflatex emite bytes en la codificación del sistema (latin-1 en Windows).
# text=True sin errors="replace" revienta con UnicodeDecodeError.
_SUB = dict(capture_output=True, text=True, encoding="utf-8", errors="replace")

BIB_POR_DEFECTO = r"""
@techreport{igac2020,
    author = {{Instituto Geográfico Agustín Codazzi (IGAC)}},
    title = {Resolución 471 de 2020: Adopción del Origen Nacional para Colombia},
    year = {2020}, address = {Bogotá, Colombia}
}
@book{mccormac2004,
    author = {McCormac, Jack C.}, title = {Topografía},
    edition = {4}, year = {2004}, publisher = {Limusa Wiley}
}
@techreport{ras2017,
    author = {{Ministerio de Vivienda, Ciudad y Territorio}},
    title = {Reglamento Técnico para el Sector de Agua Potable y Saneamiento
             Básico (RAS) -- Resolución 0330 de 2017},
    year = {2017}, address = {Bogotá, Colombia}
}
@techreport{invias2022,
    author = {{Instituto Nacional de Vías (INVÍAS)}},
    title = {Especificaciones Generales de Construcción de Carreteras},
    year = {2022}, address = {Bogotá, Colombia}
}
@techreport{nsr10,
    author = {{Asociación Colombiana de Ingeniería Sísmica}},
    title = {Reglamento Colombiano de Construcción Sismo Resistente NSR-10,
             Título H: Estudios Geotécnicos},
    year = {2010}, address = {Bogotá, Colombia}
}
@book{wolf2015,
    author = {Wolf, Paul R. and Ghilani, Charles D.},
    title = {Elementary Surveying: An Introduction to Geomatics},
    edition = {14}, year = {2015}, publisher = {Pearson}
}
"""


def generar_archivo_bib(output_dir, contenido=None):
    os.makedirs(output_dir, exist_ok=True)
    ruta = os.path.join(output_dir, "referencias.bib")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(contenido or BIB_POR_DEFECTO)
    return ruta


def _errores_del_log(ruta_log, max_errores=6):
    """Extrae las líneas de error reales del .log (mucho más útil que el stdout)."""
    if not os.path.exists(ruta_log):
        return "No se generó archivo .log."
    with open(ruta_log, "r", encoding="utf-8", errors="ignore") as f:
        lineas = f.readlines()
    errores = []
    for i, ln in enumerate(lineas):
        if ln.startswith("!") or re.match(r"^l\.\d+", ln):
            bloque = "".join(lineas[i:i + 4]).strip()
            errores.append(bloque)
        if len(errores) >= max_errores:
            break
    return "\n\n".join(errores) if errores else "Sin errores explícitos en el .log."


def limpiar_auxiliares(output_dir, nombre):
    for ext in (".aux", ".bbl", ".blg", ".out", ".toc", ".lof", ".lot", ".fls",
                ".fdb_latexmk", ".synctex.gz"):
        p = os.path.join(output_dir, nombre + ext)
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def compilar_latex_a_pdf(tex_code, output_dir="Reportes_PDF",
                         filename="Reporte_Final", contenido_bib=None,
                         limpiar=True):
    """
    Devuelve (pdf_bytes, ruta, mensaje). 'mensaje' es "OK" o "OK con advertencias: ..."
    """
    os.makedirs(output_dir, exist_ok=True)

    nombre = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(filename))
    nombre = re.sub(r"_+", "_", nombre).strip("_") or "Reporte_Topografico"

    tex_path = os.path.join(output_dir, f"{nombre}.tex")
    pdf_path = os.path.join(output_dir, f"{nombre}.pdf")
    log_path = os.path.join(output_dir, f"{nombre}.log")

    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex_code)
    generar_archivo_bib(output_dir, contenido_bib)

    if shutil.which("pdflatex") is None:
        return None, tex_path, "Error: el sistema no encuentra 'pdflatex'."

    out_dir = output_dir.replace("\\", "/")
    cmd_tex = ["pdflatex", "-interaction=nonstopmode",
               f"-output-directory={out_dir}", tex_path.replace("\\", "/")]
    advertencias = []

    try:
        # Pasada 1: genera .aux
        subprocess.run(cmd_tex, timeout=180, **_SUB)

        # BibTeX: si falla, se advierte pero NO se aborta el informe
        if shutil.which("bibtex"):
            pb = subprocess.run(["bibtex", nombre], cwd=out_dir, timeout=60, **_SUB)
            if pb.returncode != 0:
                log = (pb.stdout + "\n" + pb.stderr).strip()
                advertencias.append("BibTeX no resolvió la bibliografía: "
                                    + (log[:400] or "sin detalle"))
        else:
            advertencias.append("BibTeX no está instalado; se omite la bibliografía.")

        # Pasadas 2 y 3: índice, referencias cruzadas y \pageref{LastPage}
        subprocess.run(cmd_tex, timeout=180, **_SUB)
        proc = subprocess.run(cmd_tex, timeout=180, **_SUB)

        if not os.path.exists(pdf_path):
            return None, tex_path, ("LaTeX no generó PDF. Errores detectados:\n\n"
                                    + _errores_del_log(log_path))

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        if limpiar:
            limpiar_auxiliares(output_dir, nombre)

        msg = "OK" if not advertencias else "OK con advertencias: " + " | ".join(advertencias)
        return pdf_bytes, pdf_path, msg

    except subprocess.TimeoutExpired:
        return None, tex_path, "La compilación excedió el tiempo límite."
    except Exception as e:
        return None, tex_path, f"Error en Python al invocar LaTeX: {e}"
