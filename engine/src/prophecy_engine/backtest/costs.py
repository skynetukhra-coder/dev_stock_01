"""Indian F&O transaction cost and slippage models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostBreakdown:
    """Itemized breakdown of taxes and regulatory fees for F&O trades."""

    brokerage: float
    stt: float
    exchange_charges: float
    gst: float
    sebi_charges: float
    stamp_duty: float
    total_cost: float


@dataclass(frozen=True)
class TransactionCostModel:
    """Calculates realistic transaction costs and statutory levies for Indian options trading."""

    brokerage_per_order: float = 20.0  # ₹20 flat brokerage per executed order
    stt_sell_rate: float = 0.000625  # 0.0625% on option sell turnover (STT)
    exchange_charge_rate: float = 0.0005  # 0.05% of turnover (NSE transaction fees)
    gst_rate: float = 0.18  # 18% GST on (Brokerage + Exchange Fees)
    sebi_turnover_rate: float = 0.000001  # ₹10 per crore (0.0001%)
    stamp_duty_buy_rate: float = 0.00003  # 0.003% on buy turnover

    def calculate_costs(
        self,
        buy_price: float,
        sell_price: float,
        quantity: int,
    ) -> CostBreakdown:
        """Calculate complete roundtrip cost for an option position."""
        buy_turnover = buy_price * quantity
        sell_turnover = sell_price * quantity
        total_turnover = buy_turnover + sell_turnover

        # 1. Brokerage: ₹20 on buy + ₹20 on sell
        brokerage = 2.0 * self.brokerage_per_order

        # 2. STT: charged only on sell side for options
        stt = sell_turnover * self.stt_sell_rate

        # 3. Exchange transaction charges
        exchange_charges = total_turnover * self.exchange_charge_rate

        # 4. GST on (brokerage + exchange charges)
        gst = (brokerage + exchange_charges) * self.gst_rate

        # 5. SEBI turnover charges
        sebi_charges = total_turnover * self.sebi_turnover_rate

        # 6. Stamp duty: charged only on buy side
        stamp_duty = buy_turnover * self.stamp_duty_buy_rate

        total = round(brokerage + stt + exchange_charges + gst + sebi_charges + stamp_duty, 2)

        return CostBreakdown(
            brokerage=round(brokerage, 2),
            stt=round(stt, 2),
            exchange_charges=round(exchange_charges, 2),
            gst=round(gst, 2),
            sebi_charges=round(sebi_charges, 2),
            stamp_duty=round(stamp_duty, 2),
            total_cost=total,
        )


@dataclass(frozen=True)
class SlippageModel:
    """Simulates market impact and execution slippage on entry and exit."""

    slippage_pct: float = 0.001  # 0.10% price slippage
    fixed_slippage_points: float = 0.0  # Optional fixed absolute points

    def apply_buy(self, price: float) -> float:
        """Simulate buy fill price (higher than market quote)."""
        return round(price * (1.0 + self.slippage_pct) + self.fixed_slippage_points, 2)

    def apply_sell(self, price: float) -> float:
        """Simulate sell fill price (lower than market quote)."""
        slipped = price * (1.0 - self.slippage_pct) - self.fixed_slippage_points
        return round(max(0.05, slipped), 2)
