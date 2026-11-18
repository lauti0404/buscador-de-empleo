import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from util import contiene, fold, recortar, strip_html

# Cada grupo es la misma habilidad dicha de otra forma.
# El primero es el nombre base. No se agregan oficios que el CV no tenga.
GRUPOS = [
    ["desarrollador", "developer", "programador", "programmer"],
    ["full stack", "fullstack", "full-stack"],
    ["frontend", "front-end", "front end"],
    ["backend", "back-end", "back end"],
    ["react native", "react-native"],
    ["nestjs", "nest.js"],
    ["ingles", "english"],
    ["espanol", "spanish"],
    ["portugues", "portuguese"],
    ["ventas", "sales"],
    ["marketing", "mercadotecnia"],
    ["diseño", "design"],
    ["diseñador", "designer"],
    ["atencion al cliente", "customer service", "customer support", "servicio al cliente"],
    ["soporte tecnico", "technical support", "help desk"],
    ["recursos humanos", "human resources"],
    ["contabilidad", "accounting"],
    ["finanzas", "finance"],
    ["logistica", "logistics"],
    ["c#", "csharp", "c sharp"],
    ["c++", "cpp"],
    ["node.js", "nodejs", "node"],
    ["react", "react.js", "reactjs"],
    ["vue", "vue.js", "vuejs"],
    ["angular", "angularjs"],
    ["next.js", "nextjs"],
    ["javascript", "js"],
    ["typescript", "ts"],
    ["videojuegos", "game development", "video games"],
    ["analisis de datos", "data analysis", "data analyst"],
    ["ciencia de datos", "data science"],
    ["machine learning", "aprendizaje automatico"],
    ["power bi", "powerbi"],
    ["project manager", "gestor de proyectos", "project management"],
    ["product manager", "product management"],
    ["community manager", "social media"],
    ["copywriting", "redaccion"],
    ["seo", "posicionamiento web"],
    ["google ads", "adwords"],
    ["meta ads", "facebook ads"],
]

SUELTAS = [
    "python", "java", "php", "ruby", "kotlin", "swift", "rust", "golang", "scala",
    "html", "css", "sql", "django", "flask", "spring", ".net", "asp.net", "laravel",
    "unity", "unreal", "godot", "git", "github", "docker", "kubernetes", "aws",
    "azure", "gcp", "linux", "figma", "photoshop", "illustrator", "indesign",
    "blender", "premiere", "after effects", "canva", "excel", "powerpoint",
    "outlook", "tableau", "sap", "salesforce", "hubspot", "jira", "notion",
    "scrum", "agile", "qa", "testing", "cybersecurity", "ciberseguridad",
    "autocad", "solidworks", "wordpress", "shopify", "mysql", "postgresql",
    "mongodb", "firebase", "android", "ios", "flutter", "supabase", "prisma",
    "illustrator", "lightroom", "audition", "davinci", "resolve",
    "traduccion", "docencia", "profesor", "enfermeria", "recepcionista",
    "administrativo", "data entry", "facturacion", "payroll", "nomina",
    "cocina", "barista", "chofer", "almacen", "deposito", "compras",
    "negociacion", "crm", "erp", "sap", "abap", "figma", "sketch",
    "tailwind", "bootstrap", "graphql", "linux", "bash",
    "powershell", "azure devops", "ci/cd", "terraform", "ansible",
    "pandas", "numpy", "tensorflow", "pytorch", "spark", "hadoop",
    "ingles", "frances", "aleman", "italiano",
    "photoshop", "maya", "3ds max", "zbrush", "substance painter",
    "atencion al publico", "telemarketing", "call center", "cobranzas",
    "seleccion de personal", "reclutamiento", "onboarding",
    "contable", "impuestos", "auditoria", "balances",
    "ventas b2b", "ventas b2c", "retail", "ecommerce",
    "ux", "ui", "ux/ui", "investigacion de usuarios",
    "cisco", "mikrotik",
]

GENERICOS = {
    "comunicacion",
    "trabajo en equipo",
    "liderazgo",
}

