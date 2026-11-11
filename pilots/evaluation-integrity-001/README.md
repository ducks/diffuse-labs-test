# Evaluation integrity pilots

Three independent attempts used the task at commit `f29477c` and low
reasoning effort. Codex ran in Harbor with web search disabled. Claux ran
Particle-1 via OpenRouter with a 600-second limit and a 100-round cap.

| Harness | Model | Attempt | Reward | Agent time | Reported cost |
| --- | --- | ---: | ---: | ---: | ---: |
| Codex 0.164.0 via Harbor 0.25.0 | `openai/gpt-6.1-sol` | 1 | 1.0 | 84.64 s | USD 0.0537 |
| Codex 0.164.0 via Harbor 0.25.0 | `openai/gpt-6.1-sol` | 2 | 1.0 | 77.40 s | USD 0.0513 |
| Claux via OpenRouter | `particle-ai/particle-1` | 1 | 1.0 | 92.75 s | USD 0.0092 |

Each agent started with the public task files in a fresh container. Grading
used the protected verifier in a separate container and collected only
`pipeline.py` from each submission. The Claux run used the same starter image
and an offline Docker grader. Agent times exclude setup and grading.
Codex costs are Harbor estimates. Particle cost is provider-reported.

3 of 3 submissions earned full reward on the unseen fixtures. Difficulty
remains uncalibrated because the sample is small and the harnesses and
budgets differ.

[Result summary](result-summary.json) records result and submission hashes.
Raw transcripts and agent submissions are retained locally.
