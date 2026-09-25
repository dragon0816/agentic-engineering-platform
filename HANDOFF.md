# Handoff — E2E-01 implementation ready; owner hardware evidence pending

Updated: 2026-09-25 (Asia/Taipei).
Branch: `main`.
Pull requests: #102 merged as `c700366d951c1a990f64a5cdcd37519f28529700`;
#103 merged as `60d5e18fb26f4331063eb7abd573037c9fd09a24`.
Verified heads: #102 `2e69de744a8cc349ee8a730ad2f439127d2104cf`;
#103 `98e529e07653751d769821bc173f88047cef13a6`.
CI runs: #102 `36080782267`; #103 `36081352644`; both successful.

Progress across all phases remains in `docs/TASKS.md`. This file is the current
stopping point. Product E2E-01 is **not complete** until the owner runs the
Windows package on an enrolled company Bridge with a real DUT/instrument and a
human accepts the resulting production-like evidence.

## Completed

- Added provider-neutral DUT, instrument, command, observation, deterministic
  measurement/state validation, evidence, development and human-review
  contracts under `src/dut/`.
- Reused the E2E-03 bounded `CodingHarness` for a DUT controller change. The
  development result is green only after the Harness repairs its deliberately
  failing candidate and an independent simulator passes the new case and
  regressions.
- Added a high-risk physical validation capability. It is
  `external_side_effect`, requires a permission, technical policy and approval
  reference, and does not derive authority from a Skill or publication.
- Added exact local capability execution through the existing resident Agent,
  device admission and Bridge policy. No parallel authorization path was added.
- Added company-host DUT configuration for an exact Skill, target/firmware,
  optional instrument, resource availability, fixed driver executable and an
  explicit `physical_enabled` switch.
- Added a fixed-executable subprocess adapter. It uses an absolute executable,
  fixed argument vector, `shell=False` and JSON over stdin/stdout. It contains
  no vendor command behavior and the request/model cannot choose the program.
- Added `aep-host dut-validate`, which saves the complete local outcome as JSON
  and exits zero only for passing production-like physical evidence.
- Added a Windows launcher, driver protocol, strict request example and
  versioned Skill example to the offline preview. The bundle still contains no
  vendor driver or vendor procedure.
- Added automated E2E and company-host coverage for simulator development,
  bounded repair, independent validation, unauthorized/wrong/unavailable
  refusal, secret rejection, simulated-evidence rejection, fixed process
  invocation, owner admission, Bridge policy and bundle contents.
- Updated architecture, contracts, roadmap, tasks, README and the E2E-01 phase
  record only after the automated implementation passed its focused tests.
- Corrected the preview's stale `doctor` limitation in PR #103 after a real
  offline install exposed the contradiction between the new provider-neutral
  DUT boundary and the absence of a bundled vendor driver.
- Built and installed the final merged Windows preview. `aep-host
  dut-validate --help`, `doctor`, and the corrected limitation all passed.

## In Progress

- None. Implementation and package integration are complete. Stop here until
  the owner performs the company-PC hardware run.

## Remaining

- The owner must provide the actual reviewed vendor Skill and a local driver
  that implements `deploy/windows-preview/DUT_DRIVER_CONTRACT.md`.
- On the enrolled company computer, configure the exact target, firmware,
  optional instrument, grant and `physical_enabled` switch, then run the shipped
  `dut-validate.cmd` against the edited request.
- Inspect `dut-evidence.json`. It must be `mode: physical`,
  `evidence_level: production_like`, `status: passed`, with every validator
  outcome passing. A human domain owner must then accept the evidence before a
  Skill or controller change is republished.
- Record that evidence and review in the repository. Only then change E2E-01
  and the five-gate product milestone to complete.

## Architecture and migration decisions

- **REUSE** the resident `LocalAgent`, Gateway, Bridge executor, local policy,
  enrollment/device admission and E2E-03 Coding Harness.
- **ADD** provider-neutral DUT contracts, an adapter protocol, independent
  validator, physical admission service and owner evidence CLI.
- **DO NOT MIGRATE** vendor behavior. The documented source repositories were
  searched for DUT, chipset, Qualcomm and MediaTek implementations and contained
  no matching implementation. Do not invent vendor commands in core.
- Vendor procedures live in an exact versioned Skill; low-level command behavior
  lives in the reviewed host driver. Neither one grants execution permission.
- CI may use simulator or recording adapters only. Their evidence is always
  `simulated`; it cannot satisfy `DutChangeReview` or the product gate.
- Physical execution is allowed only for the company workstation's bound owner,
  through normal Bridge policy, with exact Skill/resource identity and an
  explicit host enable switch. Refusals occur before driver invocation.
