import os
import subprocess
import urllib.request

import pytest


def _prohibido(*args, **kwargs):
    raise AssertionError("un test intentó una acción real (app, proceso o red)")


@pytest.fixture(autouse=True)
def sin_efectos_reales(monkeypatch):
    """Red de seguridad: ningún test abre apps reales, lanza procesos ni sale a la red."""
    monkeypatch.setattr(os, "startfile", _prohibido, raising=False)  # raising=False: startfile solo existe en Windows
    monkeypatch.setattr(urllib.request, "urlopen", _prohibido)
    monkeypatch.setattr(subprocess, "run", _prohibido)
