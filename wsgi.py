import sys
import os
import types
import importlib.util

# ─── Self-register this directory as the 'backend' package ─────────────────
# When deployed to Render, all files are at the repo root (no backend/ subfolder).
# The internal modules use relative imports (from .config import ...) which require
# the package name 'backend' to be registered in sys.modules.
_root = os.path.dirname(os.path.abspath(__file__))

# Create 'backend' as a package pointing to the current directory
_backend_pkg = types.ModuleType('backend')
_backend_pkg.__path__ = [_root]
_backend_pkg.__package__ = 'backend'
sys.modules['backend'] = _backend_pkg

# Execute __init__.py into the backend package
_spec = importlib.util.spec_from_file_location(
    'backend',
    os.path.join(_root, '__init__.py'),
    submodule_search_locations=[_root]
)
_spec.loader.exec_module(_backend_pkg)
# ────────────────────────────────────────────────────────────────────────────

from backend import create_app
from backend.extensions import db
import backend.models  # noqa: F401 – ensures all models are registered

app = create_app()

# Create tables and upload folder on startup
with app.app_context():
    db.create_all()
    upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
