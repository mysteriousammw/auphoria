"""Fake ``google`` package (a namespace holder for google.colab in tests).

Local notebooks executed with nbclient need ``import google.colab`` to resolve
so the notebook's install/upload/download cells run outside Colab.
"""
from __future__ import annotations
