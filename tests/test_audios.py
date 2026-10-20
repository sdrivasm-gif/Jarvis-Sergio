import importlib.util
import wave
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
AUDIO = Path(__file__).parent / "audio"
NOMBRES = {"silencio": 33, "tono": 100, "ruido_bajo": 33, "chasquido": 33}


@pytest.mark.parametrize("nombre,bloques", NOMBRES.items())
def test_audios_validos(nombre, bloques):
    ruta = AUDIO / f"{nombre}.wav"
    with wave.open(str(ruta), "rb") as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 16000)
        assert w.getnframes() == bloques * 480
    assert ruta.stat().st_size < 100_000


def test_audios_reproducibles(tmp_path):
    spec = importlib.util.spec_from_file_location("generar_audios_prueba", RAIZ / "scripts" / "generar_audios_prueba.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rutas = mod.generar(tmp_path)
    assert len(rutas) == 4
    for ruta in rutas:
        assert ruta.read_bytes() == (AUDIO / ruta.name).read_bytes()
