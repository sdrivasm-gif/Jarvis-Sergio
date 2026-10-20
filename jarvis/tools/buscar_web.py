"""Búsqueda web con el HTML de DuckDuckGo: sin clave y solo con la biblioteca estándar."""
import html
import re
import urllib.parse
import urllib.request

NOMBRE = "buscar_web"
DESCRIPCION = ("Busca en la web (DuckDuckGo) y devuelve hasta 5 resultados con título, resumen y enlace. "
               "No incluyas datos personales en la consulta.")
ESQUEMA = {
    "type": "object",
    "properties": {"consulta": {"type": "string", "description": "Qué buscar."}},
    "required": ["consulta"],
}
# ponytail: la consulta sale del equipo sin confirmación; si se quiere aprobar cada búsqueda, poner True.
requiere_confirmacion = False  # solo lee; no cambia nada fuera de la carpeta de datos (ver decisión 002, punto 2)
URL = "https://html.duckduckgo.com/html/"
AGENTE = "Mozilla/5.0 (Jarvis)"
TIMEOUT = 10
MAX_RESULTADOS = 5

TITULO = re.compile(r"<a\s([^>]*class=\"result__a\"[^>]*)>(.*?)</a>", re.DOTALL)
HREF = re.compile(r"href=\"([^\"]*)\"")
RESUMEN = re.compile(r"class=\"result__snippet\"[^>]*>(.*?)</a>", re.DOTALL)


def descargar(url: str) -> str:
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(peticion, timeout=TIMEOUT) as respuesta:  # por atributo, por la guardia de los tests
        return respuesta.read().decode("utf-8", "replace")


def limpiar(fragmento: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", fragmento)).split())


def extraer_resultados(pagina: str) -> list[dict]:
    # ponytail: regex sobre el HTML de DuckDuckGo; si cambia o sale un captcha da "Sin resultados" (distinguir el bloqueo).
    titulos = list(TITULO.finditer(pagina))
    resultados = []
    for i, m in enumerate(titulos):
        enlace = HREF.search(m.group(1))  # dentro de la etiqueta, sin depender del orden de los atributos
        href = html.unescape(enlace.group(1)) if enlace else ""
        if "duckduckgo.com/y.js" in href:  # anuncio
            continue
        if "uddg=" in href:  # enlace de redirección: la URL real va en el parámetro uddg
            href = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg", [href])[0]  # vacío: deja el de DDG
        if href.startswith("//"):
            href = "https:" + href
        fin = titulos[i + 1].start() if i + 1 < len(titulos) else len(pagina)
        resumen = RESUMEN.search(pagina, m.end(), fin)
        resultados.append({"titulo": limpiar(m.group(2)), "url": href,
                           "resumen": limpiar(resumen.group(1)) if resumen else ""})
    return resultados


def ejecutar(consulta: str) -> str:
    if not consulta.strip():
        return "Error: falta la consulta."
    url = URL + "?" + urllib.parse.urlencode({"q": consulta})
    resultados = extraer_resultados(descargar(url))[:MAX_RESULTADOS]
    if not resultados:
        return f"Sin resultados para '{consulta}'."
    return "\n".join(
        f"{i}. {r['titulo']} — {r['resumen']} ({r['url']})" if r["resumen"] else f"{i}. {r['titulo']} ({r['url']})"
        for i, r in enumerate(resultados, 1)
    )
