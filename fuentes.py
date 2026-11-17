import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

from util import detectar_remoto, fecha_texto, flat, fold, recortar, salario, strip_html

HEADERS = {
    "User-Agent": "BuscadorEmpleoLocal/1.0",
    "Accept": "application/json, application/rss+xml, text/xml, */*",
}

WWR = [
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-design-jobs.rss",
    "https://weworkremotely.com/categories/remote-customer-support-jobs.rss",
    "https://weworkremotely.com/categories/remote-product-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
    "https://weworkremotely.com/categories/remote-management-and-finance-jobs.rss",
    "https://weworkremotely.com/categories/remote-sales-and-marketing-jobs.rss",
]


def traer(url, timeout=25, data=None, headers=None):
    pedido = urllib.request.Request(url, data=data, headers=headers or HEADERS)
    with urllib.request.urlopen(pedido, timeout=timeout) as respuesta:
        return respuesta.read()


def traer_json(url, timeout=25, data=None, headers=None):
    return json.loads(traer(url, timeout, data, headers).decode("utf-8", "replace"))


def limpiar_error(error):
    texto = str(error)
    texto = re.sub(r"(app_key|app_id|api_key|key)=[^&\s]+", r"\1=***", texto, flags=re.I)
    texto = re.sub(r"jooble\.org/api/[^\s\"']+", "jooble.org/api/***", texto, flags=re.I)
    texto = re.sub(r"key=[A-Za-z0-9_\-]+", "key=***", texto)
    return texto[:220]


def _aviso(titulo, empresa, fuente, url, lugar, descripcion, remoto, fecha="", pago=""):
    titulo = (titulo or "").strip()
    url = (url or "").strip()
    if not titulo or not url:
        return None
    texto = recortar(strip_html(descripcion), 3500)
    return {
        "titulo": titulo[:180],
        "empresa": (empresa or "").strip()[:120],
        "fuente": fuente,
        "url": url,
        "lugar": (lugar or "").strip()[:120],
        "remoto": remoto if isinstance(remoto, bool) else detectar_remoto(f"{lugar}\n{texto}", remoto),
        "fecha": fecha_texto(fecha),
        "descripcion": texto,
        "salario": (pago or "").strip()[:80],
    }


def fuente_remotive():
    data = traer_json("https://remotive.com/api/remote-jobs?limit=100")
    trabajos = []
    for item in data.get("jobs") or []:
        aviso = _aviso(
            item.get("title"),
            item.get("company_name"),
            "Remotive",
            item.get("url"),
            item.get("candidate_required_location") or "Remoto",
            item.get("description"),
            True,
            item.get("publication_date"),
            item.get("salary") or "",
        )
        if aviso:
            trabajos.append(aviso)
    return trabajos


def fuente_remoteok():
    data = traer_json("https://remoteok.com/api", timeout=30)
    trabajos = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict) or not item.get("position"):
            continue
        pago = salario(item.get("salary_min"), item.get("salary_max"))
        aviso = _aviso(
            item.get("position"),
            item.get("company"),
            "Remote OK",
            item.get("apply_url") or item.get("url"),
            item.get("location") or "Remoto",
            item.get("description"),
            True,
            item.get("date") or item.get("epoch"),
            pago,
        )
        if aviso:
            trabajos.append(aviso)
    return trabajos


def fuente_arbeitnow():
    data = traer_json("https://www.arbeitnow.com/api/job-board-api?page=1", timeout=45)
    trabajos = []
    for item in data.get("data") or []:
        aviso = _aviso(
            item.get("title"),
            item.get("company_name"),
            "Arbeitnow",
            item.get("url"),
            item.get("location"),
            item.get("description"),
            item.get("remote") if isinstance(item.get("remote"), bool) else None,
            item.get("created_at"),
        )
        if aviso:
            trabajos.append(aviso)
    return trabajos


