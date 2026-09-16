import pandas as pd
import pytest

from research.regime.detector import VolatilityDetector
from research.regime.models import VolatilityState


def test_volatility_detector_unknown_when_data_insufficient():
    frame = pd.DataFrame({"close": [100] * 50})

    result = VolatilityDetector().detect(frame)

    assert result.iloc[-1] == VolatilityState.UNKNOWN.value


def test_volatility_detector_missing_close():
    frame = pd.DataFrame({"open": [100] * 100})

    with pytest.raises(ValueError, match="close"):
        VolatilityDetector().detect(frame)
