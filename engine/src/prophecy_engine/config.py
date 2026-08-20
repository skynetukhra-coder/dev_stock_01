"""Runtime configuration with a safe default trading mode."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TradingMode(str, Enum):
    SIGNAL = "SIGNAL"
    PAPER = "PAPER"
    LIVE = "LIVE"


@dataclass(frozen=True)
class GrowwCredentials:
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    access_token: Optional[str] = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key or self.access_token)


@dataclass(frozen=True)
class EngineConfig:
    trading_mode: TradingMode = TradingMode.SIGNAL
    strategy_version: str = "0.1.0"
    groww: GrowwCredentials = GrowwCredentials()

    @classmethod
    def from_environment(cls) -> "EngineConfig":
        mode_str = os.getenv("TRADING_MODE", TradingMode.SIGNAL.value).upper()
        mode = TradingMode(mode_str)
        if mode is TradingMode.LIVE:
            raise ValueError("LIVE trading is disabled until a later accepted milestone")

        groww_creds = GrowwCredentials(
            api_key=os.getenv("GROWW_API_KEY") or None,
            api_secret=os.getenv("GROWW_API_SECRET") or None,
            access_token=os.getenv("GROWW_ACCESS_TOKEN") or None,
        )

        return cls(
            trading_mode=mode,
            strategy_version=os.getenv("STRATEGY_VERSION", "0.1.0"),
            groww=groww_creds,
        )
