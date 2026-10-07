# fix-run-013: 19 of 20

Build: Agent Web on `db38f28`, the same build as lab fix-010.

**T13 FAIL (Agent variance).**
- What the program got wrong: Phone C's detail page has no price. The program the Agent wrote picked up the `9` in its CPU name `Dim 9` and put it in Price, so Price was `9` (Currency `N/A`) instead of `N/A`.
- What was correct: every other requirement held, including the 500 page tried exactly 3 times, the error row, and `warnings.json`.
- History: T13 passed in fix-run-007, -009, -011 and -012.

No platform change follows. The phase gate (coding_v1 20 of 20 on the lab's build) is re-checked under a new run ID on the same build.