# Nombrar el oficio no alcanza: casi todo aviso de sistemas dice "developer".
ROLES = {
    "desarrollador",
    "ventas",
    "marketing",
    "diseño",
    "diseñador",
    "profesor",
    "administrativo",
    "finanzas",
    "logistica",
    "project manager",
    "product manager",
    "community manager",
}

# Sirven como dato, pero no alcanzan para marcar un aviso como apto.
# Si la persona hace el lado completo, un aviso solo de front o solo de back también le sirve.
IMPLICA = {
    "full stack": ["frontend", "backend"],
    "react": ["frontend"],
    "react native": ["frontend"],
    "nestjs": ["backend"],
    "node.js": ["backend"],
}

UBICUAS = {
    "git",
    "github",
    "jira",
    "excel",
    "ingles",
    "espanol",
    "powerpoint",
    "outlook",
    "notion",
    "scrum",
    "agile",
}

GRUPOS.extend(
    [
        ["comunicacion", "communication"],
        ["trabajo en equipo", "teamwork"],
        ["liderazgo", "leadership"],
    ]
)

RELLENO = {
    "para", "como", "con", "sin", "por", "los", "las", "del", "una", "uno",
    "que", "the", "and", "with", "from", "this", "that", "your", "you", "our",
    "are", "was", "were", "will", "have", "has", "had", "not", "but", "its",
    "job", "role", "work", "team", "years", "year", "experience", "skills",
    "skill", "ability", "including", "strong", "plus", "using", "used",
    "looking", "required", "requirements", "responsibilities", "responsibility",
    "about", "their", "they", "who", "what", "when", "where", "into", "over",
    "more", "other", "than", "then", "also", "can", "all", "any", "new",
    "experiencia", "anos", "año", "equipo", "trabajo", "empresa", "puesto",
    "requisitos", "responsabilidades", "buscamos", "ofrecemos", "capacidad",
    "habilidades", "conocimiento", "conocimientos", "manejo", "buena", "buen",
    "alto", "alta", "nivel", "area", "dentro", "sobre", "entre", "hasta",
    "desde", "hacia", "porque", "ademas", "mediante", "través", "traves",
    "applicant", "candidates", "candidate", "position", "company", "we",
    "join", "opportunity", "full", "time", "part", "based", "across",
    "well", "etc", "via", "per", "day", "week", "month", "remote", "remoto",
    "senior", "junior", "semi", "mid", "level", "staff",
}


def formas_por_canon():
    mapa = {}
    for formas in GRUPOS:
        mapa[fold(formas[0])] = formas
    return mapa


FORMAS = formas_por_canon()


def _compilar_patrones():
    patrones = []
    vistos = set()
    grupos = sorted(GRUPOS, key=lambda formas: max(len(f) for f in formas), reverse=True)
    for formas in grupos:
        canon = fold(formas[0])
        if not canon or canon in vistos:
            continue
        vistos.add(canon)
        opciones = sorted({fold(forma) for forma in formas if fold(forma)}, key=len, reverse=True)
        partes = [r"(?<![a-z0-9])" + re.escape(opcion) + r"(?![a-z0-9])" for opcion in opciones]
        patrones.append((canon, re.compile("|".join(partes))))
    for nombre in sorted(set(SUELTAS), key=len, reverse=True):
        canon = fold(nombre)
        if not canon or canon in vistos:
            continue
        vistos.add(canon)
        patrones.append((canon, re.compile(r"(?<![a-z0-9])" + re.escape(canon) + r"(?![a-z0-9])")))
    return patrones


PATRONES = _compilar_patrones()


def tokens(texto):
    plano = fold(strip_html(texto))
    return [
        t
        for t in re.findall(r"[a-z0-9#+./-]{2,}", plano)
        if t not in RELLENO and not t.isdigit() and len(t) > 2
    ]


def ocurrencias(texto):
    plano = fold(strip_html(texto))
    halladas = []
    for canon, patron in PATRONES:
        halladas.extend((canon, match.start()) for match in patron.finditer(plano))
    return plano, halladas


