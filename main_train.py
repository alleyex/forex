import sys

try:
    from app.entrypoints.train import main
except ModuleNotFoundError as exc:
    print(
        "Module not found. Recommended usage:\n"
        "  1) Install the package (e.g. `pip install -e .[ui]`) and run `forex-train`\n"
        "  2) Or run with PYTHONPATH=src, e.g. `PYTHONPATH=src python -m app.entrypoints.train`\n",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


if __name__ == "__main__":
    sys.exit(main())
