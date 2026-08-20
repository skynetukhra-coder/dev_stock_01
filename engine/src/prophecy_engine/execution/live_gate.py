"""Live broker safety guardrails, multi-key authorization and 6-lock safety gate."""

from __future__ import annotations

import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from ..broker.protocols import (
    BrokerOrderResponse,
    OrderExecutionProvider,
    OrderRequest,
    OrderStatus,
    Position,
    Quote,
)
from ..domain.models import Signal
from ..market.sessions import IST, to_ist
from ..risk.manager import RiskContext


class LiveTradingDisabledError(RuntimeError):
    """Raised when any live broker safety gate lock fails."""

    pass


@dataclass(frozen=True)
class ConfirmationToken:
    """Cryptographic single-use token granting temporary authorization to place a live order."""

    token_id: str
    signal_id: str
    symbol: str
    operator_id: str
    created_at: datetime
    nonce: str
    ttl_seconds: int = 60

    def is_expired(self, current_time: Optional[datetime] = None) -> bool:
        """Check whether the confirmation token has exceeded its TTL."""
        now = to_ist(current_time or datetime.now(IST))
        token_time = to_ist(self.created_at)
        return (now - token_time) > timedelta(seconds=self.ttl_seconds)


@dataclass(frozen=True)
class LiveSafetyConfig:
    """Configuration and hard safety limits for live broker execution."""

    execution_mode_env_key: str = "PROPHECY_EXECUTION_MODE"
    ack_env_key: str = "PROPHECY_LIVE_TRADING_ACKNOWLEDGED"
    operator_sig_env_key: str = "PROPHECY_OPERATOR_SIGNATURE"
    max_order_quantity: int = 100  # Hard ceiling: max 100 units (4 lots)
    max_order_notional: float = 35000.0  # Hard ceiling: max ₹35,000 per order
    max_price_deviation_pct: float = 0.10  # Fat-finger limit: 10% max deviation from quote LTP
    token_ttl_seconds: int = 60  # 60s confirmation token window


@dataclass(frozen=True)
class LiveOrderValidationResult:
    """Audit outcome of live safety gate evaluation."""

    is_valid: bool
    failed_locks: tuple[str, ...] = ()
    message: str = ""


