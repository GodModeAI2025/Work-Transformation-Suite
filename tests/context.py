"""Gemeinsamer Kontext der Testsuite: Pfade und Importe der Skill-Skripte.

Die Skripte der Suite sind bewusst eigenständig und kennen einander nicht über
Paketimporte — jeder Skill ist einzeln installierbar. Für die Tests werden sie
deshalb hier gezielt über ihren Pfad geladen.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

ROOT = HERE.parent
SKILLS = ROOT / "skills"
EXAMPLE = ROOT / "examples" / "order-to-cash"

# workgraph_lib ist in jedem Skill identisch; die Tests nehmen die Quelle im Orchestrator.
sys.path.insert(0, str(SKILLS / "work-transformation" / "scripts"))
sys.path.insert(0, str(SKILLS / "work-graph-builder" / "scripts"))
sys.path.insert(0, str(SKILLS / "process-redesigner" / "scripts"))

import workgraph_lib as wl  # noqa: E402
import validate_graph  # noqa: E402


def load(skill: str, module: str):
    """Ein Skript eines Skills als Modul laden, ohne die Skills zu koppeln."""
    path = SKILLS / skill / "scripts" / f"{module}.py"
    name = f"_{skill.replace('-', '_')}_{module}"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(mod)
    return mod


def script(skill: str, name: str) -> Path:
    return SKILLS / skill / "scripts" / f"{name}.py"
