"""Adapter scaffold for switching the AML endpoint from mock mode to a real model.

Expected contract:
- init_model(): load model artifacts from AZUREML_MODEL_DIR or local files.
- predict(input_data): return a JSON-serializable dict with the same shape as the mock result.

The default implementation raises NotImplementedError so score.py can safely
fall back to mock mode until you replace the TODO blocks.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


MODEL = None
MODEL_DIR = Path(os.getenv("AZUREML_MODEL_DIR", Path(__file__).parent / "model_artifacts"))


def init_model() -> None:
    """Load your real model here.

    Example directions:
    1. Put model files under mock_model/model_artifacts/
    2. Add the required runtime dependencies to conda.yml
    3. Replace this body with real model loading logic
    """
    raise NotImplementedError(
        "Replace mock_model/real_model_adapter.py with real model loading logic."
    )


def predict(input_data: dict[str, Any]) -> dict[str, Any]:
    """Run real inference and return the normalized result payload.

    input_data currently contains:
    - blob_name: uploaded blob path/name
    - image_b64: base64 encoded image bytes
    """
    raise NotImplementedError(
        "Implement predict() to decode the image, run inference, and return the result."
    )