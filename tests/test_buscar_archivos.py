from pathlib import Path

from jarvis.tools import buscar_archivos


def crear(base: Path, *rutas: str) -> None:
    for ruta in rutas:
        archivo = base / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text("x", encoding="utf-8")


def nombres(salida: str) -> list[str]:
    return [Path(linea).name for linea in salida.splitlines()[1:] if not linea.startswith("(")]


def test_encuentra_por_nombre_y_comodin(tmp_path):
    crear(tmp_path, "informe.pdf", "sub/Informe-2.PDF")
    for patron in ("informe", "*.pdf"):
        salida = buscar_archivos.ejecutar(str(tmp_path), patron)
        assert salida.startswith("Encontré 2 archivo(s):")
        assert str(tmp_path / "informe.pdf") in salida
        assert str(tmp_path / "sub" / "Informe-2.PDF") in salida


def test_no_lee_contenidos(tmp_path):
    (tmp_path / "notas.txt").write_text("informe", encoding="utf-8")
    salida = buscar_archivos.ejecutar(str(tmp_path), "informe")
    assert "notas.txt" not in salida


def test_nunca_lista_env(tmp_path):
    # .ENV va en otra carpeta: en Windows .env y .ENV en la misma serían el mismo archivo
    crear(tmp_path, ".env", "otra/.ENV", ".env.local", "sub/.env.example", ".env-local", ".env_prod", ".envrc",
          "app.env", "config.env.txt")
    for patron in ("env", "*"):
        encontrados = [n.casefold() for n in nombres(buscar_archivos.ejecutar(str(tmp_path), patron))]
        assert encontrados == ["config.env.txt"]


def test_carpeta_oculta_se_salta(tmp_path):
    crear(tmp_path, ".git/informe.txt")
    assert "informe.txt" not in buscar_archivos.ejecutar(str(tmp_path), "informe")


def test_profundidad_maxima(tmp_path):
    crear(tmp_path, "a/b/c/d/e/x.txt", "a/b/c/d/e/f/x.txt")
    salida = buscar_archivos.ejecutar(str(tmp_path), "x.txt")
    assert salida.startswith("Encontré 1 archivo(s):")
    assert str(tmp_path / "a/b/c/d/e/x.txt") in salida


def test_tope_de_resultados(tmp_path):
    crear(tmp_path, *[f"f{i}.txt" for i in range(60)])
    lineas = buscar_archivos.ejecutar(str(tmp_path), "f").splitlines()
    assert lineas[0] == "Encontré 50 archivo(s):"
    assert len(lineas) == 52
    assert lineas[-1] == "(hay más; acota la búsqueda)"


def test_errores_y_sin_coincidencias(tmp_path):
    falta = str(tmp_path / "nada")
    assert buscar_archivos.ejecutar(falta, "x") == f"Error: la carpeta '{falta}' no existe."
    assert buscar_archivos.ejecutar(str(tmp_path), "") == "Error: falta el patrón de búsqueda."
    assert buscar_archivos.ejecutar(str(tmp_path), "zzz") == (
        f"No encontré archivos que coincidan con 'zzz' en '{tmp_path}'.")


def test_no_pide_confirmacion():
    assert buscar_archivos.requiere_confirmacion is False
