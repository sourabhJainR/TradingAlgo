from __future__ import annotations

import typer

from tradingalgo.execution.broker import PaperBroker
from tradingalgo.execution.gateway import ExecutionGateway
from tradingalgo.risk.engine import RiskEngine, RiskLimits

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def run(mode: str = typer.Option("paper", help="backtest, paper, or live")) -> None:
    if mode not in {"backtest", "paper", "live"}:
        raise typer.BadParameter("mode must be backtest, paper, or live")
    if mode == "live":
        raise typer.BadParameter("live execution is not enabled in the bootstrap; add and validate a broker adapter first")
    gateway = ExecutionGateway(PaperBroker(), RiskEngine(RiskLimits()))
    typer.echo(f"TradingAlgo started in {mode} mode; execution gateway={type(gateway).__name__}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
