# Download and run TradingAlgo

TradingAlgo can be used either as a normal Python package or as a standalone executable. The standalone build does not require Python on the target machine.

## Standalone download

Tagged releases publish one ZIP bundle per supported platform:

- Linux x64
- Windows x64
- macOS x64
- macOS arm64

Each ZIP contains:

- the single-file TradingAlgo executable
- `QUICKSTART.md`
- a SHA-256 checksum file

Release assets are generated automatically from version tags. The release workflow also smoke-tests `--help` and `web --help` before publishing.

## First run

Extract the ZIP and run:

Linux/macOS:

```bash
./tradingalgo-<platform> web
```

Windows:

```powershell
.\tradingalgo-windows-x64.exe web
```

Open `http://127.0.0.1:8080` in your browser.

No Python installation is required for standalone bundles.

## Verify the download

Use the matching `.sha256` file with the platform's SHA-256 utility before running the executable.

## Python installation

For development or when a Python environment is preferred:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
```

For the research stack:

```bash
python -m pip install '.[research]'
```

## Important

TradingAlgo is advisory-only. Live brokerage execution is disabled. Provider credentials, where required, remain external configuration and are never packaged into the executable.
