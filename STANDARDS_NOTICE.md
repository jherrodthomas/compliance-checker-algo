# Standards Notice

## This repository does not include any copyrighted standard content.

The compliance engine is **standard-agnostic** — it works with any safety or quality standard you provide. However, the standards themselves are copyrighted documents that must be purchased from their respective publishers.

### Where to purchase

| Standard | Publisher | Link |
|---|---|---|
| ISO 26262 (Functional Safety) | ISO / SAE | [iso.org](https://www.iso.org/standard/68383.html) |
| ISO 21434 (Cybersecurity) | ISO / SAE | [iso.org](https://www.iso.org/standard/70918.html) |
| ISO 21448 / SOTIF | ISO | [iso.org](https://www.iso.org/standard/77490.html) |
| Automotive SPICE (ASPICE) | VDA QMC | [vda-qmc.de](https://www.vda-qmc.de/en/automotive-spice/) |
| IEC 61508 | IEC | [iec.ch](https://www.iec.ch/functionalsafety) |
| DO-178C | RTCA | [rtca.org](https://www.rtca.org/) |

### How to use your own standards

1. Purchase the standard from the official publisher
2. Convert it to the JSON schema the engine expects (see `examples/synthetic_standard/` for the format)
3. Place the JSON files in a directory and point the engine at it

The `examples/` folder contains **synthetic (fictional) data only** — suitable for testing and understanding the engine's input format, but not representative of any real standard's content.

### Legal

Redistribution of copyrighted standard content is not permitted. If you fork this repository, do **not** add proprietary standard data to your fork.
