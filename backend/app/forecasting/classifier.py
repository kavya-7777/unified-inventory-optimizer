"""
Demand Classifier.
Classifies a demand series into an inventory demand pattern (Syntetos-Boylan scheme),
which determines which family of forecasting models is appropriate.
"""
from enum import Enum
from typing import Any, Dict, List

import numpy as np

ADI_CUTOFF = 1.32
CV2_CUTOFF = 0.49


class DemandPattern(str, Enum):
    SMOOTH = "smooth"              # Regular, low-variability demand
    INTERMITTENT = "intermittent"  # Frequent zeros, stable sizes
    LUMPY = "lumpy"                # Frequent zeros, highly variable sizes
    ERRATIC = "erratic"            # Few zeros, highly variable sizes


def demand_statistics(history: List[float]) -> Dict[str, Any]:
    """
    ADI (average demand interval) = periods / periods with demand.
    CV² = squared coefficient of variation of the non-zero demand sizes.

    ADI < 1.32 and CV² < 0.49 → Smooth
    ADI >= 1.32 and CV² < 0.49 → Intermittent
    ADI < 1.32 and CV² >= 0.49 → Erratic
    ADI >= 1.32 and CV² >= 0.49 → Lumpy
    """
    arr = np.asarray(history, dtype=float)
    nonzero = arr[arr > 0]
    stats: Dict[str, Any] = {
        "observations": int(arr.size),
        "mean": round(float(arr.mean()), 4) if arr.size else 0.0,
        "std": round(float(arr.std(ddof=1)), 4) if arr.size > 1 else 0.0,
        "zero_share": round(float((arr == 0).mean()), 4) if arr.size else 0.0,
        "adi": None,
        "cv2": None,
    }
    if arr.size < 3:
        return {**stats, "pattern": DemandPattern.SMOOTH.value}
    if nonzero.size == 0:
        return {**stats, "pattern": DemandPattern.INTERMITTENT.value}

    adi = arr.size / nonzero.size
    cv2 = float((nonzero.std() / nonzero.mean()) ** 2)
    if adi < ADI_CUTOFF:
        pattern = DemandPattern.SMOOTH if cv2 < CV2_CUTOFF else DemandPattern.ERRATIC
    else:
        pattern = DemandPattern.INTERMITTENT if cv2 < CV2_CUTOFF else DemandPattern.LUMPY
    return {**stats, "adi": round(adi, 4), "cv2": round(cv2, 4), "pattern": pattern.value}


def classify_demand(history: List[float]) -> DemandPattern:
    return DemandPattern(demand_statistics(history)["pattern"])
