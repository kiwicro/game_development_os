"""Pipeline smoke test, not game logic."""

import sys


def main():
    args = sys.argv[1:]
    fmt = "text"
    if args:
        fmt = args[0].split("=", 1)[1]

    formats = {
        "text": "Game Development OS pipeline: v1 (text)",
        "json": '{"pipeline": "Game Development OS", "version": "v1"}',
    }
    print(formats[fmt])


if __name__ == "__main__":
    main()
