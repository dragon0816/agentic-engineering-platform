# fix-run-007: findings

Re-verification on the current build: AEP `f69ee2c`, with these changes since fix-run-006:
- 20 tool calls per turn and the tool record;
- several tool calls per reply;
- the Edge and desktop tools with their fixes;
- coding Skill 1.6.0;
- the retry of a reply cut at the output limit.

Validator 1.3, with the same fixtures and prompts.

Result: **20 PASS of 20**, the second full pass in a row (fix-run-006 was the first). Interventions were the same kind as in fix-run-006: approve-button presses for T09 and T20, T09's second scenario, and T20's scripted threshold answer.