- Driver exit code does not decide validation. The platform compares typed
  units, measurement bounds and expected state. Out-of-limit evidence stays
  failed.
- Real credentials are never asset, request, driver-argument or evidence
  content. A driver resolves any required credential from its approved runtime
  environment.

## Exact verification commands and results

Local Windows/Python 3.12:

```text
.venv\Scripts\python.exe -m pytest tests\test_product_e2e_01.py tests\test_dut_host.py tests\test_windows_preview_bundle.py tests\test_weekly_report_documented_grants.py -q -p no:cacheprovider --basetemp .scratch\pytest-e2e01-final-focused
24 passed in 0.63s

.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_browser.py -p no:cacheprovider --basetemp .scratch\pytest-e2e01-final
1289 passed, 4 skipped in 33.34s

.venv\Scripts\python.exe -m ruff check .
All checks passed

.venv\Scripts\python.exe -m ruff format --check .
262 files already formatted

.venv\Scripts\python.exe -m mypy
Success: no issues found in 211 source files

.venv\Scripts\python.exe -m build --no-isolation --outdir .scratch\build-e2e01-final
Successfully built sdist and wheel

.venv\Scripts\python.exe -m pip check
No broken requirements found

git diff --check
passed
```

The four skips are existing host-dependent cases: two Windows link privilege
checks, IPv6 loopback availability and a directory-link privilege check. No
Ubuntu or Python 3.11 validation was run, per owner instruction.

A local full run reached 1299 passed and then reported nine existing browser
cases as failed/error because Edge exited without publishing its remote-debug
port. The DUT suites passed, and the complete non-browser regression is green.
The exact-head GitHub Windows workflows include the browser suite and offline
preview build/install. PR #102 run `36080782267` and PR #103 run `36081352644`
both passed before their exact heads were merged.

Final merged package verification:

```text
.venv\Scripts\python.exe -m build --no-isolation --outdir .scratch\build-e2e01-release
Successfully built sdist and wheel

.venv\Scripts\python.exe scripts\build_windows_preview.py --wheel .scratch\build-e2e01-release\agentic_engineering_platform-0.1.0-py3-none-any.whl --dependency-dir .scratch\e2e01-dependencies --output-dir dist --source-revision 60d5e18fb26f4331063eb7abd573037c9fd09a24
dist\aep-windows-preview-0.1.0-60d5e18fb26f.zip

Offline install with Python 3.12 passed; `aep-host dut-validate --help` and
`aep-host doctor` passed.
SHA256 6A14FDBECF62CD699EC5DBE1CF20BA29BC32345470F559C1B1FE8599BE4A6BDF
```

## Company-PC validation procedure

1. Copy `dist\aep-windows-preview-0.1.0-60d5e18fb26f.zip` to the company
   computer, verify its SHA256 above, and extract it to a short path such as
   `C:\aep`.
2. Read `DUT_DRIVER_CONTRACT.md` and replace the ACME examples. Copy the reviewed
   Skill into the installed `workspace\assets\skills` directory.
3. Add the `dut` object shown in the bundle README to installed `host.json`,
   using the exact driver, target, firmware and optional instrument. Set
   `physical_enabled` only when the setup is ready.
4. Add the documented `dut-engineering/validate-physical@1.0.0` grant for the
   bound owner with its permission, policy and approval reference.
5. Edit `dut-request.example.json` so Bridge, Skill, resource identities and
   acceptance limits match the host. Replace `workspace_revision` with the
   64-character digest of the controller revision under test.
6. Run `verify.cmd`, then:

   ```bat
   dut-validate.cmd dut-request.example.json dut-evidence.json
   ```

7. Keep the evidence even when the command returns nonzero. A nonzero result is
   a refusal, execution failure, simulated result or failed measurement and must
   not be approved.

## Known issues

- No real DUT, instrument or vendor driver was available on this development
  computer. The production-like gate is intentionally pending.
- The bundled Skill, target and command names are fake examples and must not be
  used as company evidence.
- The product records the supplied workspace revision in evidence; the operator
  and reviewed driver remain responsible for selecting the actual revision under
  test.
- The local Edge remote-debug profile did not start during the full browser
  suite. The unchanged browser implementation is covered by GitHub Windows CI.
- `.claude/` is user-owned local state. Do not commit, modify or remove it.

## Next Recommended Action

Give the owner the final Windows package and wait for the company-PC result.
When `dut-evidence.json` arrives, verify its exact identities, production-like
mode and every validator outcome, record the human review, and only then mark
E2E-01 and the five-gate milestone complete. Do not redesign the boundary or add
vendor commands to core while waiting.
