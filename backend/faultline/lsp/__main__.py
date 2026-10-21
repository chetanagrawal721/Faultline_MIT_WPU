"""python -m faultline.lsp: the language server over stdio. Protocol frames go to stdout; every log line goes to stderr."""
import logging
import sys

from .server import build_server


def main() -> int:
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    server = build_server()
    server.start_io()
    return 0 if server.shut_down else 1             # `exit` without a prior `shutdown` is an error exit


if __name__ == "__main__":
    sys.exit(main())
