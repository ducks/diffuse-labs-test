"""A minimal agent runner with a session recovery bug. See instruction.md."""
import argparse
import json
import os
from pathlib import Path
import sys
import uuid

import tool_service


def checkpoint(stage, index):
    if os.environ.get("RECOVERY_BARRIER") == f"{stage}:{index}":
        print(json.dumps({"checkpoint": stage, "index": index}), flush=True)
        sys.stdin.readline()


def save(path, state):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        json.dump(state, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def run(session, store, plan, session_id):
    path = Path(session)
    if path.exists():
        state = json.loads(path.read_text())
    else:
        state = {"session_id": session_id, "messages": [
            {"role": "user", "content": "Execute the release plan."}], "next": 0}
    if state["session_id"] != session_id:
        raise ValueError("session ID mismatch")
    # A saved call is a durable intent. Its ID is also the service's
    # idempotency key, so recovery must keep it even if execution was interrupted.
    if (state["next"] == len(plan) and state["messages"]
            and state["messages"][-1] == {"role": "assistant", "content": "Done"}):
        return
    while state["next"] < len(plan):
        index = state["next"]
        action = plan[index]
        if state["messages"] and state["messages"][-1].get("role") == "tool_call":
            call = state["messages"][-1]
            if (call["name"] != action["name"]
                    or call["arguments"] != action["arguments"]):
                raise ValueError("pending call does not match the plan")
        else:
            call = {"role": "tool_call", "id": uuid.uuid4().hex,
                    "name": action["name"], "arguments": action["arguments"]}
            state["messages"].append(call)
            save(path, state)
        checkpoint("before_effect", index)
        result = tool_service.lookup(store, call["id"])
        if result is None:
            result = tool_service.execute(store, call["id"], call["name"], call["arguments"])
        checkpoint("after_effect", index)
        state["messages"].append({"role": "tool_result", "call_id": call["id"],
                                  "result": result})
        state["next"] += 1
        save(path, state)
        checkpoint("after_save", index)
    state["messages"].append({"role": "assistant", "content": "Done"})
    save(path, state)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for field in ("session", "store", "plan", "session-id"):
        parser.add_argument("--" + field, required=True)
    args = parser.parse_args()
    run(args.session, args.store, json.loads(Path(args.plan).read_text()), args.session_id)
