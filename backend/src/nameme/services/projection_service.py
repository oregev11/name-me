"""Projects name vectors into the pre-fit global 2D PCA space.

The PCA is fit once (in scripts/build_artifacts.py) on the full corpus and
loaded read-only here -- we only ever call `.transform()`, never `.fit()`,
so the coordinate space stays identical across every request and every
refine step in a session.
"""

from __future__ import annotations

import numpy as np
from sklearn.decomposition import PCA


def project_to_2d(pca: PCA, vectors: np.ndarray) -> list[tuple[float, float]]:
    coords = pca.transform(vectors)
    return [(float(x), float(y)) for x, y in coords]
