"""Helpers for loading files from directory-style skill packages."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


ROOT_DIR = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT_DIR / "skills"


def get_skill_package_dir(skill_name: str) -> Path:
    return SKILLS_DIR / skill_name


def get_skill_asset_path(skill_name: str, *parts: str) -> Path:
    return get_skill_package_dir(skill_name).joinpath(*parts)


def read_skill_asset(skill_name: str, *parts: str) -> str:
    return get_skill_asset_path(skill_name, *parts).read_text(encoding="utf-8")


def load_skill_script(skill_name: str, script_name: str) -> ModuleType:
    script_path = get_skill_asset_path(skill_name, "scripts", script_name)
    module_name = f"_skill_{skill_name.replace('-', '_')}_{script_name.replace('.', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load skill script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