class LiveSafetyGate:
    """Enforces 6 mandatory safety locks before permitting real broker order submission."""

    def __init__(self, config: Optional[LiveSafetyConfig] = None) -> None:
        self.config = config or LiveSafetyConfig()
        self._active_tokens: dict[str, ConfirmationToken] = {}
        self._consumed_tokens: set[str] = set()

    def generate_confirmation_token(
        self,
        signal: Signal,
        operator_id: str = "operator",
        timestamp: Optional[datetime] = None,
    ) -> ConfirmationToken:
        """Generate a cryptographically random, timestamped single-use confirmation token."""
        now = to_ist(timestamp or datetime.now(IST))
        token = ConfirmationToken(
            token_id=f"tok-{uuid.uuid4().hex[:12]}",
            signal_id=signal.id,
            symbol=signal.symbol,
            operator_id=operator_id,
            created_at=now,
            nonce=secrets.token_hex(16),
            ttl_seconds=self.config.token_ttl_seconds,
        )
        self._active_tokens[token.token_id] = token
        return token

    def verify_live_order(
        self,
        order_request: OrderRequest,
        quote: Quote,
        token: Optional[ConfirmationToken],
        context: Optional[RiskContext] = None,
        is_kill_switch_active: bool = False,
        env_vars: Optional[dict[str, str]] = None,
        current_time: Optional[datetime] = None,
    ) -> LiveOrderValidationResult:
        """Evaluate live order against all 6 safety locks."""
        env = env_vars if env_vars is not None else os.environ
        now = to_ist(current_time or datetime.now(IST))
        failed: list[str] = []
        messages: list[str] = []

        # -------------------------------------------------------------
        # Lock 1: Multi-Key Environment Authorization
        # -------------------------------------------------------------
        exec_mode = env.get(self.config.execution_mode_env_key, "").upper()
        ack = env.get(self.config.ack_env_key, "").upper()
        sig = env.get(self.config.operator_sig_env_key, "").strip()

        if exec_mode != "LIVE":
            failed.append("LOCK_1_ENV_MODE_NOT_LIVE")
            messages.append(f"{self.config.execution_mode_env_key} must be 'LIVE'")

        if ack != "TRUE":
            failed.append("LOCK_1_LIVE_TRADING_NOT_ACKNOWLEDGED")
            messages.append(f"{self.config.ack_env_key} must be 'TRUE'")

        if not sig:
            failed.append("LOCK_1_OPERATOR_SIGNATURE_MISSING")
            messages.append(f"{self.config.operator_sig_env_key} is required")

        # -------------------------------------------------------------
        # Lock 2: Emergency Kill Switch Check
        # -------------------------------------------------------------
        if is_kill_switch_active:
            failed.append("LOCK_2_KILL_SWITCH_ACTIVE")
            messages.append("Emergency kill switch is currently active")

        # -------------------------------------------------------------
        # Lock 3: Single-Use Confirmation Token Verification
        # -------------------------------------------------------------
        if token is None:
            failed.append("LOCK_3_CONFIRMATION_TOKEN_MISSING")
            messages.append("Missing required confirmation token")
        else:
            if token.token_id not in self._active_tokens:
                failed.append("LOCK_3_CONFIRMATION_TOKEN_UNRECOGNIZED")
                messages.append("Token not found in active registry")
            elif token.token_id in self._consumed_tokens:
                failed.append("LOCK_3_CONFIRMATION_TOKEN_REPLAYED")
                messages.append("Token has already been consumed")
            elif token.is_expired(now):
                failed.append("LOCK_3_CONFIRMATION_TOKEN_EXPIRED")
                messages.append(f"Token expired (> {token.ttl_seconds}s)")

        # -------------------------------------------------------------
        # Lock 4: Hard Quantity Ceiling
        # -------------------------------------------------------------
        if order_request.quantity > self.config.max_order_quantity:
            failed.append("LOCK_4_QUANTITY_CEILING_EXCEEDED")
            messages.append(
                f"Order quantity ({order_request.quantity}) exceeds live ceiling "
                f"({self.config.max_order_quantity})"
            )

        # -------------------------------------------------------------
        # Lock 5: Live Order Notional Ceiling
        # -------------------------------------------------------------
        est_price = order_request.price if order_request.price is not None else quote.ltp
        order_notional = est_price * order_request.quantity
        if order_notional > self.config.max_order_notional:
            failed.append("LOCK_5_NOTIONAL_CEILING_EXCEEDED")
            messages.append(
                f"Order notional (₹{order_notional:.2f}) exceeds live ceiling "
                f"(₹{self.config.max_order_notional:.2f})"
            )

        # -------------------------------------------------------------
        # Lock 6: Fat-Finger Price Sanity Deviation Check
        # -------------------------------------------------------------
        if quote.ltp > 0 and order_request.price is not None:
            dev_pct = abs(order_request.price - quote.ltp) / quote.ltp
            if dev_pct > self.config.max_price_deviation_pct:
                failed.append("LOCK_6_FAT_FINGER_PRICE_DEVIATION")
                messages.append(
                    f"Price ₹{order_request.price:.2f} deviates {dev_pct:.1%} from quote LTP "
                    f"₹{quote.ltp:.2f} (max allowed {self.config.max_price_deviation_pct:.1%})"
                )

        if failed:
            return LiveOrderValidationResult(
                is_valid=False,
                failed_locks=tuple(failed),
                message="; ".join(messages),
            )

        # Consume token on success to guarantee single-use
        if token is not None:
            self._consumed_tokens.add(token.token_id)
            if token.token_id in self._active_tokens:
                del self._active_tokens[token.token_id]

        return LiveOrderValidationResult(
            is_valid=True,
            failed_locks=(),
            message="Live order successfully passed all 6 security locks",
        )


class LiveBrokerAdapter(OrderExecutionProvider):
    """Guarded live broker adapter wrapping real broker API with LiveSafetyGate."""

    def __init__(
        self,
        underlying_adapter: OrderExecutionProvider,
        safety_gate: LiveSafetyGate,
    ) -> None:
        self.underlying_adapter = underlying_adapter
        self.safety_gate = safety_gate

    def place_order(
        self,
        request: OrderRequest,
        quote: Optional[Quote] = None,
        token: Optional[ConfirmationToken] = None,
        context: Optional[RiskContext] = None,
        is_kill_switch_active: bool = False,
        env_vars: Optional[dict[str, str]] = None,
        current_time: Optional[datetime] = None,
    ) -> BrokerOrderResponse:
        """Place live order after strict 6-lock verification."""
        now = to_ist(current_time or datetime.now(IST))
        live_quote = quote or Quote(
            groww_symbol=request.groww_symbol,
            ltp=request.price or 100.0,
            timestamp=now,
        )

        val_result = self.safety_gate.verify_live_order(
            order_request=request,
            quote=live_quote,
            token=token,
            context=context,
            is_kill_switch_active=is_kill_switch_active,
            env_vars=env_vars,
            current_time=now,
        )

        if not val_result.is_valid:
            raise LiveTradingDisabledError(
                f"Live order rejected by safety gate: {val_result.message}"
            )

        return self.underlying_adapter.place_order(request)

    def cancel_order(self, order_id: str) -> bool:
        return self.underlying_adapter.cancel_order(order_id)

    def get_order_status(self, order_id: str) -> OrderStatus:
        return self.underlying_adapter.get_order_status(order_id)

    def get_positions(self) -> list[Position]:
        return self.underlying_adapter.get_positions()
