# Example Data

This folder contains **synthetic (fictional) data** for testing and demonstration.

No proprietary or copyrighted standard content is included.

## What's here

| File / Folder | Purpose |
|---|---|
| `synthetic_standard/` | A made-up 4-part safety standard in the JSON format the engine expects |
| `synthetic_artifact.json` | A fictional work product (smart thermostat) to check against the standard |
| `synthetic_meta.json` | Optional meta-config providing schema hints to the engine |

## Quick test

```bash
python agnostic_engine.py examples/synthetic_standard examples/synthetic_artifact.json --meta examples/synthetic_meta.json
```

## Using real standards

The engine works with **any** standard you can represent as JSON or Markdown.
To use a real standard (e.g., ISO 26262, IEC 61508, DO-178C):

1. **Purchase the standard** from the official publisher (ISO, SAE, etc.)
2. Convert it to the JSON schema shown in `synthetic_standard/` or to Markdown
3. Point the engine at your standard directory and your work product

See the root README for the full JSON schema reference.
