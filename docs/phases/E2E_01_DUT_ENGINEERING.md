# Product gate E2E-01 — physical DUT and chipset engineering

Status: automated simulator proof and company-host physical-validation entry
point implemented; owner hardware run and human evidence review pending

## User scenario

An engineer asks the resident Personal Agent to change a bounded DUT behavior in
an explicitly pinned workspace. The Agent uses an exact vendor Skill, the
existing Coding Harness plans and repairs the change, and an independent
simulator validates the new case plus regressions. A later, explicitly approved
request executes the same typed operation through an enrolled Bridge and a
host-configured physical driver. Measured state, rather than model confidence,
decides success. Human review is required before republishing.

## Minimum architecture

```text
Personal Agent -> Gateway -> Bridge -> DUT development capability
                                      -> existing Coding Harness
                                      -> simulator adapter + validator

operator evidence command -> enrolled Local Agent admission
                          -> Bridge physical-validation capability
                          -> fixed host driver executable (no shell)
                          -> measurement validator -> evidence JSON
```

The simulator and physical driver implement the same provider-neutral operation
and observation contracts. CI installs only the simulator. The company host
installs the physical capability only when trusted local configuration names an
absolute driver executable and explicitly enables hardware execution.

## Architecture guard

- Keep the resident Agent, Gateway, Bridge policy and Coding Harness. Do not add
  a second agent, workflow engine or device authorization path.
- Vendor procedures and command meaning live in an exact versioned Skill and the
  host driver. Core contracts describe identity, operations, measurements and
  evidence but contain no Qualcomm, MediaTek, Broadcom or Realtek commands.
- Physical commands are `external_side_effect`, require a Bridge grant and an
  approval reference, and are refused before adapter invocation when the actor,
  Bridge, device resource, Skill, driver or execution mode does not match.
- A Skill supplies procedure context but grants no execution permission.
- CI never enables the subprocess physical adapter. Recorded/simulated success
  remains explicitly insufficient for the production-like acceptance gate.
- Device evidence contains no credentials and binds Bridge, DUT, firmware,
  optional instrument, workspace revision, Skill version, command, observations
  and validator outcome.

## Source decision

The documented source repositories were searched for DUT, chipset, Qualcomm and
MediaTek implementations. No matching implementation was found. Decision:
**ADD** a small provider-neutral adapter boundary and reuse the current Harness,
Bridge, enrollment and policy components. Do not invent or migrate vendor
commands; a company-host driver supplies them later.

## Incremental slices

1. Define closed DUT target, operation, measurement-limit, observation,
   validation-evidence, development-result and human-review contracts.
2. Add simulator and fixed-executable physical adapter boundaries. The physical
   adapter uses an argument vector with `shell=False` and JSON over stdin/stdout.
3. Add a development service/capability that runs the existing bounded Harness,
   then validates the artifact through the simulator.
4. Add a physical-validation service/capability that checks the enrolled device,
   one-member rule, advertised local resources, exact Skill and host execution
   switch before invoking the adapter.
5. Add a company-host configuration and CLI evidence command that dispatches
   through the enrolled Agent and Bridge policy; emit reviewable JSON.
6. Prove the automated path and negative boundaries in CI with fixtures only.
   Build the Windows/Python 3.12 package and document the later owner hardware
   command without claiming the physical gate passed.

## Phase completion

The implementation slice is reviewable when the simulator green path and all
negative tests pass, the Windows package contains the physical-validation entry
point, and the handoff gives exact company-PC instructions. Product E2E-01 and
the five-gate milestone remain pending until the owner runs that package on an
enrolled Bridge with real DUT/instrument evidence and a human accepts it.

## Implemented evidence path

- `DutDevelopmentService` reuses the existing bounded `CodingHarness` and
  requires an injected simulator to pass the new case and regressions.
- `DutValidationService` independently grades finite typed measurements, units
  and expected state; adapter success alone is insufficient.
- `PhysicalDutValidationService` refuses actor, Bridge, Skill, target,
  instrument and availability mismatches before adapter invocation.
- `LocalAgent.execute_capability` provides an exact operator-selected path while
  retaining normal device admission and Bridge policy.
- `SubprocessDutAdapter` runs only the absolute executable in trusted host
  configuration, with fixed arguments, `shell=False` and typed JSON I/O.
- `aep-host dut-validate` retains the complete local outcome as JSON and exits
  successfully only for passing production-like physical evidence.
- The Windows preview includes a driver contract, Skill/request examples and a
  `dut-validate.cmd` launcher. It includes no vendor command implementation.

Automated coverage lives in `tests/test_product_e2e_01.py`,
`tests/test_dut_host.py` and the Windows bundle tests. Final product evidence
must come from the owner-run command in `deploy/windows-preview/README.md`.
