# Physical DUT driver contract

The preview does not contain vendor commands. A reviewed local executable owns
those commands and is named by an absolute path in `host.json`. The platform
starts that exact executable with `shell=False`; the model and request cannot
choose another program.

For each requested command the driver receives one UTF-8 JSON document on
standard input:

```json
{
  "target": {
    "resource_id": "dut-acme-001",
    "device_id": "acme-001",
    "vendor": "acme",
    "model": "radio-x1",
    "firmware": "FW-2.3"
  },
  "instrument": null,
  "command": {
    "name": "set_tx_power",
    "arguments": { "requested_dbm": 10.0 }
  }
}
```

It returns one UTF-8 JSON document on standard output and exits with code zero:

```json
{
  "command": "set_tx_power",
  "state": { "ready": true },
  "measurements": [
    { "name": "tx_power", "value": 15.0, "unit": "dBm" }
  ]
}
```

The command name must match. Values must be finite. The platform independently
checks units, limits and expected state, so a driver's success exit alone cannot
pass validation. A nonzero exit or invalid JSON fails the capability.

Credentials do not belong in the request, response, command arguments, fixed
driver arguments, Skill, evidence file or `host.json`. The driver must resolve
any required credential through its own approved runtime environment.
