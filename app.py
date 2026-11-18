import base64
import hashlib
import json
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from cvarchivo import leer_archivo
from fuentes import buscar_fuentes
from motor import adaptar, armar_consulta, forma_visible, puntuar, transcribir_cv

ROOT = Path(__file__).resolve().parent
DATOS = ROOT / "datos"
CV_PATH = DATOS / "cv.txt"
CONFIG_PATH = DATOS / "config.json"
POSTULACIONES_PATH = DATOS / "postulaciones.json"
CANDADO = threading.Lock()
MEMORIA = {}

PUERTO_BASE = 8765


def cargar_config():
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def guardar_config(config):
    DATOS.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def cargar_cv():
    try:
        return CV_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""


def guardar_cv(texto):
    DATOS.mkdir(parents=True, exist_ok=True)
    CV_PATH.write_text(texto or "", encoding="utf-8")


def cargar_postulaciones():
    try:
        data = json.loads(POSTULACIONES_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return []


def guardar_postulacion(resultado):
    entrada = {
        "titulo": resultado.get("titulo") or "",
        "empresa": resultado.get("empresa") or "",
        "fuente": resultado.get("fuente") or "",
        "url": resultado.get("url") or "",
        "cv_texto": resultado.get("cv_texto") or "",
        "propuesta": resultado.get("propuesta") or "",
        "mensaje": resultado.get("mensaje") or "",
        "cuando": datetime.now().isoformat(timespec="minutes"),
    }
    items = [item for item in cargar_postulaciones() if item.get("url") != entrada["url"]]
    items.insert(0, entrada)
    DATOS.mkdir(parents=True, exist_ok=True)
    POSTULACIONES_PATH.write_text(
        json.dumps(items[:40], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return [
        {k: item.get(k) or "" for k in ("titulo", "empresa", "fuente", "url", "cuando")}
        for item in items[:40]
    ]


def _clave(secreto, nuevo, borrar):
    if borrar:
        return ""
    nuevo = (nuevo or "").strip()
    if nuevo:
        return nuevo
    return secreto or ""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, formato, *args):
        return

    def _enviar(self, codigo, data, tipo="application/json; charset=utf-8"):
        if isinstance(data, (dict, list)):
            raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        elif isinstance(data, bytes):
            raw = data
        else:
            raw = str(data).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _json(self):
        largo = int(self.headers.get("Content-Length") or 0)
        if largo > 12_000_000:
            raise ValueError("El archivo es demasiado grande.")
        raw = self.rfile.read(largo) if largo else b""
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("El pedido no es un objeto.")
        return data

    def do_GET(self):
        ruta = urlparse(self.path).path
        if ruta == "/":
            html = (ROOT / "index.html").read_bytes()
            self._enviar(200, html, "text/html; charset=utf-8")
            return
        if ruta == "/api/estado":
            config = cargar_config()
            self._enviar(
                200,
                {
                    "cv": cargar_cv(),
                    "consulta": config.get("consulta") or "",
                    "lugar": config.get("lugar") or "Argentina",
                    "solo_remotos": bool(config.get("solo_remotos")),
                    "adzuna_pais": config.get("adzuna_pais") or "ar",
                    "claves": {
                        "gemini": bool((config.get("gemini_key") or "").strip()),
                        "adzuna": bool((config.get("adzuna_app_id") or "").strip() and (config.get("adzuna_app_key") or "").strip()),
                        "jooble": bool((config.get("jooble_key") or "").strip()),
                    },
                },
            )
            return
        if ruta == "/api/postulaciones":
            self._enviar(200, {"postulaciones": cargar_postulaciones()})
            return
        self._enviar(404, {"error": "No existe."})

    def do_POST(self):
        ruta = urlparse(self.path).path
        try:
            data = self._json()
        except Exception as exc:
            self._enviar(400, {"error": str(exc)})
            return
        if ruta == "/api/config":
            self._guardar_config(data)
            return
        if ruta == "/api/buscar":
            self._buscar(data)
            return
        if ruta == "/api/adaptar":
            self._adaptar(data)
            return
        if ruta == "/api/cv":
            self._subir_cv(data)
            return
        if ruta == "/api/cv-ats":
            self._cv_ats(data)
            return
        self._enviar(404, {"error": "No existe."})

    def _guardar_config(self, data):
        config = cargar_config()
        config["gemini_key"] = _clave(config.get("gemini_key"), data.get("gemini_key"), data.get("borrar_gemini"))
        config["adzuna_app_id"] = _clave(config.get("adzuna_app_id"), data.get("adzuna_app_id"), data.get("borrar_adzuna"))
        config["adzuna_app_key"] = _clave(config.get("adzuna_app_key"), data.get("adzuna_app_key"), data.get("borrar_adzuna"))
        config["jooble_key"] = _clave(config.get("jooble_key"), data.get("jooble_key"), data.get("borrar_jooble"))
        pais = (data.get("adzuna_pais") or config.get("adzuna_pais") or "ar").strip().lower()
        config["adzuna_pais"] = pais if len(pais) == 2 and pais.isalpha() else "ar"
        if "gemini_modelo" in data and data.get("gemini_modelo"):
            config["gemini_modelo"] = str(data.get("gemini_modelo"))[:80]
        guardar_config(config)
        self._enviar(200, {"ok": True})

    def _buscar(self, data):
        cv = str(data.get("cv") or "").strip()
        if len(cv) < 40:
            self._enviar(400, {"error": "Subí el archivo de tu CV. Con un par de líneas no se puede saber si un puesto te sirve."})
            return
        guardar_cv(cv)
        config = cargar_config()
        consulta = armar_consulta(cv, str(data.get("consulta") or ""))
        lugar = str(data.get("lugar") or config.get("lugar") or "Argentina").strip()[:80]
        solo_remotos = bool(data.get("solo_remotos"))
        config["consulta"] = str(data.get("consulta") or "")[:120]
        config["lugar"] = lugar
        config["solo_remotos"] = solo_remotos
        guardar_config(config)

        crudos, reportes = buscar_fuentes(consulta, config, lugar, solo_remotos)
        vistos = set()
        unicos = []
        for job in crudos:
            url = job["url"].split("?")[0].rstrip("/").lower()
            firma = (url, job["titulo"].strip().lower(), job["empresa"].strip().lower())
            if firma in vistos:
                continue
            vistos.add(firma)
            unicos.append(job)

        memoria = {}
        anotados = []
        for job in unicos:
            ident = hashlib.sha1(f"{job['fuente']}|{job['url']}|{job['titulo']}".encode("utf-8")).hexdigest()[:12]
            evaluacion = puntuar(cv, job)
            memoria[ident] = job
            anotados.append(
                {
                    "id": ident,
                    "titulo": job["titulo"],
                    "empresa": job["empresa"],
                    "fuente": job["fuente"],
                    "url": job["url"],
                    "lugar": job["lugar"],
                    "remoto": job["remoto"],
                    "fecha": job["fecha"],
                    "salario": job["salario"],
                    "extracto": (job["descripcion"] or "").replace("\n", " ")[:280],
                    "puntaje": evaluacion["puntaje"],
                    "nivel": evaluacion["nivel"],
                    "motivos": evaluacion["motivos"],
                    "palabras_sin_respaldo": [
                        # se completan en adaptar; acá van las que el motor ya separó
                    ],
                }
            )
            faltan = evaluacion["faltan"]
            aviso_texto = f"{job['titulo']}\n{job['descripcion']}"
            anotados[-1]["palabras_sin_respaldo"] = [
                forma_visible(h, aviso_texto, aviso_texto) for h in faltan[:5]
            ]

        anotados.sort(key=lambda item: item["puntaje"], reverse=True)
        buenos = [item for item in anotados if item["nivel"] != "flojo"]
        if len(buenos) >= 8:
            visibles = buenos[:40]
            mensaje = ""
        elif buenos:
            resto = [item for item in anotados if item["nivel"] == "flojo"]
            visibles = (buenos + resto)[:15]
            mensaje = "Hay pocos avisos que encajen. También se muestran los más cercanos."
        else:
            visibles = anotados[:12]
            mensaje = (
                "Ningún aviso encaja bien con tu CV. Estos son los menos lejanos. "
                "No agregues palabras del aviso si no las hiciste."
            )

        with CANDADO:
            MEMORIA.clear()
            MEMORIA.update(memoria)

        self._enviar(
            200,
            {
                "consulta": consulta,
                "mensaje": mensaje,
                "fuentes": reportes,
                "revisados": len(unicos),
                "resultados": visibles,
            },
        )

    def _adaptar(self, data):
        ident = str(data.get("id") or "")
        with CANDADO:
            job = MEMORIA.get(ident)
        if not job:
            self._enviar(404, {"error": "Ese aviso ya no está en memoria. Volvé a buscar."})
            return
        cv = str(data.get("cv") or "").strip() or cargar_cv()
        if len(cv) < 40:
            self._enviar(400, {"error": "Falta el CV."})
            return
        guardar_cv(cv)
        resultado = adaptar(cv, job, cargar_config())
        guardar_postulacion(resultado)
        self._enviar(200, resultado)

    def _subir_cv(self, data):
        nombre = str(data.get("nombre") or "")
        try:
            crudo = base64.b64decode(str(data.get("contenido") or ""), validate=False)
        except Exception:
            self._enviar(400, {"error": "No pude leer el archivo."})
            return
        if not crudo:
            self._enviar(400, {"error": "El archivo está vacío."})
            return
        try:
            texto, imagenes = leer_archivo(nombre, crudo)
        except ValueError as exc:
            self._enviar(400, {"error": str(exc)})
            return
        aviso = ""
        if len(texto.strip()) < 80:
            config = cargar_config()
            clave = (config.get("gemini_key") or "").strip()
            if not clave or not imagenes:
                self._enviar(
                    400,
                    {
                        "error": (
                            "Ese archivo no tiene texto para copiar. "
                            "Si es una foto o un PDF escaneado, guardá la clave de Gemini y volvé a subirlo: "
                            "la IA copia lo que se lee, sin completarlo."
                        )
                    },
                )
                return
            try:
                texto = transcribir_cv(
                    imagenes,
                    clave,
                    (config.get("gemini_modelo") or "gemini-2.5-flash"),
                )
            except Exception as exc:
                self._enviar(400, {"error": str(exc)[:240]})
                return
            aviso = "El archivo era una imagen. Gemini copió el texto visible, sin agregar datos."
        texto = texto.strip()
        if len(texto) < 40:
            self._enviar(400, {"error": "No alcancé a leer un CV en ese archivo."})
            return
        guardar_cv(texto)
        self._enviar(200, {"cv": texto, "aviso": aviso})

    def _cv_ats(self, data):
        cv = str(data.get("cv") or "").strip() or cargar_cv()
        if len(cv) < 40:
            self._enviar(400, {"error": "Primero subí el archivo del CV."})
            return
        config = cargar_config()
        if not (config.get("gemini_key") or "").strip():
            self._enviar(
                400,
                {
                    "error": (
                        "Guardá la clave de Gemini. Con esa clave se redacta un CV nuevo en texto plano "
                        "para los filtros ATS, usando solo el archivo original."
                    )
                },
            )
            return
        guardar_cv(cv)
        consulta = str(data.get("consulta") or config.get("consulta") or "").strip()
        aviso = {
            "titulo": consulta or "el puesto buscado",
            "empresa": "",
            "descripcion": consulta,
            "url": "",
            "fuente": "",
        }
        resultado = adaptar(cv, aviso, config)
        if not resultado.get("con_ia"):
            self._enviar(
                400,
                {"error": resultado.get("aviso_ia") or "Gemini no pudo redactar el CV."},
            )
            return
        resultado["titulo"] = "CV para filtros ATS"
        resultado["url"] = "local://cv-ats"
        guardar_postulacion(resultado)
        self._enviar(200, resultado)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    DATOS.mkdir(parents=True, exist_ok=True)
    puerto = PUERTO_BASE
    servidor = None
    for candidato in range(PUERTO_BASE, PUERTO_BASE + 6):
        try:
            servidor = ThreadingHTTPServer(("127.0.0.1", candidato), Handler)
            puerto = candidato
            break
        except OSError:
            continue
    if servidor is None:
        print("No pude abrir un puerto local entre 8765 y 8770.")
        return
    url = f"http://127.0.0.1:{puerto}"
    print(f"Buscador listo en {url}", flush=True)
    print("Dejá esta ventana abierta. Para cerrarlo, usá Ctrl+C.", flush=True)
    if "--sin-navegador" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    servidor.serve_forever()


if __name__ == "__main__":
    main()
