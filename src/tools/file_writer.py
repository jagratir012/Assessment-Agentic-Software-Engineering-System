"""
File Writer tool - writes generated artifacts to disk.
"""

from __future__ import annotations

import os
import logging
from pathlib import Path

from ..models.schemas import CodeArtifact

logger = logging.getLogger(__name__)


class FileWriter:
    """Writes code artifacts to the output directory."""

    def __init__(self, output_dir: str = "output"):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def write_artifact(self, artifact: CodeArtifact) -> str:
        """Write a single code artifact to disk."""
        filepath = self._output_dir / artifact.filepath
        filepath.parent.mkdir(parents=True, exist_ok=True)

        filepath.write_text(artifact.content, encoding="utf-8")
        logger.info(f"Written: {filepath}")
        return str(filepath)

    def write_all(self, artifacts: list[CodeArtifact]) -> list[str]:
        """Write all artifacts and return list of written paths."""
        paths = []
        for artifact in artifacts:
            path = self.write_artifact(artifact)
            paths.append(path)
        return paths
