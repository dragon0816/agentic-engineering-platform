# fix-003 is invalid

The run was stopped after W03. Every `browser__operate` call, and every platform Workflow step that used `browser/operate`, failed with `profile_in_use`.

The cause was the operator's environment, not the Agent:
- The operator restarted Agent Web with `Stop-Process -Force`.
- The headless Edge the previous host process had started was never closed.
- That Edge kept the Agent's browser profile locked.

The Agent reported the error each time and fabricated nothing.

Fix: `browser/operate` now asks a leftover browser on its own profile to close and starts again, and the host closes its Edge on shutdown. Committed after this run. The tasks were rerun as fix-004.
