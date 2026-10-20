import importlib.util
from pathlib import Path

import pytest

from jarvis.llm import Respuesta

spec = importlib.util.spec_from_file_location(
    "medir_claude_cli", Path(__file__).parents[1] / "scripts" / "medir_claude_cli.py")
mc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mc)  # importar no llama a claude: la guardia de conftest lo impediría


class ClienteMedido:
    """Sustituye a ClienteClaudeCLI: responder emite un fragmento, y se anota cada paso."""

    def __init__(self, falla_en=None):
        self.pasos, self.al_texto, self.falla_en = [], None, falla_en

    def precalentar(self, sistema):
        self.pasos.append("precalentar")

    def responder(self, mensajes, herramientas, sistema):
        self.pasos.append("responder")
        if len(self.pasos) == self.falla_en:
            raise RuntimeError("roto")
        self.al_texto("hola")
        return Respuesta(texto="hola")

    def cerrar(self):
        self.pasos.append("cerrar")


def test_persistente_precalienta_mide_el_primero_y_los_siguientes_y_cierra(capsys, monkeypatch):
    monkeypatch.setattr(mc, "REPETICIONES", 2)
    cliente = ClienteMedido()
    mc.medir_persistente(cliente, espera=0)

    assert cliente.pasos == ["precalentar"] + ["responder"] * 3 + ["cerrar"]  # el 1.º y REPETICIONES siguientes
    salida = capsys.readouterr().out
    assert "persistente 1.º: primer texto" in salida
    assert "persistente siguientes (media): primer texto" in salida


def test_persistente_cierra_aunque_falle():
    cliente = ClienteMedido(falla_en=3)
    with pytest.raises(RuntimeError):
        mc.medir_persistente(cliente, espera=0)
    assert cliente.pasos[-1] == "cerrar"
