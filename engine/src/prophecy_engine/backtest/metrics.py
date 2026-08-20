"""Performance analytics, risk metrics calculation, and reporting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .models import BacktestTrade


@dataclass(frozen=True)
class BacktestMetrics:
    """Comprehensive performance statistics calculated from trade logs."""

    initial_capital: float
    final_capital: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    loss_rate: float
    profit_factor: float
    expectancy: float
    total_gross_pnl: float
    total_net_pnl: float
    total_costs: float
    avg_trade_pnl: float
    avg_win: float
    avg_loss: float
    max_drawdown_amount: float
    max_drawdown_pct: float
    avg_holding_duration_minutes: float
    case_breakdown: dict[int, dict[str, Any]]
    symbol_breakdown: dict[str, dict[str, Any]]
    daily_pnl: dict[str, float]


def calculate_metrics(
    trades: Sequence[BacktestTrade],
    initial_capital: float = 100000.0,
) -> BacktestMetrics:
    """Compute performance metrics from sequence of executed backtest trades."""
    if not trades:
        return BacktestMetrics(
            initial_capital=initial_capital,
            final_capital=initial_capital,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            loss_rate=0.0,
            profit_factor=0.0,
            expectancy=0.0,
            total_gross_pnl=0.0,
            total_net_pnl=0.0,
            total_costs=0.0,
            avg_trade_pnl=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            max_drawdown_amount=0.0,
            max_drawdown_pct=0.0,
            avg_holding_duration_minutes=0.0,
            case_breakdown={},
            symbol_breakdown={},
            daily_pnl={},
        )

    total_trades = len(trades)
    winning_trades = [t for t in trades if t.is_winner]
    losing_trades = [t for t in trades if not t.is_winner]

    n_win = len(winning_trades)
    n_loss = len(losing_trades)
    win_rate = (n_win / total_trades) * 100.0
    loss_rate = (n_loss / total_trades) * 100.0

    total_gross_pnl = sum(t.gross_pnl for t in trades)
    total_net_pnl = sum(t.net_pnl for t in trades)
    total_costs = sum(t.costs.total_cost for t in trades)
    final_capital = initial_capital + total_net_pnl

    gross_profit = sum(t.net_pnl for t in winning_trades)
    gross_loss = abs(sum(t.net_pnl for t in losing_trades))

    if gross_loss > 0:
        profit_factor = round(gross_profit / gross_loss, 2)
    else:
        profit_factor = 999.0 if gross_profit > 0 else 0.0

    avg_win = (gross_profit / n_win) if n_win > 0 else 0.0
    avg_loss = (gross_loss / n_loss) if n_loss > 0 else 0.0
    avg_trade_pnl = total_net_pnl / total_trades

    # Expectancy: (Win% * AvgWin) - (Loss% * AvgLoss)
    win_prob = n_win / total_trades
    loss_prob = n_loss / total_trades
    expectancy = (win_prob * avg_win) - (loss_prob * avg_loss)

    # Max Drawdown calculation using equity curve
    peak = initial_capital
    max_dd_amount = 0.0
    max_dd_pct = 0.0
    running_equity = initial_capital

    for t in trades:
        running_equity += t.net_pnl
        if running_equity > peak:
            peak = running_equity
        dd = peak - running_equity
        if dd > max_dd_amount:
            max_dd_amount = dd
            max_dd_pct = (dd / peak) * 100.0 if peak > 0 else 0.0

    avg_duration = sum(t.holding_duration_minutes for t in trades) / total_trades

    # Case Breakdown
    case_breakdown: dict[int, dict[str, Any]] = {}
    for case_num in range(1, 7):
        c_trades = [t for t in trades if t.case_number == case_num]
        if c_trades:
            c_wins = [t for t in c_trades if t.is_winner]
            c_net = sum(t.net_pnl for t in c_trades)
            case_breakdown[case_num] = {
                "trades": len(c_trades),
                "wins": len(c_wins),
                "win_rate": round((len(c_wins) / len(c_trades)) * 100.0, 1),
                "net_pnl": round(c_net, 2),
            }

    # Symbol Breakdown
    symbol_breakdown: dict[str, dict[str, Any]] = {}
    symbols = {t.symbol for t in trades}
    for sym in symbols:
        s_trades = [t for t in trades if t.symbol == sym]
        s_wins = [t for t in s_trades if t.is_winner]
        symbol_breakdown[sym] = {
            "trades": len(s_trades),
            "wins": len(s_wins),
            "win_rate": round((len(s_wins) / len(s_trades)) * 100.0, 1),
            "net_pnl": round(sum(t.net_pnl for t in s_trades), 2),
        }

    # Daily P&L Series
    daily_pnl: dict[str, float] = {}
    for t in trades:
        dt_str = t.entry_time.strftime("%Y-%m-%d")
        daily_pnl[dt_str] = round(daily_pnl.get(dt_str, 0.0) + t.net_pnl, 2)

    return BacktestMetrics(
        initial_capital=round(initial_capital, 2),
        final_capital=round(final_capital, 2),
        total_trades=total_trades,
        winning_trades=n_win,
        losing_trades=n_loss,
        win_rate=round(win_rate, 2),
        loss_rate=round(loss_rate, 2),
        profit_factor=round(profit_factor, 2),
        expectancy=round(expectancy, 2),
        total_gross_pnl=round(total_gross_pnl, 2),
        total_net_pnl=round(total_net_pnl, 2),
        total_costs=round(total_costs, 2),
        avg_trade_pnl=round(avg_trade_pnl, 2),
        avg_win=round(avg_win, 2),
        avg_loss=round(avg_loss, 2),
        max_drawdown_amount=round(max_dd_amount, 2),
        max_drawdown_pct=round(max_dd_pct, 2),
        avg_holding_duration_minutes=round(avg_duration, 1),
        case_breakdown=case_breakdown,
        symbol_breakdown=symbol_breakdown,
        daily_pnl=daily_pnl,
    )


def generate_markdown_report(metrics: BacktestMetrics) -> str:
    """Generate structured markdown summary of backtest performance."""
    ret_pct = ((metrics.final_capital - metrics.initial_capital) / metrics.initial_capital) * 100.0

    lines = [
        "# Prophecy Strategy Backtest Performance Report",
        "",
        "## Executive Summary",
        f"- **Initial Capital**: ₹{metrics.initial_capital:,.2f}",
        f"- **Final Capital**: ₹{metrics.final_capital:,.2f} ({ret_pct:+.2f}%)",
        f"- **Net P&L**: ₹{metrics.total_net_pnl:,.2f}",
        f"- **Total Transaction Costs & Taxes**: ₹{metrics.total_costs:,.2f}",
        f"- **Total Trades**: {metrics.total_trades} (Win Rate: {metrics.win_rate:.1f}%)",
        f"- **Profit Factor**: {metrics.profit_factor:.2f}",
        f"- **Expectancy**: ₹{metrics.expectancy:.2f} per trade",
        (
            f"- **Max Drawdown**: ₹{metrics.max_drawdown_amount:,.2f} "
            f"({metrics.max_drawdown_pct:.2f}%)"
        ),
        f"- **Avg Holding Duration**: {metrics.avg_holding_duration_minutes:.1f} min",
        "",
        "## Performance Metrics",
        "| Metric | Value |",
        "|---|---|",
        f"| Winning Trades | {metrics.winning_trades} |",
        f"| Losing Trades | {metrics.losing_trades} |",
        f"| Average Win | ₹{metrics.avg_win:,.2f} |",
        f"| Average Loss | ₹{metrics.avg_loss:,.2f} |",
        f"| Average Trade P&L | ₹{metrics.avg_trade_pnl:,.2f} |",
        "",
        "## Strategy Case Breakdown",
        "| Case # | Trades | Wins | Win Rate | Net P&L |",
        "|---|---|---|---|---|",
    ]

    for case_num in range(1, 7):
        if case_num in metrics.case_breakdown:
            c = metrics.case_breakdown[case_num]
            row = (
                f"| Case {case_num} | {c['trades']} | {c['wins']} | "
                f"{c['win_rate']:.1f}% | ₹{c['net_pnl']:,.2f} |"
            )
            lines.append(row)
        else:
            lines.append(f"| Case {case_num} | 0 | 0 | 0.0% | ₹0.00 |")

    lines.append("")
    lines.append("## Symbol Breakdown")
    lines.append("| Symbol | Trades | Wins | Win Rate | Net P&L |")
    lines.append("|---|---|---|---|---|")
    for sym, s in metrics.symbol_breakdown.items():
        row = (
            f"| {sym} | {s['trades']} | {s['wins']} | {s['win_rate']:.1f}% | ₹{s['net_pnl']:,.2f} |"
        )
        lines.append(row)

    return "\n".join(lines)
