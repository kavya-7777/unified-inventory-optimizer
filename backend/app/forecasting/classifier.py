"""
Demand Classifier.
Classifies a demand series into an inventory demand pattern,
which determines which forecasting model is most appropriate.
"""
import numpy as np
from enum import Enum
from typing import List


class DemandPattern(str, Enum):
    SMOOTH = "smooth"          # Regular, low-variability demand → ETS/ARIMA
    INTERMITTENT = "intermittent"  # Frequent zeros → Croston
    LUMPY = "lumpy"            # Sporadic, high variability → Croston variant
    ERRATIC = "erratic"        # High variability, no zeros → ARIMA


def classify_demand(history: List[float]) -> DemandPattern:
    """
    Classifies demand using ADI (Average Demand Interval) and CV² (Squared Coefficient of Variation).
    
    ADI < 1.32 and CV² < 0.49 → Smooth
    ADI >= 1.32 and CV² < 0.49 → Intermittent
    ADI < 1.32 and CV² >= 0.49 → Erratic
    ADI >= 1.32 and CV² >= 0.49 → Lumpy
    """
    if not history or len(history) < 3:
        return DemandPattern.SMOOTH

    arr = np.array(history, dtype=float)
    nonzero = arr[arr > 0]

    if len(nonzero) == 0:
        return DemandPattern.INTERMITTENT

    # ADI: average interval between non-zero demands
    zero_count = np.sum(arr == 0)
    adi = len(arr) / max(len(nonzero), 1)

    # CV²: squared coefficient of variation of non-zero demands
    mean_nz = np.mean(nonzero)
    std_nz = np.std(nonzero)
    cv2 = (std_nz / mean_nz) ** 2 if mean_nz > 0 else 0.0

    if adi < 1.32 and cv2 < 0.49:
        return DemandPattern.SMOOTH
    elif adi >= 1.32 and cv2 < 0.49:
        return DemandPattern.INTERMITTENT
    elif adi < 1.32 and cv2 >= 0.49:
        return DemandPattern.ERRATIC
    else:
        return DemandPattern.LUMPY
