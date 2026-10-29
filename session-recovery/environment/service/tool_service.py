"""Durable stand-in for an external deployment API. Do not modify for the task.

execute(path, key, name, arguments) atomically commits a side effect and receipt.
Reusing a key returns the receipt, but mismatched payloads raise ValueError.
lookup(path, key) returns a committed receipt or None. Side effects are not
rolled back when the caller dies. No model, network, or timing dependencies.
"""
import json
import sqlite3


def connect(path):
    db = sqlite3.connect(path)
    db.execute("PRAGMA synchronous=FULL")
    db.execute("CREATE TABLE IF NOT EXISTS effects (seq INTEGER PRIMARY KEY, "
               "key TEXT UNIQUE, name TEXT, arguments TEXT, receipt TEXT)")
    return db


def lookup(path, key):
    with connect(path) as db:
        row = db.execute("SELECT receipt FROM effects WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None


def execute(path, key, name, arguments):
    payload = json.dumps(arguments, sort_keys=True)
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT name, arguments, receipt FROM effects WHERE key=?",
                         (key,)).fetchone()
        if row:
            if row[:2] != (name, payload):
                raise ValueError("idempotency key reused with a different request")
            return json.loads(row[2])
        seq = db.execute("SELECT COUNT(*) FROM effects").fetchone()[0] + 1
        receipt = {"sequence": seq, "operation_id": key, "name": name,
                   "arguments": arguments, "status": "committed"}
        db.execute("INSERT INTO effects VALUES (?, ?, ?, ?, ?)",
                   (seq, key, name, payload, json.dumps(receipt)))
        return receipt
