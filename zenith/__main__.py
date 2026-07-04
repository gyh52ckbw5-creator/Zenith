import sys


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "web":
        import uvicorn

        uvicorn.run("zenith.server:app", host="0.0.0.0", port=8000)
    else:
        from .cli import main as cli_main

        cli_main()


if __name__ == "__main__":
    main()
