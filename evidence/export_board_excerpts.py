#!/usr/bin/env python3
"""Export verbatim seat-board excerpts from the T2Helix chronicle.

Standing consequence 13: the correspondence that produced ECS decisions is
preserved under `evidence/board_excerpts/` with a per-file hash manifest, so
the record is auditable **without a live chronicle database**. The chronicle is
a local SQLite file on one machine; a reviewer reading the repo three years
from now will not have it, and every "board #NNNNN" citation in SPEC.md,
PREREG.md and the limitations notes would resolve to nothing.

The first export was done by hand on 2026-08-04 and stopped at #13840. The
entire fail-closed round, LN-7, both supersessions and every counter-signature
after that date were unarchived — which is how a manual export fails: not
loudly, but by quietly falling behind while the citations keep accumulating.
This script exists so the archive can be brought current in one command
instead.

VERBATIM MEANS VERBATIM. Content is written byte-identical to the chronicle
entry: no editing, truncation, reformatting or redaction. The sha256 in the
manifest is of the exported file, so any later alteration is detectable. An
excerpt archive that had been tidied would be worth less than none, because it
would look like evidence.

Idempotent: re-running rewrites the same bytes for entries already present and
adds only what is new.

  python3 evidence/export_board_excerpts.py [--db PATH] [--dry-run]
"""
import hashlib, json, os, sqlite3, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "evidence", "board_excerpts")
DB_DEFAULT = os.path.expanduser(
    "~/.claude/plugins/data/t2helix-templetwo-t2helix/chronicle.db")

# Selection is by DOMAIN, not by hand-picked id. A hand-picked list is another
# thing that silently falls behind.
SELECT = """
  SELECT id, content, domain, layer, tags, created_at
  FROM insights
  WHERE domain LIKE '%conditioned-kernel%'
  ORDER BY id
"""


def main(argv):
    db = DB_DEFAULT
    if "--db" in argv:
        db = argv[argv.index("--db") + 1]
    dry = "--dry-run" in argv
    if not os.path.exists(db):
        print(f"CANNOT EVALUATE: no chronicle at {db}. Nothing exported, and "
              f"an empty archive is not a successful export.")
        return 2

    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute(SELECT).fetchall()
    os.makedirs(OUT, exist_ok=True)

    excerpts, added, unchanged = [], 0, 0
    for _id, content, domain, layer, tags, created in rows:
        # BYTE-FOR-BYTE. An earlier draft of this script appended a trailing
        # newline where the entry lacked one. That is a one-byte change and it
        # would have rewritten all 38 hand-exported files with new hashes,
        # invalidating every sha256 already recorded in MANIFEST.json. Caught
        # by dry-running and diffing against disk before writing, not by
        # reasoning about it. Verbatim means no normalisation at all — not
        # newlines, not whitespace, not encoding.
        raw = content.encode()
        # Zero-padded to 5, matching the hand export's convention (9934 ->
        # 09934.md) and its MANIFEST entries. Writing "9934.md" instead would
        # have left the original file in place and added a duplicate beside it,
        # so the archive would hold two copies of two entries and the manifest
        # would name only one of each. Found by dry-run accounting that did not
        # add up — 38 files on disk, only 36 reported byte-identical.
        name = f"{_id:05d}.md"
        path = os.path.join(OUT, name)
        exists = os.path.exists(path)
        if not exists or open(path, "rb").read() != raw:
            if not dry:
                open(path, "wb").write(raw)
            added += 1
        else:
            unchanged += 1
        try:
            tag_list = json.loads(tags) if tags else []
        except Exception:
            tag_list = [t for t in str(tags or "").split(",") if t]
        excerpts.append({"id": _id, "file": name, "domain": domain,
                         "layer": layer, "tags": tag_list,
                         "created_at_ms": created,
                         "sha256": hashlib.sha256(raw).hexdigest(),
                         "bytes": len(raw)})

    manifest = {
        "note": ("VERBATIM seat-board excerpts, exported unmodified from the "
                 "T2Helix chronicle. Content is byte-identical to the chronicle "
                 "entry; no editing, truncation, or reformatting. sha256 is of "
                 "the exported file. These are evidence of the correspondence "
                 "that produced ECS v1 decisions, preserved so the record is "
                 "auditable without a live chronicle database."),
        "exported_utc": time.strftime("%Y-%m-%d", time.gmtime()),
        "source": "T2Helix chronicle.db insights table",
        "selection": ("all entries whose domain contains 'conditioned-kernel', "
                      "by query rather than by hand-picked id, so the archive "
                      "cannot silently fall behind the citations"),
        "count": len(excerpts),
        "excerpts": excerpts}
    if not dry:
        json.dump(manifest, open(os.path.join(OUT, "MANIFEST.json"), "w"), indent=1)
    print(f"  {'DRY RUN — ' if dry else ''}{len(excerpts)} excerpts total "
          f"({added} written/updated, {unchanged} already byte-identical)")
    print(f"  id range {excerpts[0]['id']}..{excerpts[-1]['id']}" if excerpts else "")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