def extraer_habilidades(texto):
    _, halladas = ocurrencias(texto)
    vistos = []
    for canon, _pos in halladas:
        if canon not in vistos:
            vistos.append(canon)
    return vistos


def _recuperar_forma(frase, texto):
    if not texto or not frase:
        return ""
    mapa = {
        "a": "[aáàä]",
        "e": "[eéèë]",
        "i": "[iíìï]",
        "o": "[oóòö]",
        "u": "[uúùü]",
        "n": "[nñ]",
    }
    partes = [mapa.get(ch, re.escape(ch)) for ch in fold(frase)]
    patron = r"(?<![A-Za-z0-9])" + "".join(partes) + r"(?![A-Za-z0-9])"
    hallado = re.search(patron, texto, flags=re.IGNORECASE)
    return hallado.group(0) if hallado else ""


def forma_visible(canon, texto_preferido, texto_respaldo):
    formas = FORMAS.get(canon, [canon])
    for base in (texto_preferido, texto_respaldo):
        for forma in sorted(formas, key=len, reverse=True):
            visible = _recuperar_forma(forma, base)
            if visible:
                return visible
    return formas[0]


def ampliar(habilidades):
    salida = list(habilidades)
    vistos = set(salida)
    for habilidad in habilidades:
        for destino in IMPLICA.get(habilidad, []):
            if destino not in vistos:
                vistos.add(destino)
                salida.append(destino)
    return salida


def armar_consulta(cv, escrita):
    escrita = (escrita or "").strip()
    if escrita:
        return escrita[:120]
    habilidades = extraer_habilidades(cv[:3000])
    fuertes = [h for h in habilidades if h not in GENERICOS and h not in ROLES and h not in UBICUAS]
    habilidades = fuertes or [h for h in habilidades if h not in GENERICOS]
    if habilidades:
        return " ".join(forma_visible(h, cv, cv) for h in habilidades[:3])
    palabras = []
    for token in tokens(cv[:900]):
        if len(token) > 4 and token not in palabras:
            palabras.append(token)
        if len(palabras) == 3:
            break
    return " ".join(palabras)


def _ocurrencia_util(plano, canon, pos):
    if canon == "unity" and plano.startswith("unity catalog", pos):
        return False
    if canon == "videojuegos":
        ventana = plano[max(0, pos - 16) : pos + 18]
        if "play video games" in ventana or "playing video games" in ventana:
            return False
    return True


