"""Opcional: faster-whisper real con audios de tests/audio/. Se salta sin el extra [voz] o sin una carpeta local
de modelo en JARVIS_STT_MODELO (con un nombre como "base" se salta: los tests nunca descargan nada)."""
import os
from pathlib import Path

import pytest

faster_whisper = pytest.importorskip("faster_whisper")

from jarvis import voz  # noqa: E402

AUDIO = Path(__file__).parent / "audio"
MODELO = os.environ.get("JARVIS_STT_MODELO", "")
pytestmark = pytest.mark.skipif(not (MODELO and Path(MODELO).is_dir()),
                                reason="pon JARVIS_STT_MODELO con la carpeta local de un modelo de faster-whisper")
FRASES = sorted(AUDIO.glob("voz_*.wav"))


@pytest.fixture(scope="module")
def transcribir():
    return voz.transcriptor_whisper(MODELO, "jarvis")


def test_silencio_da_texto_vacio(transcribir):
    assert transcribir(b"".join(voz.bloques_de_wav(AUDIO / "silencio.wav"))) == ""


@pytest.mark.parametrize("ruta", FRASES or [pytest.param(None, marks=pytest.mark.skip(
    reason="sin voz_*.wav: python scripts/generar_audios_prueba.py --con-voz"))])
def test_frase_real(transcribir, ruta):
    oido = voz.OyenteLocal(transcribir, fuente=lambda: voz.bloques_de_wav(ruta)).escuchar()
    esperado = ruta.with_suffix(".txt").read_text(encoding="utf-8")
    assert set(voz.normalizar(esperado).split()) <= set(voz.normalizar(oido or "").split())
    if ruta.name.startswith("voz_si"):
        assert voz.es_afirmativa(oido) is True
    if ruta.name.startswith("voz_no"):
        assert voz.es_afirmativa(oido) is False
