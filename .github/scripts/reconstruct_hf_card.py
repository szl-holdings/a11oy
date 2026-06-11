#!/usr/bin/env python3
"""Reconstruct the HuggingFace Space card exactly as hf-sync.yml would push it.

a11oy's hf-sync.yml does NOT mirror README.md verbatim to the Space card. It:
  1. strips any leading front-matter from the GitHub README body,
  2. prepends a fixed Space front-matter block (the base64 ``FM_B64`` env declared
     in hf-sync.yml — required because the Space is ``sdk: docker``),
  3. injects a one-line "front-matter is required" HTML note,
  4. appends the (front-matter-stripped) body.

So a byte-for-byte README.md vs Space-card comparison would be permanently red.
The drift check (hf-drift-check.yml) uses this script to rebuild the same card the
sync would produce and compares THAT to the live Space card. ``FM_B64`` is read
straight out of hf-sync.yml so the two stay in lockstep; if hf-sync's transform
ever changes, update both this script and that workflow together.

Usage:
    reconstruct_hf_card.py <readme_path> <hf_sync_yml_path> <output_path>

Exits non-zero (so the caller can flag a reconstruct failure) if FM_B64 cannot be
found/decoded in hf-sync.yml.
"""
import base64
import re
import sys

# Mirrors the note string assembled in hf-sync.yml. Keep in lockstep with that
# workflow; the join below reproduces its exact concatenation (no space before
# the embedded newline, since hf-sync splits the literal mid-word at "by ").
NOTE = (
    "<!-- HF Space front-matter is REQUIRED (sdk: docker). Injected by "
    "hf-sync\n     so the Space builds the Dockerfile. Do not remove. -->\n\n"
)


def main(argv):
    if len(argv) != 4:
        print(
            "usage: reconstruct_hf_card.py <readme> <hf-sync.yml> <output>",
            file=sys.stderr,
        )
        return 2

    readme_path, sync_path, out_path = argv[1], argv[2], argv[3]

    with open(sync_path, "r", encoding="utf-8") as fh:
        sync = fh.read()

    m = re.search(r'FM_B64:\s*"([A-Za-z0-9+/=]+)"', sync)
    if not m:
        print("ERROR: FM_B64 not found in hf-sync.yml", file=sys.stderr)
        return 1
    try:
        fm = base64.b64decode(m.group(1)).decode("utf-8")
    except Exception as exc:  # noqa: BLE001 - any decode failure is fatal here
        print(f"ERROR: FM_B64 did not base64-decode to UTF-8: {exc!r}", file=sys.stderr)
        return 1

    front_matter = "---\n" + fm + "\n---\n"

    with open(readme_path, "r", encoding="utf-8") as fh:
        body = fh.read()
    # Strip any existing front-matter so we never double-stack a header
    # (identical logic to hf-sync.yml).
    if body.startswith("---"):
        segs = body.split("\n---", 2)
        if len(segs) >= 2:
            body = segs[-1].lstrip("\n")

    card = front_matter + NOTE + body

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(card)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
