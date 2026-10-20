"""Shared pytest fixtures.

The pipeline CLIs write to a relative ``.output/`` directory. Tests that
exercise those CLIs must therefore run inside an isolated working directory
that already contains the canonical ``simple_room.dxf`` stage outputs.
Without this isolation the suite only passed when a previous run had left
``.output/`` behind, which is why CI (a clean checkout) was red.
"""
import pytest

from tests.helpers import build_canonical_workspace


@pytest.fixture()
def canonical_workspace(tmp_path):
    """Isolated workspace with parse -> semantic -> materials outputs for simple_room.dxf."""
    return build_canonical_workspace(tmp_path)
