# Markdown Parser for ISO Standards

## Overview

The `markdown_parser.py` module parses ISO-style markdown documents (typically derived from PDF-to-markdown conversion of ISO standards) into structured JSON that the compliance engine (`agnostic_engine.py`) can consume.

### Design Principle

The parser produces **identical output structure** to the existing JSON clause files. No modifications to the compliance engine are needed — the parser output is directly compatible.

### Output Structure

Each parsed document produces JSON matching this schema:

```json
{
  "part": "4",
  "title": "ISO 26262-4:2018 — Road vehicles — Functional safety — Part 4: Product development at the system level",
  "clauses": [
    {
      "section": "6.4.2",
      "title": "Technical safety requirements",
      "type": "requirement",
      "text": "...",
      "tags": ["ASIL", "Safety", "Verification"],
      "asil_level": "B-D",
      "notes": ["Note 1 text", "Note 2 text"],
      "cross_references": [
        {"part": "3", "section": "7.4.1", "context": "..."}
      ]
    }
  ]
}
```

## Core Functions

### Primary Entry Points

#### `parse_markdown_standard(md_path: str) -> List[Dict]`
Parse a single markdown file into a list of clause dictionaries.

```python
clauses = parse_markdown_standard("iso_26262_part_4.md")
# Returns: [
#   {"section": "1", "title": "Scope", "type": "overview", ...},
#   {"section": "6.4.2", "title": "Technical safety requirements", ...},
# ]
```

#### `parse_markdown_directory(dir_path: str) -> Dict`
Parse all `.md` files in a directory, organizing by part number.

```python
results = parse_markdown_directory("./iso_standards/")
# Returns: {
#   "4": {"title": "...", "clauses": [...]},
#   "5": {"title": "...", "clauses": [...]},
# }
```

#### `parse_and_save(md_path: str, output_json: str = None) -> str`
Parse markdown and save directly to JSON file.

```python
output_path = parse_and_save("iso_26262_part_4.md", "output.json")
# Writes to output.json and returns path
```

### Parsing Utilities

#### `detect_part_number(text: str, filename: str = "") -> str`
Extract part number from document title or filename.

- Supports "Part 4" format
- Supports "ISO 26262-4" format
- Supports "iso_26262_part_4.md" filename format
- Returns: Part number string (e.g., "4") or empty string

#### `extract_section_id(heading: str) -> Tuple[str, str]`
Extract section ID and title from markdown heading.

```python
section_id, title = extract_section_id("6.4.2 Technical safety requirements")
# Returns: ("6.4.2", "Technical safety requirements")
```

Handles:
- Major clauses: "6 Specification of..."
- Subclauses: "6.4 Requirements..."
- Sub-subclauses: "6.4.2 Technical safety requirements"
- Annex clauses: "Annex A Guidance" or "A.1 Sub-item guidance"

#### `classify_clause(text: str) -> str`
Classify clause type based on keyword patterns.

Returns one of:
- **"requirement"** — Contains "shall" (mandatory)
- **"recommendation"** — Contains "should" (recommended)
- **"permission"** — Contains "may" in permission context
- **"guideline"** — Contains "NOTE" or "EXAMPLE"
- **"overview"** — General informative sections
- **"annex"** — Explicit annexes

Example:
```python
clause_type = classify_clause("The system shall be designed...")
# Returns: "requirement"
```

#### `extract_asil_level(text: str) -> str`
Detect ASIL levels from clause text.

Recognizes patterns:
- "ASIL A", "ASIL B", "ASIL C", "ASIL D"
- "ASIL: A, B, C, D"
- "ASIL A-D", "ASIL B-D"
- "ASIL (A, B, C, D)"
- Table rows mapping methods to ASIL levels

Returns: ASIL level string (e.g., "B", "B-D", "A, B, C, D") or empty string

#### `extract_cross_references(text: str) -> List[Dict]`
Extract cross-references to other parts/sections.

Recognizes patterns:
- "see Part 3, Clause 7.4.1"
- "see 6.4.2"
- "in accordance with Part 8"
- "ISO 26262-3:2018, 7.4.1"
- "Part 4, 5.4.2"

Returns list of: `{"part": "3", "section": "7.4.1", "context": "..."}`

#### `extract_tags(text: str) -> List[str]`
Extract key concept tags from clause text.

Extracts:
- Acronyms and all-caps terms (FMEA, FTA, ASIL, etc.)
- Bold/italic emphasized terms
- Common safety/compliance keywords
- Returns: Sorted list of unique tags

Example:
```python
tags = extract_tags("The FMEA and FTA analysis for hazard identification...")
# Returns: ["ASIL", "FTA", "FMEA", "Hazard", ...]
```

#### `extract_notes(text: str) -> List[str]`
Extract NOTE and EXAMPLE blocks.

Returns list of note paragraphs, each up to 300 characters.

### Markdown Processing

#### `split_markdown_into_sections(content: str) -> List[Tuple[int, str, str]]`
Split markdown into (level, heading, body) tuples.

