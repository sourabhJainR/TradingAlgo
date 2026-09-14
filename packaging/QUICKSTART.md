# TradingAlgo standalone artifact

This bundle is a self-contained TradingAlgo executable for the target operating system.

## Start the web application

Linux/macOS:

```bash
./tradingalgo web
```

Windows:

```powershell
.\tradingalgo.exe web
```

Then open `http://127.0.0.1:8080` in a browser.

## Check the command line

Linux/macOS:

```bash
./tradingalgo --help
```

Windows:

```powershell
.\tradingalgo.exe --help
```

## Data and credentials

The application does not require paid services for its core local functionality. Optional provider credentials can be supplied as environment variables when a configured provider requires them.

Do not put credentials in the bundle or source code.

## Advisory boundary

TradingAlgo is an analysis and advisory application. Live brokerage execution is disabled.

## Platform

Use the bundle matching your operating system and CPU architecture. The executable is built as a single-file application and does not require a Python installation.
