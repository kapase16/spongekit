"""
spongekit_core
==============
Core package for SpongeKit v1.0.

Who this is for
---------------
This package is written so that a hydrologist who can read Python (but does not
live in code every day) can follow the logic. Every module focuses on a single,
clear responsibility and uses SI units:
- Rainfall depths in millimetres (mm)
- Areas in square metres (m²)
- Volumes in cubic metres (m³)

What this file does
-------------------
This file marks the folder as a Python package and defines what the package
exposes at import time. Keeping this minimal helps performance and avoids
importing heavy GIS libraries until needed.

Example
-------
>>> import spongekit_core as sk
>>> sk.__version__
'1.0.0'

"""

# Import only the light-weight version string here to avoid heavy imports.
from .version import __version__

# Public API surface (deliberately small at the package root). As we build the
# project, we may add a couple of simple helpers here. For now, just the version.
__all__ = ["__version__"]
