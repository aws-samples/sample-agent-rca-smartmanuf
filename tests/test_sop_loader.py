"""Tests for SOP loader."""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))

from prompts.sop_loader import (
    load_sop,
    load_step1_sop,
    load_step2_sop,
    load_step3_sop,
)


class TestLoadSop:
    def test_load_step1_sop(self):
        content = load_step1_sop()
        assert "Problem Definition" in content
        assert "## Overview" in content
        assert "## Steps" in content
        assert "NEXUS" in content

    def test_load_step2_sop(self):
        content = load_step2_sop()
        assert "Root Cause Analysis" in content
        assert "potential causes" in content.lower()
        assert "NEXUS" in content

    def test_load_step3_sop(self):
        content = load_step3_sop()
        assert "Verification" in content
        assert "RETAINED" in content
        assert "ELIMINATED" in content
        assert "NEXUS" in content

    def test_invalid_sop_raises_error(self):
        with pytest.raises(FileNotFoundError):
            load_sop("nonexistent-sop")