def puntuar(cv, aviso):
    habilidades_cv = ampliar(extraer_habilidades(cv))
    titulo = aviso.get("titulo") or ""
    descripcion = aviso.get("descripcion") or ""
    titulo_plano, ocs_titulo = ocurrencias(titulo)
    plano, ocs_desc = ocurrencias(descripcion)
    ocs_titulo = [(canon, pos) for canon, pos in ocs_titulo if _ocurrencia_util(titulo_plano, canon, pos)]
    ocs_desc = [(canon, pos) for canon, pos in ocs_desc if _ocurrencia_util(plano, canon, pos)]
    habilidades_aviso = []
    for canon, _pos in ocs_titulo + ocs_desc:
        if canon not in habilidades_aviso:
            habilidades_aviso.append(canon)
    set_cv = set(habilidades_cv)
    coinciden = []
    faltan = []
    for habilidad in habilidades_aviso:
        if habilidad in set_cv:
            if habilidad not in coinciden:
                coinciden.append(habilidad)
        elif habilidad not in GENERICOS and habilidad not in faltan:
            faltan.append(habilidad)

    titulo_hab = {canon for canon, _pos in ocs_titulo}
    cortes = [0]
    cortes.extend(match.end() for match in re.finditer(r"[\n.;]+", plano))
    cortes.append(len(plano) + 1)

    def span_de(pos):
        for indice in range(len(cortes) - 1):
            if cortes[indice] <= pos < cortes[indice + 1]:
                return indice
        return -1

    por_span = {}
    for canon, pos in ocs_desc:
        por_span.setdefault(span_de(pos), set()).add(canon)
    ensalada = {indice for indice, skills in por_span.items() if len(skills) >= 6}
    en_frase_corta = set()
    for canon, pos in ocs_desc:
        indice = span_de(pos)
        if indice in ensalada or indice < 0:
            continue
        if cortes[indice + 1] - cortes[indice] <= 320:
            en_frase_corta.add(canon)
    repeticiones = {}
    for canon, pos in ocs_desc:
        if span_de(pos) not in ensalada:
            repeticiones[canon] = repeticiones.get(canon, 0) + 1

    def esta_en_titulo(habilidad):
        return habilidad in titulo_hab

    def abre(habilidad):
        if habilidad in GENERICOS or habilidad in ROLES:
            return False
        if habilidad in UBICUAS and not esta_en_titulo(habilidad):
            return False
        if esta_en_titulo(habilidad):
            return True
        if repeticiones.get(habilidad, 0) >= 2:
            return True
        if habilidad in en_frase_corta:
            return True
        return False

    fuertes = [h for h in coinciden if abre(h)]
    puntos = 0
    for habilidad in coinciden:
        puntos += 16 if habilidad in fuertes else 3
    puntos = min(puntos, 64)

    cv_tokens = set(tokens(cv))
    for habilidad in habilidades_cv:
        for forma in FORMAS.get(habilidad, [habilidad]):
            cv_tokens.update(tokens(forma))
            cv_tokens.add(fold(forma))

    titulo_tokens = []
    for token in tokens(titulo):
        if token not in titulo_tokens:
            titulo_tokens.append(token)
    titulo_hits = [t for t in titulo_tokens if t in cv_tokens and t not in {"developer", "programmer", "designer", "engineer", "manager"}]
    puntos += min(20, len(titulo_hits) * 8)
    puntos = min(100, puntos)

    if len(fuertes) >= 2 or (len(fuertes) == 1 and esta_en_titulo(fuertes[0])):
        nivel = "encaja"
    elif fuertes:
        nivel = "posible"
    else:
        nivel = "flojo"

    motivos = []
    aviso_texto = titulo + "\n" + (aviso.get("descripcion") or "")
    if fuertes or coinciden:
        orden = fuertes + [h for h in coinciden if h not in fuertes]
        nombres = [forma_visible(h, aviso_texto, cv) for h in orden[:6]]
        motivos.append("Coincide con tu CV: " + ", ".join(nombres))
    if titulo_hits:
        motivos.append("El título comparte: " + ", ".join(titulo_hits[:5]))
    faltan_utiles = [h for h in faltan if h not in ROLES and h not in UBICUAS]
    if faltan_utiles:
        nombres = [forma_visible(h, aviso_texto, aviso_texto) for h in faltan_utiles[:5]]
        motivos.append("El aviso pide y tu CV no lo respalda: " + ", ".join(nombres))
    if not motivos:
        motivos.append("Poca coincidencia con lo que escribiste en el CV.")

    return {
        "puntaje": puntos,
        "nivel": nivel,
        "motivos": motivos[:3],
        "coinciden": fuertes + [h for h in coinciden if h not in fuertes],
        "faltan": faltan_utiles[:8],
    }


def _lineas(cv):
    salida = []
    for linea in cv.splitlines():
        limpia = linea.strip().strip("•-*–—\t ")
        if len(limpia) >= 8:
            salida.append(limpia)
    return salida


def _es_contacto(linea):
    plano = fold(linea)
    if "@" in linea or "http" in plano or "linkedin.com" in plano:
        return True
    digitos = re.sub(r"\D", "", linea)
    return 8 <= len(digitos) <= 15 and len(linea) <= 40


def _es_estudio(linea):
    plano = fold(linea)
    marcas = (
        "universidad", "facultad", "tecnicatura", "licenciatura", "ingenieria",
        "bachiller", "secundario", "bootcamp", "curso", "certificacion",
        "degree", "bachelor", "master", "university", "college", "diplomado",
        "terciario", "profesorado",
    )
    return any(m in plano for m in marcas)


