"""
SOP Loader Utility

Loads Agent SOPs from markdown files and provides them as system prompts.
"""

import os
from pathlib import Path
from functools import lru_cache

DEFAULT_SOP_DIR = Path(__file__).parent.parent / "sops"


@lru_cache(maxsize=10)
def load_sop(sop_name: str, sop_dir: Path | str | None = None) -> str:
    """Load an SOP from a markdown file and return it as a string."""
    if sop_dir is None:
        sop_dir = Path(os.environ.get("SOP_DIR", DEFAULT_SOP_DIR))
    else:
        sop_dir = Path(sop_dir)

    sop_path = sop_dir / f"{sop_name}.sop.md"

    if not sop_path.exists():
        raise FileNotFoundError(f"SOP not found: {sop_path}")

    return sop_path.read_text(encoding="utf-8")


def load_step1_sop(sop_dir: Path | str | None = None) -> str:
    return load_sop("step1-problem-definition", sop_dir)


def load_step2_sop(sop_dir: Path | str | None = None) -> str:
    return load_sop("step2-root-cause-analysis", sop_dir)


def load_step3_sop(sop_dir: Path | str | None = None) -> str:
    return load_sop("step3-verification", sop_dir)
