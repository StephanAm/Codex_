#!/usr/bin/env python3
"""Export ~/.note_taker/notes.db to JSONL on stdout."""

import json
import sqlite3
import sys
from pathlib import Path

DB = Path.home() / ".note_taker" / "notes.db"

if len(sys.argv) > 1:
    DB = Path(sys.argv[1])

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# Notes
tags = {}
refs = {}
for row in conn.execute("SELECT nt.note_id, t.name FROM note_tags nt JOIN tags t ON t.id = nt.tag_id"):
    tags.setdefault(row[0], []).append(row[1])
for row in conn.execute('SELECT nr.note_id, r.name FROM note_references nr JOIN "references" r ON r.id = nr.reference_id'):
    refs.setdefault(row[0], []).append(row[1])

for note in conn.execute("SELECT * FROM notes"):
    d = dict(note)
    d["_type"] = "note"
    d["tags"] = tags.get(d["id"], [])
    d["references"] = refs.get(d["id"], [])
    print(json.dumps(d))

# Instance kinds
for kind in conn.execute("SELECT * FROM instance_kinds"):
    d = dict(kind)
    d["_type"] = "instance_kind"
    print(json.dumps(d))

# Instances
inst_refs = {}
for row in conn.execute('SELECT ir.instance_id, r.name FROM instance_references ir JOIN "references" r ON r.id = ir.reference_id'):
    inst_refs.setdefault(row[0], []).append(row[1])

kinds = {row["id"]: row["name"] for row in conn.execute("SELECT id, name FROM instance_kinds")}

for inst in conn.execute("SELECT * FROM instances"):
    d = dict(inst)
    d["_type"] = "instance"
    d["instance_kind_name"] = kinds.get(d["instance_kind_id"])
    d["references"] = inst_refs.get(d["id"], [])
    print(json.dumps(d))

conn.close()