def _datos_contacto(cv):
    lineas = _lineas(cv)
    nombre = ""
    if lineas:
        primera = lineas[0]
        palabras = primera.split()
        if (
            1 <= len(palabras) <= 6
            and "@" not in primera
            and "http" not in primera.lower()
            and len(re.sub(r"\D", "", primera)) < 2
            and len(primera) <= 48
        ):
            nombre = primera
    email = ""
    hallado = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", cv)
    if hallado:
        email = hallado.group(0)
    telefono = ""
    for posible in re.finditer(r"\+?\d[\d\s().-]{7,}\d", cv):
        digitos = re.sub(r"\D", "", posible.group())
        if 8 <= len(digitos) <= 15:
            telefono = posible.group().strip()
            break
    links = re.findall(r"https?://[^\s<>]+", cv)
    return nombre, email, telefono, links


def _viñetas(cv):
    estudios = []
    experiencia = []
    for linea in _lineas(cv):
        if _es_contacto(linea):
            continue
        if _es_estudio(linea):
            estudios.append(linea)
            continue
        experiencia.append(linea)
    if experiencia:
        primera = experiencia[0]
        palabras = primera.split()
        if len(palabras) <= 6 and len(primera) <= 48 and primera == _datos_contacto(cv)[0]:
            experiencia = experiencia[1:]
    return experiencia, estudios


def adaptar_local(cv, aviso):
    evaluacion = puntuar(cv, aviso)
    experiencia, estudios = _viñetas(cv)
    nombre, email, telefono, links = _datos_contacto(cv)
    aviso_texto = f"{aviso.get('titulo', '')}\n{aviso.get('descripcion', '')}"
    avisos_tokens = set(tokens(aviso_texto))

    def valor(linea):
        propios = set(tokens(linea))
        return len(propios & avisos_tokens)

    experiencia_ordenada = sorted(experiencia, key=valor, reverse=True)
    elegidas = [linea for linea in experiencia_ordenada if valor(linea) > 0]
    for linea in experiencia_ordenada:
        if linea not in elegidas:
            elegidas.append(linea)
        if len(elegidas) >= 3:
            break
    resumen_lineas = elegidas[:3]
    piezas = []
    for linea in resumen_lineas:
        linea = linea.strip()
        if linea and linea[-1] not in ".!?":
            linea += "."
        piezas.append(linea)
    resumen = " ".join(piezas).strip()
    if not resumen:
        resumen = recortar(strip_html(cv), 400)

    habilidades = [
        forma_visible(h, aviso_texto, cv)
        for h in evaluacion["coinciden"]
        if h not in GENERICOS
    ]
    ya = set(evaluacion["coinciden"])
    for habilidad in extraer_habilidades(cv):
        if habilidad in GENERICOS or habilidad in ya:
            continue
        habilidades.append(forma_visible(habilidad, cv, cv))
        ya.add(habilidad)
    habilidades = habilidades[:12]

    faltan_visibles = [
        forma_visible(h, aviso_texto, aviso_texto) for h in evaluacion["faltan"]
    ]
    return {
        "nombre": nombre,
        "email": email,
        "telefono": telefono,
        "links": links,
        "resumen": resumen,
        "habilidades": habilidades,
        "experiencia": experiencia_ordenada[:8],
        "estudios": estudios[:6],
        "faltan": faltan_visibles,
        "coinciden": habilidades,
        "puntaje": evaluacion["puntaje"],
        "nivel": evaluacion["nivel"],
    }


def _respaldado(fragmento, cv):
    if not fragmento or not fragmento.strip():
        return False
    for numero in re.findall(r"\d{3,}", fragmento):
        if numero not in cv:
            return False
    propias = set(extraer_habilidades(cv))
    for habilidad in extraer_habilidades(fragmento):
        if habilidad not in propias:
            return False
    significativos = [t for t in tokens(fragmento) if len(t) > 4]
    if not significativos:
        return True
    base = set(tokens(cv))
    return any(t in base for t in significativos)


