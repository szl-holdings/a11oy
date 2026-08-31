"""SENTRA forecasts package — witnessed forecasting with Mādhava error envelope.

Vendored from szl-holdings/sentra src/forecasts/ (Cursor PR #65, merged).
SPDX-License-Identifier: BSL-1.1
"""
from .witnessed import (
    forecast_with_madhava_bound,
    forecast_batch,
    WitnessedForecast,
    ConfidenceEnvelope,
    MADHAVA_THEOREM_REF,
    MADHAVA_FORMULA_ID,
)