def fuente_jobicy():
    data = traer_json("https://jobicy.com/api/v2/remote-jobs?count=50")
    trabajos = []
    for item in data.get("jobs") or []:
        pago = salario(item.get("salaryMin"), item.get("salaryMax"), item.get("salaryCurrency") or "")
        aviso = _aviso(
            item.get("jobTitle"),
            item.get("companyName"),
            "Jobicy",
            item.get("url"),
            item.get("jobGeo") or "Remoto",
            item.get("jobDescription") or item.get("jobExcerpt"),
            True,
            item.get("pubDate"),
            pago,
        )
        if aviso:
            trabajos.append(aviso)
    return trabajos


def fuente_himalayas():
    data = traer_json("https://himalayas.app/jobs/api?limit=80")
    trabajos = []
    for item in data.get("jobs") or []:
        pago = salario(item.get("minSalary"), item.get("maxSalary"), item.get("currency") or "")
        lugar = flat(item.get("locationRestrictions")) or "Remoto"
        aviso = _aviso(
            item.get("title"),
            item.get("companyName"),
            "Himalayas",
            item.get("applicationLink") or item.get("guid"),
            lugar,
            item.get("description") or item.get("excerpt"),
            True,
            item.get("pubDate"),
            pago,
        )
        if aviso:
            trabajos.append(aviso)
    return trabajos


def fuente_nomads():
    data = traer_json("https://www.workingnomads.com/api/exposed_jobs")
    trabajos = []
    if isinstance(data, dict):
        data = data.get("jobs") or data.get("data") or []
    for item in data or []:
        aviso = _aviso(
            item.get("title"),
            item.get("company_name"),
            "Working Nomads",
            item.get("url"),
            item.get("location") or "Remoto",
            item.get("description"),
            True,
            item.get("pub_date"),
        )
        if aviso:
            trabajos.append(aviso)
    return trabajos


def terminos_busqueda(consulta):
    partes = [p.strip() for p in re.split(r"[\s,/|]+", consulta or "") if p.strip()]
    salida = []
    for parte in partes:
        if len(parte) < 3 and "#" not in parte and "+" not in parte:
            continue
        if parte.lower() in [item.lower() for item in salida]:
            continue
        salida.append(parte)
    return salida[:3]


def fuente_getonbrd(consulta):
    terminos = terminos_busqueda(consulta)
    if not terminos:
        return []
    trabajos = []
    vistos = set()
    for termino in terminos:
        url = "https://www.getonbrd.com/api/v0/search/jobs?" + urllib.parse.urlencode(
            {"query": termino, "per_page": 25, "page": 1}
        )
        data = traer_json(url)
        for item in data.get("data") or []:
            attrs = item.get("attributes") or {}
            link = (item.get("links") or {}).get("public_url")
            if not link or link in vistos:
                continue
            vistos.add(link)
            lugar = ", ".join(
                x
                for x in (
                    flat(attrs.get("location_cities")),
                    flat(attrs.get("countries")),
                    flat(attrs.get("remote_zone")),
                )
                if x
            )
            descripcion = "\n".join(
                x
                for x in (
                    flat(attrs.get("description_headline")),
                    flat(attrs.get("description")),
                    flat(attrs.get("functions")),
                    flat(attrs.get("desirable")),
                )
                if x
            )
            remoto = attrs.get("remote") if isinstance(attrs.get("remote"), bool) else None
            empresa = flat(attrs.get("company"))
            if re.search(r"\bcompany\b", empresa, re.I) and re.search(r"\d", empresa):
                empresa = ""
            aviso = _aviso(
                attrs.get("title"),
                empresa,
                "Get on Board",
                link,
                lugar,
                descripcion,
                remoto,
                attrs.get("published_at"),
                salario(attrs.get("min_salary"), attrs.get("max_salary")),
            )
            if aviso:
                trabajos.append(aviso)
        if len(trabajos) >= 40:
            break
    return trabajos


def _historia_who_is_hiring():
    url = "https://hn.algolia.com/api/v1/search_by_date?" + urllib.parse.urlencode(
        {"tags": "story,author_whoishiring", "hitsPerPage": 6}
    )
    data = traer_json(url)
    for hit in data.get("hits") or []:
        titulo = (hit.get("title") or "").lower()
        if "who is hiring" in titulo and "who wants" not in titulo:
            return str(hit.get("objectID"))
    return ""


