# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Sphinx configuration for pylocal-akuvox documentation."""

import importlib.metadata

project = "pylocal-akuvox"
author = "Andrew Grimberg"
copyright = "2026, Andrew Grimberg"  # noqa: A001

try:
    release = importlib.metadata.version("pylocal-akuvox")
except importlib.metadata.PackageNotFoundError:
    release = "0.0.0"
version = ".".join(release.split(".")[:2])

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
    "sphinx_copybutton",
]

templates_path = []
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for autodoc -----------------------------------------------------

autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_class_signature = "separated"
always_use_bars_union = True
typehints_use_signature = False

# -- Options for HTML output -------------------------------------------------

html_theme = "furo"
html_title = "pylocal-akuvox"
html_static_path = ["_static"]

html_theme_options = {
    "source_repository": "https://github.com/tykeal/pylocal-akuvox",
    "source_branch": "main",
    "source_directory": "docs/",
}

# -- Options for intersphinx -------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "aiohttp": ("https://docs.aiohttp.org/en/stable/", None),
}
