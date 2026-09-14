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


@app.command()
def web(host: str = typer.Option("127.0.0.1"), port: int = typer.Option(8080, min=1, max=65535)) -> None:
    """Start the research-only stock analysis web UI."""
    from tradingalgo.web.app import serve
    serve(host, port)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