def fuente_hn(consulta):
    terminos = terminos_busqueda(consulta)
    if not terminos:
        return []
    historia = _historia_who_is_hiring()
    if not historia:
        return []
    trabajos = []
    vistos = set()
    for termino in terminos:
        url = "https://hn.algolia.com/api/v1/search?" + urllib.parse.urlencode(
            {"tags": f"comment,story_{historia}", "hitsPerPage": 30, "query": termino}
        )
        data = traer_json(url)
        for hit in data.get("hits") or []:
            if str(hit.get("parent_id")) != historia:
                continue
            ident = str(hit.get("objectID"))
            if ident in vistos:
                continue
            texto = strip_html(hit.get("comment_text") or "")
            if len(texto) < 80:
                continue
            vistos.add(ident)
            primera = texto.split("\n", 1)[0]
            partes_linea = [p.strip() for p in primera.split("|") if p.strip()]
            empresa = partes_linea[0][:80] if partes_linea else ""
            titulo = partes_linea[1][:160] if len(partes_linea) > 1 else primera[:160]
            lugar = partes_linea[2][:80] if len(partes_linea) > 2 else ""
            aviso = _aviso(
                titulo,
                empresa,
                "Hacker News",
                f"https://news.ycombinator.com/item?id={ident}",
                lugar,
                texto,
                detectar_remoto(texto),
                hit.get("created_at"),
            )
            if aviso:
                trabajos.append(aviso)
        if len(trabajos) >= 40:
            break
    return trabajos


def fuente_wwr():
    trabajos = []
    vistos = set()
    fallos = 0
    for url in WWR:
        try:
            raw = traer(url, timeout=20)
        except (urllib.error.URLError, TimeoutError, OSError):
            fallos += 1
            continue
        inicio = raw.lstrip()[:80].lower()
        if b"<rss" not in inicio and b"<?xml" not in inicio:
            fallos += 1
            continue
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            fallos += 1
            continue
        for item in root.iter("item"):
            titulo_crudo = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not link or link in vistos:
                continue
            vistos.add(link)
            if ":" in titulo_crudo:
                empresa, titulo = titulo_crudo.split(":", 1)
            else:
                empresa, titulo = "", titulo_crudo
            aviso = _aviso(
                titulo,
                empresa,
                "We Work Remotely",
                link,
                "Remoto",
                item.findtext("description") or "",
                True,
                item.findtext("pubDate") or "",
            )
            if aviso:
                trabajos.append(aviso)
    if not trabajos and fallos:
        raise RuntimeError("We Work Remotely no respondió.")
    return trabajos


def _pais_adzuna(config, lugar):
    pais = (config.get("adzuna_pais") or "ar").strip().lower()
    if re.fullmatch(r"[a-z]{2}", pais):
        return pais
    return "ar"


def fuente_adzuna(consulta, config, lugar):
    app_id = (config.get("adzuna_app_id") or "").strip()
    app_key = (config.get("adzuna_app_key") or "").strip()
    terminos = terminos_busqueda(consulta)
    if not app_id or not app_key or not terminos:
        return []
    pais = _pais_adzuna(config, lugar)
    if pais == "ar":
        raise RuntimeError(
            "Adzuna no publica avisos de Argentina. La clave quedó guardada. Si cambiás el país a Brasil, Estados Unidos o Reino Unido, entra en la búsqueda."
        )
    trabajos = []
    vistos = set()
    for termino in terminos:
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": 20,
            "what": _consulta_online(termino, pais),
            "content-type": "application/json",
        }
        if lugar and lugar.strip().lower() not in {"argentina", "remoto", "remote"}:
            params["where"] = lugar.strip()
        url = (
            f"https://api.adzuna.com/v1/api/jobs/{_pais_adzuna(config, lugar)}/search/1?"
            + urllib.parse.urlencode(params)
        )
        data = traer_json(url)
        for item in data.get("results") or []:
            company = item.get("company") or {}
            location = item.get("location") or {}
            aviso = _aviso(
                item.get("title"),
                company.get("display_name") if isinstance(company, dict) else flat(company),
                "Adzuna",
                item.get("redirect_url"),
                location.get("display_name") if isinstance(location, dict) else flat(location),
                item.get("description"),
                None,
                item.get("created"),
                salario(item.get("salary_min"), item.get("salary_max")),
            )
            if aviso and aviso["url"] not in vistos:
                vistos.add(aviso["url"])
                trabajos.append(aviso)
    return trabajos


