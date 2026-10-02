# Executable Gateway task slice

Status: implementation slice approved by the owner's 2026-10-02 instruction to
continue through the next executable Agent/Orchestrator checkpoint. The Phase 0
repository audit and the backend/data/portable-contract slices are already
complete; this slice makes those contracts drive an explicit local task run.

## Scope and invariant

An admitted local member submits one exact `TaskContract` through the Host CLI.
The task uses the existing Gateway model backend and AEP's bounded conversation
loop. Only installed, read-side-effect capability commands explicitly named in
the task may appear as model tools; an empty allowlist is text-only. Bridge
grants still decide each attempted capability invocation. Slash commands and
existing Web conversation behavior are unchanged in this slice.

The Host checks the entire initial task request as `UNCLASSIFIED` against the
exact host-approved internal Gateway before selecting or calling the backend.
The existing `ApprovedModelClient` remains the final check on each complete
model request, including later tool observations. No native backend, implicit
fallback or JEV call is enabled.

The task's first supported output is one local `answer` artifact, checked by
the existing `CompletionValidator` after the Host writes actual response bytes
to an exclusive file under its workspace. A backend's `answered` status is only
a candidate result. The durable `TaskRunState` contains a digest, backend and
approval references, bounded event codes, artifact refs and validation result;
it contains no objective, answer bytes or model reasoning. A failed policy,
admission, artifact or validation check never reports a validated task.

## Contract and implementation sequence

1. Extend the Gateway conversation request with an optional exact tool-name
   allowlist and bounded turn count. The default remains the existing catalog
   and five-turn behavior. Verify hidden, workflow and invented calls cannot
   execute when an allowlist is supplied.
2. Add a Host-owned task executor that validates TaskContract scope and
   identity, constructs complete conservative pre-execution context, enforces
   Gateway data policy, persists each state transition, invokes the one exact
   backend, stores the answer artifact and validates it from the store.
3. Add `aep-host run-task --config ... --prompt ...` for a text-only answer
   task and `--task ...` for an explicit contract. Both use identical admission,
   policy, execution and validation; this is testable without a Web-only path.
4. Test policy denial before model/provider execution, read-only scope,
   host admission, successful and failed artifact validation, restart, no
   fallback, and unchanged ordinary conversation. Run focused and full checks,
   then update `TASKS.md` and `HANDOFF.md`.

This is intentionally a text/read-capability task slice. The result validator
proves only the task's declared nonempty or digest check, not semantic answer
quality. Backend transition remains disabled until the Host can enumerate and
re-authorize every material transferred in a portable resume package.
