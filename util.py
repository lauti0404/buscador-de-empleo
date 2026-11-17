import html
import re
from datetime import datetime, timezone


def fold(texto):
    texto = (texto or "").lower()
    tabla = str.maketrans(
        "áéíóúüñàèìòùâêîôûäëïöõç",
        "aeiouunaeiouaeiouaeiooc",
    )
    return texto.translate(tabla)


def strip_html(texto):
    texto = texto or ""
    texto = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", texto)
    texto = re.sub(r"(?i)<br\s*/?>", "\n", texto)
    texto = re.sub(r"(?i)</p>", "\n", texto)
    texto = re.sub(r"(?i)<li[^>]*>", "\n- ", texto)
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = html.unescape(texto)
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n[ \t]+", "\n", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def contiene(plano, frase):
    if not frase:
        return False
    patron = r"(?<![a-z0-9])" + re.escape(frase) + r"(?![a-z0-9])"
    return re.search(patron, plano) is not None


def flat(valor):
    if valor is None:
        return ""
    if isinstance(valor, str):
        return strip_html(valor)
    if isinstance(valor, (int, float)):
        return str(valor)
    if isinstance(valor, list):
        return ", ".join(x for x in (flat(v) for v in valor) if x)
    if isinstance(valor, dict):
        for clave in ("name", "display_name", "title", "label", "en", "es"):
            if isinstance(valor.get(clave), str):
                return strip_html(valor[clave])
        return " ".join(x for x in (flat(v) for v in valor.values()) if x)
    return ""


def fecha_texto(valor):
    if valor is None or valor == "":
        return ""
    if isinstance(valor, (int, float)) or (isinstance(valor, str) and str(valor).isdigit()):
        ts = int(float(valor))
        if ts > 10_000_000_000:
            ts //= 1000
        try:
            return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return ""
    return str(valor)[:10]


def recortar(texto, limite=3500):
    texto = texto or ""
    if len(texto) <= limite:
        return texto
    return texto[:limite].rsplit(" ", 1)[0] + "…"


def detectar_remoto(texto, bandera=None):
    plano = fold(texto)
    remoto = any(
        p in plano
        for p in (
            "remote",
            "remoto",
            "teletrabajo",
            "trabajo remoto",
            "home office",
            "work from home",
            "anywhere",
            "worldwide",
            "distributed",
            "hibrido",
            "hybrid",
        )
    )
    presencial = any(
        p in plano
        for p in ("onsite", "on-site", "on site", "in office", "presencial", "in-office")
    )
    if remoto:
        return True
    if bandera is True:
        return True
    if bandera is False or presencial:
        return False
    return None


def salario(minimo, maximo, moneda=""):
    def limpio(valor):
        if valor is None or valor == "" or valor == 0:
            return ""
        if isinstance(valor, float) and valor.is_integer():
            valor = int(valor)
        return str(valor)

    a = limpio(minimo)
    b = limpio(maximo)
    moneda = (moneda or "").strip()
    if a and b and a != b:
        return f"{moneda} {a} - {b}".strip()
    if a or b:
        return f"{moneda} {a or b}".strip()
    return ""
