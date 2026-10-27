"""Importing this package registers every tool in REGISTRY."""
from . import api, browser, control, files  # noqa: F401
from .base import REGISTRY, specs  # noqa: F401
