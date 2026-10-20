import importlib.util
from pathlib import Path

import pytest

from jarvis import habla, voz

RAIZ_PROYECTO = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("medir_voz", RAIZ_PROYECTO / "scripts" / "medir_voz.py")
mv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mv)


class HablanteMedido:
    """Hablante simulado: decir llama a al_empezar (si `suena`) como lo haría el reproductor de la cola."""

    def __init__(self, suena=True, nombre="edge (es-MX-JorgeNeural)"):
        self.suena, self.nombre, self.al_empezar, self.dichos = suena, nombre, None, []

    def decir(self, texto):
        self.dichos.append(texto)
        if self.suena and self.al_empezar:
            self.al_empezar()


def reloj_falso(*tiempos):
    pendientes = iter(tiempos)
    return lambda: next(pendientes)


def test_medir_primer_audio_y_total():
    h = HablanteMedido()
    assert mv.medir(h, "Hola, señor.", reloj_falso(0.0, 0.4, 2.5)) == (0.4, 2.5)
    assert h.dichos == ["Hola, señor."] and h.al_empezar is None  # el gancho se devuelve como estaba


def test_medir_sin_al_empezar_no_hay_primer_audio():
    assert mv.medir(HablanteMedido(suena=False), "Hola.", reloj_falso(0.0, 1.5)) == (None, 1.5)


@pytest.fixture
def sin_env(monkeypatch):
    monkeypatch.setattr(mv, "load_dotenv", lambda: None)  # no se lee el .env real
    monkeypatch.setenv("ELEVENLABS_API_KEY", "clave-de-mentira-123")


def test_main_con_sapi(monkeypatch, capsys, sin_env):
    entornos = []

    def crear_hablante(entorno, mostrar=print):
        entornos.append(entorno)
        return HablanteMedido(suena=False, nombre="sapi")

    monkeypatch.setattr(habla, "crear_hablante", crear_hablante)
    assert mv.main(["--motor", "sapi"]) == 0
    assert entornos[0]["JARVIS_VOZ_MOTOR"] == "sapi"
    salida = capsys.readouterr()
    lineas = salida.out.splitlines()
    assert lineas[0] == "motor: sapi"
    assert lineas[1] == "primer audio: n/d (la voz de Windows no lo informa)"
    assert lineas[2].startswith("total: ") and lineas[2].endswith(" s")
    assert "clave-de-mentira-123" not in salida.out + salida.err


def test_main_imprime_el_primer_audio(monkeypatch, capsys, sin_env):
    monkeypatch.setattr(habla, "crear_hablante", lambda entorno, mostrar=print: HablanteMedido())
    assert mv.main(["--frase", "Una frase de prueba."]) == 0
    lineas = capsys.readouterr().out.splitlines()
    assert lineas[0] == "motor: edge (es-MX-JorgeNeural)"
    assert lineas[1].startswith("primer audio: ") and lineas[1].endswith(" s") and "n/d" not in lineas[1]


def test_main_con_error_de_voz(monkeypatch, capsys, sin_env):
    def crear_hablante(entorno, mostrar=print):
        raise voz.ErrorVoz("Falta ELEVENLABS_VOICE_ID en .env (JARVIS_VOZ_MOTOR=elevenlabs).")

    monkeypatch.setattr(habla, "crear_hablante", crear_hablante)
    assert mv.main(["--motor", "elevenlabs"]) == 1
    salida = capsys.readouterr()
    assert salida.err.startswith("No se pudo preparar la voz: Falta ELEVENLABS_VOICE_ID")
    assert "clave-de-mentira-123" not in salida.out + salida.err


def test_motor_desconocido_lo_rechaza_argparse(sin_env):
    with pytest.raises(SystemExit) as e:
        mv.main(["--motor", "piper"])
    assert e.value.code == 2