def _filtrar_habilidades_ia(lista, cv, aviso_texto):
    propias = set(extraer_habilidades(cv))
    limpias = []
    for item in lista or []:
        texto = str(item).strip()
        if not texto:
            continue
        halladas = extraer_habilidades(texto)
        if halladas and any(h not in propias for h in halladas):
            continue
        if halladas:
            limpias.append(forma_visible(halladas[0], aviso_texto, cv))
        elif _respaldado(texto, cv):
            limpias.append(texto)
    return limpias


def _gemini(partes, clave, modelo, json_mode=True):
    if isinstance(partes, str):
        partes = [{"text": partes}]
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + urllib.parse.quote(modelo)
        + ":generateContent?key="
        + urllib.parse.quote(clave)
    )
    config = {"temperature": 0.2}
    if json_mode:
        config["responseMimeType"] = "application/json"
    cuerpo = {
        "contents": [{"parts": partes}],
        "generationConfig": config,
    }
    data = json.dumps(cuerpo).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        respuesta = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 401, 403):
            raise RuntimeError("Gemini rechazó la clave. Revisala y volvé a guardarla.") from exc
        if exc.code == 429:
            raise RuntimeError("Gemini llegó al límite de uso. Probá de nuevo más tarde.") from exc
        raise RuntimeError(f"Gemini no pudo responder ({exc.code}).") from exc
    with respuesta:
        payload = json.loads(respuesta.read().decode("utf-8", "replace"))
    candidatos = payload.get("candidates") or []
    if not candidatos:
        raise RuntimeError("Gemini no devolvió texto.")
    salida = candidatos[0].get("content", {}).get("parts") or []
    return "\n".join(p.get("text", "") for p in salida)


