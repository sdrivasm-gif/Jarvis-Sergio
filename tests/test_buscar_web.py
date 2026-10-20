import urllib.request

from jarvis.tools import buscar_web

# Imita el HTML de html.duckduckgo.com: un anuncio, Lima, uno sin resumen y 5 más.
HTML_FALSO = """
<div class="result results_links result--ad">
  <a rel="nofollow" class="result__a" href="https://duckduckgo.com/y.js?ad=1">Anuncio</a>
  <a class="result__snippet" href="https://duckduckgo.com/y.js?ad=1">Compra ya</a>
</div>
<div class="result results_links">
  <h2 class="result__title">
    <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fes.wikipedia.org%2Fwiki%2FLima&amp;rut=abc">Lima - <b>Wikipedia</b></a>
  </h2>
  <a class="result__snippet" href="//duckduckgo.com/l/?uddg=x">Lima es la <b>capital</b>
     del Perú &amp; ...</a>
</div>
<div class="result results_links">
  <a href="https://sin-resumen.example/" class="result__a" rel="nofollow">Sin resumen</a>
</div>
""" + "".join(
    f'<div class="result"><a class="result__a" href="https://r{i}.example/">Resultado {i}</a>'
    f'<a class="result__snippet" href="https://r{i}.example/">Resumen {i}</a></div>\n'
    for i in range(5)
)


def test_extraer_resultados():
    resultados = buscar_web.extraer_resultados(HTML_FALSO)
    assert all("y.js" not in r["url"] for r in resultados)
    assert resultados[0] == {
        "titulo": "Lima - Wikipedia",
        "url": "https://es.wikipedia.org/wiki/Lima",
        "resumen": "Lima es la capital del Perú & ...",
    }
    assert resultados[1] == {"titulo": "Sin resumen", "url": "https://sin-resumen.example/", "resumen": ""}
    assert len(resultados) == 7


def test_uddg_vacio_no_tumba_la_busqueda():
    pagina = ('<a class="result__a" href="//duckduckgo.com/l/?uddg=&amp;rut=x">Vacío</a>'
              '<a class="result__a" href="https://normal.example/">Normal</a>')
    resultados = buscar_web.extraer_resultados(pagina)
    assert resultados[0]["url"] == "https://duckduckgo.com/l/?uddg=&rut=x"  # sin destino: queda el enlace de DDG
    assert resultados[1] == {"titulo": "Normal", "url": "https://normal.example/", "resumen": ""}


def test_ejecutar_formatea_cinco_resultados(monkeypatch):
    urls = []
    monkeypatch.setattr(buscar_web, "descargar", lambda url: urls.append(url) or HTML_FALSO)
    lineas = buscar_web.ejecutar("clima en Lima").split("\n")
    assert urls == ["https://html.duckduckgo.com/html/?q=clima+en+Lima"]
    assert len(lineas) == 5
    assert lineas[0] == "1. Lima - Wikipedia — Lima es la capital del Perú & ... (https://es.wikipedia.org/wiki/Lima)"
    assert lineas[1] == "2. Sin resumen (https://sin-resumen.example/)"


def test_sin_resultados_y_consulta_vacia(monkeypatch):
    urls = []
    monkeypatch.setattr(buscar_web, "descargar", lambda url: urls.append(url) or "<html>nada</html>")
    assert buscar_web.ejecutar("nada") == "Sin resultados para 'nada'."
    urls.clear()
    assert buscar_web.ejecutar(" ") == "Error: falta la consulta."
    assert urls == []


def test_descargar_usa_agente_y_timeout(monkeypatch):
    recibidos = []

    class RespuestaFalsa:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return "<html>hola</html>".encode("utf-8")

    def urlopen_falso(peticion, timeout=None):
        recibidos.append((peticion, timeout))
        return RespuestaFalsa()

    monkeypatch.setattr(urllib.request, "urlopen", urlopen_falso)
    assert buscar_web.descargar("https://html.duckduckgo.com/html/?q=x") == "<html>hola</html>"
    peticion, timeout = recibidos[0]
    assert peticion.full_url == "https://html.duckduckgo.com/html/?q=x"
    assert peticion.get_header("User-agent") == buscar_web.AGENTE
    assert timeout == 10


def test_no_requiere_confirmacion():
    assert buscar_web.requiere_confirmacion is False