```python
sections = split_markdown_into_sections(md_content)
# Returns: [
#   (1, "ISO 26262-4:2018 — ...", ""),
#   (2, "1 Scope", "This document specifies..."),
#   (3, "6.4 Requirements", "..."),
#   (4, "6.4.2 Technical safety requirements", "..."),
# ]
```

#### `parse_heading_level(heading_text: str) -> int`
Get heading level (count of # characters).

## Command Line Interface

### Usage

```bash
# Parse single markdown file
python markdown_parser.py input.md

# Parse and save to specific JSON
python markdown_parser.py input.md output.json

# Parse directory of markdown files
python markdown_parser.py ./iso_standards/
```

### Examples

```bash
# Parse ISO 26262 Part 4
python markdown_parser.py iso_26262_part_4.md

# Save to specific location
python markdown_parser.py iso_26262_part_4.md compliance_data.json

# Batch process multiple parts
python markdown_parser.py ./iso_pdfs_converted/
```

## Handling ISO Markdown Quirks

The parser is designed to handle imperfect markdown from PDF-to-text conversion:

### OCR Artifacts
- Inconsistent spacing and line breaks
- Misaligned section numbering
- Unicode em-dashes and special characters (handled via `[—–-]?` patterns)

### Heading Structure
- Maps heading hierarchy to section numbering
- Robust regex handles 5, 5.4, 5.4.1, 5.4.1.2, Annex A, A.1 formats
- Skips headings without section IDs (e.g., pure heading text)

### Content Variations
- Notes can appear as "NOTE", "NOTE 1", "NOTE 1 —", "NOTE:"
- ASIL levels appear inline or in tables
- Cross-references use multiple formats
- Text before first heading is skipped

## Implementation Details

### Dependencies
Pure Python standard library only:
- `re` — Regular expressions
- `json` — JSON serialization
- `os`, `pathlib` — File operations
- `collections` — Data structures
- `typing` — Type hints

### Regex Patterns

Key regex patterns used:

```python
# Section number extraction
r'^([A-Z][\dA-Z.]*|\d[\d.]*)\s+(.*)$'

# ASIL detection
r'ASIL\s*[:(]?\s*([A-D][\s,A-D\-&/]*[A-D]?)'

# Cross-reference patterns
r'Part\s+(\d+)\s*,?\s*(?:Clause|Section)'
r'in accordance with Part \d+'

# All-caps acronyms
r'\b([A-Z][A-Z0-9]{2,}(?:\s+[A-Z][A-Z0-9]{2,})*)\b'

# "shall" / "should" / "may" keywords (whole word)
r'\b(shall|should|may)\b'
```

## Example: Parsing a Test Document

```python
from markdown_parser import parse_and_save
import json

# Parse test markdown
output_path = parse_and_save("test_sample_iso_standard.md", "test_output.json")

# Verify structure
with open(output_path) as f:
    data = json.load(f)

print(f"Part: {data['part']}")
print(f"Title: {data['title']}")
print(f"Clauses: {len(data['clauses'])}")

# Inspect a specific clause
for clause in data['clauses']:
    if clause['section'] == '6.4.2':
        print(f"\nClause 6.4.2: {clause['title']}")
        print(f"Type: {clause['type']}")
        print(f"ASIL: {clause['asil_level']}")
        print(f"Tags: {clause['tags']}")
        print(f"Cross-refs: {clause['cross_references']}")
```

## Testing

A test markdown file (`test_sample_iso_standard.md`) is included that demonstrates:
- Multi-level heading hierarchy (## through ####)
- Section numbering (1, 2, 5.4.1, 6.4.2, etc.)
- Requirement keywords ("shall")
- ASIL level detection
- Cross-references to other parts
- NOTE blocks
- Method tables with ASIL columns
- Annex sections

Parse and inspect the test:

```bash
python markdown_parser.py test_sample_iso_standard.md test_output.json
cat test_output.json | python -m json.tool | head -50
```

## Integration with Compliance Engine

The parsed JSON directly feeds into `agnostic_engine.py`:

```python
from markdown_parser import parse_and_save
from agnostic_engine import ComplianceChecker

# Parse markdown
json_path = parse_and_save("iso_26262_part_4.md")

# Load into compliance engine
checker = ComplianceChecker()
results = checker.check_compliance(json_path, user_doc_path)

# Generate report
report = checker.generate_report(results, output_format="pdf")
```

## Future Enhancements

Potential improvements:

1. **Method table parsing** — Extract and structure method/ASIL mapping tables
2. **Table extraction** — Parse complex requirement tables
3. **Figures and diagrams** — Reference extraction for visual content
4. **Change tracking** — Diff between versions for regulatory updates
5. **Link validation** — Verify cross-references resolve correctly
6. **Confidence scores** — Track certainty of extracted fields (for OCR artifacts)

## License

As part of the Compliance Checker Algo suite.

## Version

Created: 2026-03-27
Compatible with: agnostic_engine.py (current version)