def fuente_jooble(consulta, config, lugar):
    clave = (config.get("jooble_key") or "").strip()
    terminos = terminos_busqueda(consulta)
    if not clave or not terminos:
        return []
    trabajos = []
    vistos = set()
    for termino in terminos:
        url = "https://ar.jooble.org/api/" + urllib.parse.quote(clave)
        cuerpo = json.dumps(
            {"keywords": termino, "location": (lugar or "Argentina").strip() or "Argentina", "page": "1"}
        ).encode("utf-8")
        data = traer_json(
            url,
            data=cuerpo,
            headers={**HEADERS, "Content-Type": "application/json"},
        )
        for item in data.get("jobs") or []:
            aviso = _aviso(
                item.get("title"),
                item.get("company"),
                "Jooble",
                item.get("link"),
                item.get("location"),
                item.get("snippet"),
                None,
                item.get("updated"),
                item.get("salary") or "",
            )
            if aviso and aviso["url"] not in vistos:
                vistos.add(aviso["url"])
                trabajos.append(aviso)
    return trabajos


FUENTES_ONLINE = {
    "Remotive",
    "Remote OK",
    "Jobicy",
    "Himalayas",
    "Working Nomads",
    "We Work Remotely",
}

LUGARES_ARGENTINA = (
    "argentina",
    "buenos aires",
    "caba",
    "capital federal",
    "gba",
    "cordoba",
    "rosario",
    "mendoza",
    "la plata",
    "mar del plata",
    "tucuman",
    "salta",
    "neuquen",
    "pilar",
)


def _consulta_online(termino, pais):
    palabra = "remoto" if pais in {"br", "es", "mx", "cl", "co"} else "remote"
    plano = (termino or "").lower()
    if palabra in plano or "remote" in plano or "remoto" in plano:
        return termino
    return f"{termino} {palabra}"


def _es_argentina(lugar):
    plano = fold(lugar or "")
    return any(marca in plano for marca in LUGARES_ARGENTINA)


def _conservar(aviso):
    if aviso.get("fuente") in FUENTES_ONLINE or aviso.get("remoto") is True:
        return True
    if _es_argentina(aviso.get("lugar")):
        return True
    return False


def buscar_fuentes(consulta, config, lugar, solo_remotos):
    config = config or {}
    tareas = [
        ("Remotive", fuente_remotive),
        ("Remote OK", fuente_remoteok),
        ("Arbeitnow", fuente_arbeitnow),
        ("Jobicy", fuente_jobicy),
        ("Himalayas", fuente_himalayas),
        ("Working Nomads", fuente_nomads),
        ("Get on Board", lambda: fuente_getonbrd(consulta)),
        ("Hacker News", lambda: fuente_hn(consulta)),
        ("We Work Remotely", fuente_wwr),
    ]
    if (config.get("adzuna_app_id") or "").strip() and (config.get("adzuna_app_key") or "").strip():
        tareas.append(("Adzuna", lambda: fuente_adzuna(consulta, config, lugar)))
    if (config.get("jooble_key") or "").strip():
        tareas.append(("Jooble", lambda: fuente_jooble(consulta, config, lugar)))

    reportes = []
    trabajos = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futuros = {pool.submit(fn): nombre for nombre, fn in tareas}
        for futuro in as_completed(futuros):
            nombre = futuros[futuro]
            try:
                lote = futuro.result() or []
            except Exception as exc:
                reportes.append({"nombre": nombre, "cantidad": 0, "error": limpiar_error(exc)})
                continue
            lote = [item for item in lote if _conservar(item)]
            if solo_remotos:
                lote = [item for item in lote if item.get("remoto") is not False]
            reportes.append({"nombre": nombre, "cantidad": len(lote), "error": ""})
            trabajos.extend(lote)

    orden_nombres = [nombre for nombre, _ in tareas]
    reportes.sort(key=lambda r: orden_nombres.index(r["nombre"]) if r["nombre"] in orden_nombres else 99)
    return trabajos, reportes
