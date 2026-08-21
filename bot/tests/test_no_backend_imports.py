"""Изоляция бота от бэкенда.

Бот — самостоятельный сервис и чистый клиент API: внутри bot/ запрещены любые
импорты кода бэкенда. Тест ловит регрессию связности на уровне импортов.
"""
import ast
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parents[1]

# Бэкенд живёт в пакете src — из бота он недоступен ни в каком виде.
FORBIDDEN_ROOTS = ("src",)


def iter_imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_bot_does_not_import_backend_modules():
    violations = []

    for path in BOT_DIR.rglob("*.py"):
        for module in iter_imports(path):
            if module.split(".")[0] in FORBIDDEN_ROOTS:
                violations.append(f"{path.relative_to(BOT_DIR)}: {module}")

    assert not violations, (
        "Бот должен ходить в бэкенд только через HTTP API, найдены импорты: "
        + ", ".join(violations)
    )


def test_bot_lives_outside_backend_package():
    """Бот — отдельный пакет в корне репозитория, а не часть src/."""
    assert BOT_DIR.name == "bot"
    assert BOT_DIR.parent == Path(__file__).resolve().parents[2]
    assert not (BOT_DIR.parent / "src" / "bot").exists()
