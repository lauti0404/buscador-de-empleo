import io
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

PERMITIDAS = {".pdf", ".docx", ".txt", ".text", ".md", ".png", ".jpg", ".jpeg", ".webp"}
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def leer_archivo(nombre, datos):
    ext = Path(nombre or "").suffix.lower()
    if ext not in PERMITIDAS:
        raise ValueError("Usá un PDF, un DOCX, un TXT o una foto del CV.")
    if len(datos) > 8_000_000:
        raise ValueError("El archivo pesa más de 8 MB.")
    if ext in {".txt", ".text", ".md"}:
        return _plano(datos), []
    if ext == ".docx":
        return _docx(datos), []
    if ext == ".pdf":
        texto, imagenes = _pdf(datos)
        if len(texto.strip()) >= 80:
            return texto, []
        return texto, imagenes
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }[ext]
    return "", [(datos, mime)]


def _plano(datos):
    for codec in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            texto = datos.decode(codec)
            break
        except UnicodeDecodeError:
            texto = ""
    return _limpiar(texto)


def _docx(datos):
    try:
        paquete = zipfile.ZipFile(io.BytesIO(datos))
        xml = paquete.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ValueError("Ese DOCX no se puede abrir.") from exc
    raiz = ET.fromstring(xml)
    lineas = []
    for parrafo in raiz.iter(_W + "p"):
        partes = []
        for nodo in parrafo.iter(_W + "t"):
            if nodo.text:
                partes.append(nodo.text)
        linea = _limpiar("".join(partes))
        if linea:
            lineas.append(linea)
    return "\n".join(lineas)


def _pdf(datos):
    try:
        import pymupdf as fitz
    except ImportError as exc:
        raise ValueError("Falta el lector de PDF. Cerrá el programa y volvé a ejecutar instalar.bat.") from exc
    try:
        doc = fitz.open(stream=datos, filetype="pdf")
    except Exception as exc:
        raise ValueError("Ese PDF no se puede abrir.") from exc
    textos = []
    imagenes = []
    for indice, pagina in enumerate(doc):
        textos.append(pagina.get_text("text") or "")
        if indice < 4:
            mapa = pagina.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            imagenes.append((mapa.tobytes("jpeg", jpg_quality=72), "image/jpeg"))
    doc.close()
    return _limpiar("\n".join(textos)), imagenes


def _limpiar(texto):
    texto = (texto or "").replace("\x00", " ")
    texto = re.sub(r"[ \t]+\n", "\n", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()
