"""Pipeline smoke test, not game logic."""

import sys


def main():
    args = sys.argv[1:]
    formats = {
        "text": "Game Development OS pipeline: v1 (text)",
        "json": '{"pipeline": "Game Development OS", "version": "v1"}',
    }

    fmt = "text"
    if args:
        parts = args[0].split("=", 1)
        if len(parts) != 2 or parts[0] != "--format":
            print(f"error: unrecognized argument: {args[0]}", file=sys.stderr)
            sys.exit(1)
        fmt = parts[1]

    if fmt not in formats:
        print(f"error: unsupported --format value: {fmt!r}", file=sys.stderr)
        sys.exit(1)

    print(formats[fmt])


if __name__ == "__main__":
    main()
