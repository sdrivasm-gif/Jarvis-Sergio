import base64
import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

RAIZ_PROYECTO = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("crear_acceso_directo", RAIZ_PROYECTO / "scripts" / "crear_acceso_directo.py")
ad = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ad)


def test_variables(tmp_path):
    v = ad.variables(tmp_path / "python.exe", tmp_path / "raiz", tmp_path / "esc")
    assert v == {"JARVIS_LNK_PYTHON": str(tmp_path / "python.exe"), "JARVIS_LNK_RAIZ": str(tmp_path / "raiz"),
                 "JARVIS_LNK_CARPETA": str(tmp_path / "esc"), "JARVIS_LNK_NOMBRE": "Jarvis.lnk"}
    assert ad.variables(tmp_path / "python.exe", tmp_path, None)["JARVIS_LNK_CARPETA"] == ""


def test_script_constante():
    c = ad.comando()
    assert c[:4] == ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand"]
    assert base64.b64decode(c[-1]).decode("utf-16-le") == ad.SCRIPT_LNK
    for parte in ("CreateShortcut", "'-m jarvis --ui'", "$env:JARVIS_LNK_PYTHON", "GetFolderPath('Desktop')",
                  "WindowStyle = 7"):
        assert parte in ad.SCRIPT_LNK
    assert ":\\" not in ad.SCRIPT_LNK


def test_crear_con_ejecutor_falso(tmp_path):
    (tmp_path / "python.exe").write_text("")
    llamadas = []

    def falso(*args, **kwargs):
        llamadas.append((args, kwargs))
        return SimpleNamespace(stdout=str(tmp_path / "Jarvis.lnk") + "\r\n")

    assert ad.crear(carpeta=tmp_path, python=tmp_path / "python.exe", ejecutar=falso) == tmp_path / "Jarvis.lnk"
    args, kwargs = llamadas[0]
    assert args[0] == ad.comando()
    assert kwargs["env"]["JARVIS_LNK_CARPETA"] == str(tmp_path)
    assert kwargs["env"]["JARVIS_LNK_RAIZ"] == str(ad.RAIZ)
    assert kwargs["check"] is True and kwargs["capture_output"] is True and kwargs["text"] is True
    assert "shell" not in kwargs
    assert [p.name for p in tmp_path.iterdir()] == ["python.exe"]
    (tmp_path / "pythonw.exe").write_text("")
    ad.crear(carpeta=tmp_path, python=tmp_path / "pythonw.exe", ejecutar=falso)
    assert llamadas[1][1]["env"]["JARVIS_LNK_PYTHON"].endswith("python.exe")


def test_sin_python(tmp_path):
    with pytest.raises(SystemExit):
        ad.crear(carpeta=tmp_path, python=tmp_path / "no.exe", ejecutar=lambda *a, **k: None)


@pytest.mark.parametrize("stderr, detalle", [
    ("Error:\x1b[31m acceso\r\n  denegado‮", "Error: [31m acceso denegado"),
    (b"fallo \xff raro", "fallo � raro"),
    (None, "PowerShell terminó con el código 1."),
    ("x" * 1000, "x" * 300 + "…"),
])
def test_powershell_falla(tmp_path, stderr, detalle):
    (tmp_path / "python.exe").write_text("")

    def falla(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0], output="", stderr=stderr)

    with pytest.raises(SystemExit) as e:
        ad.crear(carpeta=tmp_path, python=tmp_path / "python.exe", ejecutar=falla)
    assert str(e.value) == f"No pude crear el acceso directo: {detalle}"


def test_sin_ejecutor_lo_para_la_guardia(tmp_path):
    (tmp_path / "python.exe").write_text("")
    with pytest.raises(AssertionError, match="acción real"):
        ad.crear(carpeta=tmp_path, python=tmp_path / "python.exe")


def test_main(monkeypatch, tmp_path, capsys):
    vistas = []
    monkeypatch.setattr(ad, "crear", lambda carpeta=None, **k: vistas.append(carpeta) or tmp_path / "Jarvis.lnk")
    assert ad.main(["--carpeta", str(tmp_path)]) == 0
    assert vistas == [tmp_path]
    assert "Acceso directo creado:" in capsys.readouterr().out
