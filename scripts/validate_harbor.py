"""Run real Harbor oracle/nop trials and reject infrastructure failures."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
results = []
for agent, expected in (("oracle", 1.0), ("nop", 0.0)):
    name = f"session-recovery-{agent}-{stamp}"
    subprocess.run([
        "uv", "run", "--frozen", "harbor", "run", "--path", "session-recovery",
        "--agent", agent, "--env", "docker", "--job-name", name,
        "--jobs-dir", "logs/harbor",
    ], cwd=ROOT, check=True)
    path = ROOT / "logs/harbor" / name / "result.json"
    result = json.loads(path.read_text())
    stats = result["stats"]
    assert stats["n_completed_trials"] == 1, result
    assert stats["n_errored_trials"] == 0, result
    evaluation, = stats["evals"].values()
    assert evaluation["n_errors"] == 0, evaluation
    rewards = evaluation["reward_stats"]["reward"]
    assert set(rewards) == {str(expected)}, rewards
    results.append({"agent": agent, "reward": expected, "errors": 0,
                    "result": str(path.relative_to(ROOT))})
    print(f"{agent}: expected reward {expected}, no infrastructure errors", flush=True)
(ROOT / "logs/validation-harbor.json").write_text(json.dumps(results, indent=2) + "\n")
