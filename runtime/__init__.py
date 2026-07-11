"""ReasonScript runtime distribution package.

Runtime implementations currently live in the toolchain and frontend packages;
this package provides the stable installed-distribution boundary.
"""

from .data import DataBackend

__all__ = ["DataBackend"]
