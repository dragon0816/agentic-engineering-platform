# sample-002: findings

**Setup.**
- Agent Web was restarted at 17:32 on `c64a724`, with `engineering/rs-knowledge@1.0.2` bound (the new purpose). The build includes the synthesis limit of 4000 tokens with one retry, and the "say when Knowledge gave no answer" rule.
- It does not yet include `72af226`: facet credit, supported answers kept, the tool route using the harness Skill procedure, and Skill 1.5.0. Grader 1.1.
- Six foundation questions (Q1041–Q1091) failed at the end with `model_http_error` during a short gateway outage. A probe right after found the gateway working, and they were asked again with `--force`.

## Result against sample-001

| | sample-001 | sample-002 |
|---|---|---|
| Acceptable (PASS + INSUFFICIENT) | 64 | **75** |
| PASS | 31 | 34 |
| Knowledge not used (`none`) | 18 | **0** |
| SYSTEM_ERROR (synthesis cut off) | 8 | **0** |
| Direct route PASS | 22 of 34 | 19 of 34 |
| Tool route PASS | 9 of 58 | 15 of 76 |

The new vault purpose made the Agent consult Knowledge for every question, and the synthesis limit removed every cut-off.

The tool route is now most of the traffic, and it still passes only 1 in 5: 33 FAIL with `REASONING_GAP`, 28 INSUFFICIENT. Its Knowledge call still runs without the Skill procedure. That is what `72af226` changes, and sample-003 measures it.

The direct route moved from 22 to 19 PASS. That is within the run-to-run variance of the model and the reviewer, since the same build answers differently.
