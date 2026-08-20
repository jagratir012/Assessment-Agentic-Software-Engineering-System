"""
Code Validator tool - performs basic validation on generated code.
"""

from __future__ import annotations

import ast
import logging

from ..models.schemas import CodeArtifact

logger = logging.getLogger(__name__)


class CodeValidator:
    """Validates generated code for basic correctness."""

    def validate_python(self, artifact: CodeArtifact) -> dict:
        """
        Validate Python code by parsing AST.
        Returns validation result with any syntax errors.
        """
        if artifact.language != "python":
            return {"valid": True, "message": "Non-Python file, skipping AST check"}

        try:
            ast.parse(artifact.content)
            return {"valid": True, "message": "Python syntax valid"}
        except SyntaxError as e:
            return {
                "valid": False,
                "message": f"Syntax error at line {e.lineno}: {e.msg}",
            }

    def validate_all(self, artifacts: list[CodeArtifact]) -> list[dict]:
        """Validate all artifacts, return list of results."""
        results = []
        for artifact in artifacts:
            result = self.validate_python(artifact)
            result["file"] = artifact.filename
            results.append(result)
            if result["valid"]:
                logger.info(f"✓ {artifact.filename}: valid")
            else:
                logger.warning(f"✗ {artifact.filename}: {result['message']}")
        return results
