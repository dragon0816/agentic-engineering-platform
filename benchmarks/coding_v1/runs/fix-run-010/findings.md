# fix-run-010: interrupted

Build `a8a4864`. T01 to T08 passed. The run stopped at T09: the Agent's reply quoted the task SOP line `Authorization: Bearer <token>`. Agent Web's stored-message check refused it as a credential, the request was dropped without a response, and the runner crashed (`RemoteDisconnected`). T09 to T20 were not run.

This is a platform defect, not an Agent failure. Conversation messages now redact such text instead of refusing it (see `docs/DECISIONS.md`, 2026-10-07). Re-verification uses a new run ID.