def transcribir_cv(imagenes, clave, modelo):
    partes = [{
        "text": (
            "Transcribí el CV de las imágenes.\n"
            "Copiá únicamente el texto que se lee y conservá los saltos de línea.\n"
            "No corrijas, no completes y no inventes nombre, fechas, estudios, empleos ni herramientas.\n"
            "Si una palabra no se lee, omitila.\n"
            "Respondé solo el texto del CV."
        )
    }]
    for blob, mime in imagenes[:4]:
        partes.append({
            "inlineData": {
                "mimeType": mime,
                "data": base64.b64encode(blob).decode("ascii"),
            }
        })
    modelos = [modelo or "gemini-2.5-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
    vistos = []
    ultimo = None
    texto = ""
    for nombre in modelos:
        if nombre in vistos:
            continue
        vistos.append(nombre)
        try:
            texto = _gemini(partes, clave, nombre, json_mode=False).strip()
            break
        except Exception as exc:
            ultimo = exc
            texto = ""
    texto = re.sub(r"^```[a-z]*", "", texto).strip()
    texto = re.sub(r"```$", "", texto).strip()
    if len(texto) < 40:
        raise ultimo or RuntimeError("Gemini no pudo leer el archivo.")
    return texto


def _leer_json_ia(texto):
    texto = (texto or "").strip()
    texto = re.sub(r"^```(?:json)?", "", texto).strip()
    texto = re.sub(r"```$", "", texto).strip()
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio < 0 or fin < inicio:
        raise ValueError("La IA no devolvió JSON.")
    return json.loads(texto[inicio : fin + 1])


def mejorar_con_ia(cv, aviso, base, clave, modelo):
    aviso_texto = recortar(
        f"{aviso.get('titulo', '')}\n{aviso.get('empresa', '')}\n{aviso.get('descripcion', '')}",
        4000,
    )
    prompt = f"""Redactá un CV nuevo, en texto plano, para que un filtro ATS lo lea. Respondé solo JSON.

Normas del CV:
- Texto simple, sin tablas, columnas, íconos, gráficos ni encabezados de diseño.
- Oraciones cortas. Una idea por viñeta.
- El resumen nombra el puesto del aviso solo con capacidades que el CV original ya demuestra.
- En habilidades, listá las herramientas del CV que también aparecen en el aviso, y después el resto de las que el CV ya nombra.
- En experiencia, reescribí los hechos del CV con las mismas palabras del aviso cuando describen algo que ya hizo.
- Usá únicamente hechos que ya están en el CV.
- No inventes empleos, empresas, fechas, estudios, idiomas, cargos, logros ni herramientas.
- No agregues una habilidad del aviso si el CV no la menciona, ni un equivalente que no esté escrito.
- No incluyas contacto ni estudios: se agregan aparte.
- Español.

CV ORIGINAL:
{recortar(cv, 7000)}

AVISO:
{aviso_texto}

JSON con esta forma:
{{"resumen":"", "habilidades":[""], "experiencia":[""], "mensaje":""}}
"""
    modelos = [modelo or "gemini-2.5-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
    vistos = []
    ultimo = None
    for nombre in modelos:
        if nombre in vistos:
            continue
        vistos.append(nombre)
        try:
            crudo = _gemini(prompt, clave, nombre)
            data = _leer_json_ia(crudo)
            break
        except Exception as exc:
            ultimo = exc
            data = None
    if not data:
        raise ultimo or RuntimeError("No se pudo usar la IA.")

    aviso_completo = f"{aviso.get('titulo', '')}\n{aviso.get('descripcion', '')}"
    resumen = str(data.get("resumen") or "").strip()
    if not _respaldado(resumen, cv):
        resumen = base["resumen"]
    experiencia = []
    for item in data.get("experiencia") or []:
        linea = str(item).strip().lstrip("-• ").strip()
        if linea and _respaldado(linea, cv):
            experiencia.append(linea)
    if not experiencia:
        experiencia = base["experiencia"]
    habilidades = _filtrar_habilidades_ia(data.get("habilidades"), cv, aviso_completo)
    if not habilidades:
        habilidades = base["habilidades"]
    mensaje = str(data.get("mensaje") or "").strip()
    if mensaje and not _respaldado(mensaje, cv):
        mensaje = ""
    return {
        "resumen": resumen,
        "habilidades": habilidades[:12],
        "experiencia": experiencia[:8],
        "mensaje": mensaje,
        "con_ia": True,
    }


def titulo_para_cv(aviso, cv, nivel):
    if nivel != "encaja":
        return ""
    titulo = re.sub(r"\s+", " ", (aviso.get("titulo") or "")).strip()
    if not titulo:
        return ""
    plano = fold(cv)
    for marca in ("senior", "staff", "principal", "director", "head", "lead", "jefe", "gerente"):
        if contiene(fold(titulo), marca) and not contiene(plano, marca):
            titulo = re.sub(rf"(?i)\b{marca}\b", "", titulo)
    titulo = re.sub(r"\s{2,}", " ", titulo).strip(" -–,/|")
    return titulo[:120]


def armar_texto(base, aviso, cv=""):
    bloques = []
    contacto = [x for x in (base.get("email"), base.get("telefono")) if x]
    contacto.extend(base.get("links") or [])
    if base.get("nombre"):
        bloques.append(base["nombre"])
    if contacto:
        bloques.append(" | ".join(contacto))
    titulo = titulo_para_cv(aviso, cv, base.get("nivel"))
    if titulo:
        bloques.append("")
        bloques.append(titulo)
    bloques.append("")
    bloques.append("RESUMEN")
    bloques.append(base.get("resumen") or "")
    if base.get("habilidades"):
        bloques.append("")
        bloques.append("HABILIDADES")
        bloques.append(", ".join(base["habilidades"]))
    if base.get("experiencia"):
        bloques.append("")
        bloques.append("EXPERIENCIA")
        for linea in base["experiencia"]:
            bloques.append("- " + linea.lstrip("- ").strip())
    if base.get("estudios"):
        bloques.append("")
        bloques.append("ESTUDIOS")
        for linea in base["estudios"]:
            bloques.append("- " + linea.lstrip("- ").strip())
    return "\n".join(bloques).strip() + "\n"


def propuesta(cv, aviso, base):
    titulo = (aviso.get("titulo") or "el puesto").strip()
    empresa = (aviso.get("empresa") or "").strip()
    url = (aviso.get("url") or "").strip()
    nombre = (base.get("nombre") or "").strip()
    donde = f" en {empresa}" if empresa else ""
    estudios = [s.strip() for s in (base.get("estudios") or []) if str(s).strip()]
    experiencia = [e.strip().lstrip("- ").strip() for e in (base.get("experiencia") or []) if str(e).strip()][:5]
    habilidades = [h for h in (base.get("habilidades") or []) if h][:8]
    lineas = [f"Propuesta para {titulo}{donde}", ""]
    if nombre and estudios:
        lineas.append(f"Soy {nombre}. {estudios[0].rstrip('.')}.")
    elif nombre:
        lineas.append(f"Soy {nombre}.")
    elif estudios:
        lineas.append(estudios[0].rstrip(".") + ".")
    else:
        lineas.append("Escribo a partir de lo que ya figura en mi CV.")
    if experiencia:
        lineas.append("")
        lineas.append("Experiencia que ya figura en mi CV y se cruza con este puesto:")
        for linea in experiencia:
            lineas.append("- " + linea)
    lineas.append("")
    if habilidades:
        lineas.append(
            "Cómo lo llevaría: con lo que ya uso ("
            + ", ".join(habilidades)
            + "), sin agregar empleos ni herramientas que no aparecen en el CV."
        )
    else:
        lineas.append(
            "Cómo lo llevaría: con la experiencia que ya está escrita en el CV, sin inventar herramientas ni empleos."
        )
    if len(estudios) > 1:
        lineas.append("")
        lineas.append("También figura en el CV: " + "; ".join(s.rstrip(".") for s in estudios[1:3]) + ".")
    if base.get("faltan"):
        lineas.append("")
        lineas.append(
            "El aviso nombra cosas que no uso y por eso no las pongo como si las hubiera hecho: "
            + ", ".join(base["faltan"][:6])
            + "."
        )
    if url:
        lineas.append("")
        lineas.append("Link para postularme: " + url)
    return "\n".join(lineas).strip() + "\n"


def mensaje_local(base, aviso):
    titulo = aviso.get("titulo") or "el puesto"
    empresa = aviso.get("empresa") or ""
    donde = f" en {empresa}" if empresa else ""
    habilidades = ", ".join((base.get("habilidades") or [])[:4])
    detalle = ""
    if base.get("experiencia"):
        detalle = " " + base["experiencia"][0].strip()
    habilidad_txt = f" Trabajo con {habilidades}." if habilidades else ""
    return (
        f"Hola,\n\n"
        f"Vi la búsqueda de {titulo}{donde}.{habilidad_txt}{detalle}\n\n"
        f"Dejo mi CV ordenado con la experiencia que ya tengo y que se cruza con este aviso.\n\n"
        f"Gracias."
    )


def adaptar(cv, aviso, config):
    base = adaptar_local(cv, aviso)
    con_ia = False
    aviso_ia = ""
    clave = (config or {}).get("gemini_key", "").strip()
    if clave:
        try:
            mejor = mejorar_con_ia(
                cv,
                aviso,
                base,
                clave,
                (config or {}).get("gemini_modelo") or "gemini-2.5-flash",
            )
            base["resumen"] = mejor["resumen"]
            base["habilidades"] = mejor["habilidades"]
            base["experiencia"] = mejor["experiencia"]
            if mejor.get("mensaje"):
                base["mensaje"] = mejor["mensaje"]
            con_ia = True
        except Exception as exc:
            aviso_ia = str(exc)[:240]
    if not base.get("mensaje"):
        base["mensaje"] = mensaje_local(base, aviso)
    texto = armar_texto(base, aviso, cv)
    return {
        "cv_texto": texto,
        "propuesta": propuesta(cv, aviso, base),
        "mensaje": base["mensaje"],
        "habilidades": base["habilidades"],
        "palabras_sin_respaldo": base["faltan"],
        "puntaje": base["puntaje"],
        "nivel": base["nivel"],
        "con_ia": con_ia,
        "aviso_ia": aviso_ia,
        "url": aviso.get("url") or "",
        "titulo": aviso.get("titulo") or "",
        "empresa": aviso.get("empresa") or "",
        "fuente": aviso.get("fuente") or "",
    }
