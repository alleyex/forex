import sys

try:
    from forex.app.entrypoints.train import main
except ModuleNotFoundError as exc:
    print(
        "Module not found. Recommended usage:\n"
        "  1) Install the package (e.g. `pip install -e .[ui]`) and run the CLI:\n"
        "     `forex-train`\n"
        "  2) Or run with PYTHONPATH=src:\n"
        "     `PYTHONPATH=src python -m forex.app.entrypoints.train`\n",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


if __name__ == "__main__":
    sys.exit(main())
