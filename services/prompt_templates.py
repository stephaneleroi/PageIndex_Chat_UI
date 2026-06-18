"""Chargement des prompts externalisés (gabarits Jinja).

Les prompts qu'on *itère et qu'on évalue* (grounding, map de map-reduce,
décomposition) vivent dans `services/prompts/*.jinja`, séparés du code : un
diff de prompt devient lisible et l'A/B (cf. skill `evaluer-reponse-sourcee`)
plus simple. Les builders de prompt à flot de contrôle restent en Python et
interpolent ces gabarits via `render_prompt(...)`.
"""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_PROMPT_DIR = Path(__file__).parent / "prompts"
_env = Environment(
    loader=FileSystemLoader(str(_PROMPT_DIR)),
    undefined=StrictUndefined,      # une variable oubliée lève une erreur (pas un trou silencieux)
    trim_blocks=True, lstrip_blocks=True,   # conditionnels `{% if %}` sans blancs parasites
    keep_trailing_newline=True,
)


def render_prompt(name: str, **kwargs) -> str:
    """Rend le gabarit `services/prompts/<name>.jinja` avec les variables fournies."""
    return _env.get_template(f"{name}.jinja").render(**kwargs)
