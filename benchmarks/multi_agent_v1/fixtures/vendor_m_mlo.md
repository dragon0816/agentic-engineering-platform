# MX-9 Wi-Fi 7 platform: MLO integration guide (synthetic)

Document id: doc-m. Fictional vendor "Vendor M". Synthetic benchmark text; no real
vendor, product or customer data.

## Multi-Link Operation

- Links: up to 2 simultaneous links (5 GHz, 6 GHz).
- Mode: eMLSR only; STR is not supported.
- Maximum channel width: 160 MHz.
- Link switch latency: 256 microseconds (typical).

## Known limits

- The 2.4 GHz radio cannot join an MLO set.
- MLO is off by default and needs the `mlo_enable=1` driver option.
