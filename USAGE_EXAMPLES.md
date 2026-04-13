# Markdown Parser Usage Examples

This document provides practical examples of using `markdown_parser.py` for various compliance documentation tasks.

## Basic Usage

### Example 1: Parse a Single ISO Standard Document

```bash
python markdown_parser.py iso_26262_part_4.md
```

Output:
```
Success: Parsed iso_26262_part_4.md
Output: iso_26262_part_4.json
Part: 4
Title: ISO 26262-4:2018 — Road vehicles — Functional safety — Part 4: Product development at the system level
Clauses: 127
```

### Example 2: Parse with Custom Output Path

```bash
python markdown_parser.py iso_26262_part_4.md compliance_data.json
```

Saves parsed clauses to `compliance_data.json` instead of the default location.

### Example 3: Batch Process a Directory

```bash
python markdown_parser.py ./iso_pdfs_converted/
```

Parses all `.md` files in the directory:
```
Parsed 8 markdown files
  Part 1: Concepts and framework (45 clauses)
  Part 3: Product development at item level (92 clauses)
  Part 4: Product development at system level (127 clauses)
  Part 5: Product development for hardware (98 clauses)
  Part 6: Product development for software (156 clauses)
  Part 7: Application of ISO 26262 for ASIL D (73 clauses)
  Part 8: Guidelines (67 clauses)
  Part 9: Semiconductors (84 clauses)
```

## Programmatic Usage

### Example 4: Parse and Inspect Clauses

```python
from markdown_parser import parse_markdown_standard
import json

# Parse the markdown file
clauses = parse_markdown_standard("iso_26262_part_4.md")

# Find all requirement clauses
requirements = [c for c in clauses if c['type'] == 'requirement']
print(f"Found {len(requirements)} requirement clauses")

# Find clauses with ASIL levels
asil_clauses = [c for c in clauses if c['asil_level']]
print(f"Found {len(asil_clauses)} clauses with ASIL levels")

# Show first requirement
if requirements:
    req = requirements[0]
    print(f"\nFirst requirement:")
    print(f"  Section: {req['section']}")
    print(f"  Title: {req['title']}")
    print(f"  ASIL: {req['asil_level']}")
    print(f"  Tags: {', '.join(req['tags'])}")
```

### Example 5: Generate a Compliance Report

```python
from markdown_parser import parse_markdown_standard, build_compliance_json
import json

# Parse multiple parts
all_parts = {}
for part_num in ['1', '3', '4', '5', '6']:
    clauses = parse_markdown_standard(f"iso_26262_part_{part_num}.md")
    all_parts[part_num] = clauses

# Aggregate statistics
total_clauses = sum(len(c) for c in all_parts.values())
total_requirements = sum(
    1 for clauses in all_parts.values() 
    for c in clauses if c['type'] == 'requirement'
)

print(f"Total clauses across {len(all_parts)} parts: {total_clauses}")
print(f"Total requirements: {total_requirements}")
print(f"Recommendation clauses: {total_clauses - total_requirements}")
```

### Example 6: Filter Clauses by ASIL Level

```python
from markdown_parser import parse_markdown_standard

clauses = parse_markdown_standard("iso_26262_part_4.md")

# Find all clauses applicable to ASIL D
asil_d_clauses = []
for clause in clauses:
    if clause['asil_level']:
        # Check if clause applies to ASIL D
        if 'D' in clause['asil_level']:
            asil_d_clauses.append(clause)

print(f"Clauses applicable to ASIL D: {len(asil_d_clauses)}")

# Show ASIL D requirements
asil_d_requirements = [c for c in asil_d_clauses if c['type'] == 'requirement']
for clause in asil_d_requirements[:5]:
    print(f"\nSection {clause['section']}: {clause['title']}")
    print(f"  ASIL: {clause['asil_level']}")
    print(f"  Tags: {', '.join(clause['tags'][:3])}")
```

### Example 7: Build Traceability Matrix

```python
from markdown_parser import parse_markdown_standard

clauses = parse_markdown_standard("iso_26262_part_4.md")

# Create section-to-tags mapping for traceability
traceability = {}
for clause in clauses:
    section = clause['section']
    tags = clause['tags']
    if tags:
        traceability[section] = {
            'title': clause['title'],
            'tags': tags,
            'type': clause['type'],
            'asil': clause['asil_level']
        }

# Export as CSV for further analysis
import csv
with open('traceability.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Section', 'Title', 'Type', 'ASIL', 'Tags'])
    for section, data in traceability.items():
        writer.writerow([
            section,
            data['title'],
            data['type'],
            data['asil'],
            '; '.join(data['tags'])
        ])

print(f"Exported {len(traceability)} sections to traceability.csv")
```

## Integration with Compliance Engine

### Example 8: Parse Markdown and Run Compliance Check

```python
from markdown_parser import parse_and_save
from agnostic_engine import ComplianceChecker
import json

# Step 1: Parse markdown to JSON
print("Parsing ISO standard...")
json_path = parse_and_save("iso_26262_part_4.md", "iso_26262_part_4.json")
print(f"Created: {json_path}")

# Step 2: Load user documentation
with open("user_safety_documentation.json") as f:
    user_doc = json.load(f)

# Step 3: Run compliance check
print("Running compliance check...")
checker = ComplianceChecker()
results = checker.check_compliance(json_path, user_doc)

# Step 4: Generate report
print("Generating report...")
report = checker.generate_report(results, output_format="pdf")
print(f"Report saved to: {report}")
```

### Example 9: Multi-Part Compliance Analysis

```python
from markdown_parser import parse_markdown_standard, build_compliance_json
from agnostic_engine import ComplianceChecker
import json

# Parse multiple parts of ISO 26262
parts_to_check = ['4', '5', '6']
part_data = {}

for part in parts_to_check:
    print(f"Processing Part {part}...")
    md_file = f"iso_26262_part_{part}.md"
    
    clauses = parse_markdown_standard(md_file)
    part_data[part] = build_compliance_json(clauses, part, f"Part {part}")

# Check user docs against all parts
checker = ComplianceChecker()
with open("user_safety_doc.json") as f:
    user_doc = json.load(f)

overall_compliance = {}
for part, data in part_data.items():
    # Save to temp file for compliance check
    temp_file = f"temp_part_{part}.json"
    with open(temp_file, 'w') as f:
        json.dump(data, f)
    
    results = checker.check_compliance(temp_file, user_doc)
    overall_compliance[part] = results

# Summary report
print("\nCompliance Summary by Part:")
for part, results in overall_compliance.items():
    coverage = results.get('coverage', {})
    print(f"  Part {part}: {coverage.get('percentage', 0):.1f}% coverage")
```

## Advanced Examples

### Example 10: Extract Safety Requirements for Different ASIL Levels

```python
from markdown_parser import parse_markdown_standard

clauses = parse_markdown_standard("iso_26262_part_4.md")

# Organize requirements by ASIL level
asil_requirements = {
    'A': [],
    'B': [],
    'C': [],
    'D': []
}

for clause in clauses:
    if clause['type'] == 'requirement' and clause['asil_level']:
        asil_str = clause['asil_level']
        
        # Check each ASIL level
        for level in ['A', 'B', 'C', 'D']:
            if level in asil_str:
                asil_requirements[level].append({
                    'section': clause['section'],
                    'title': clause['title'],
                    'text': clause['text'][:200]  # First 200 chars
                })

# Print summary
for level in ['A', 'B', 'C', 'D']:
    print(f"\nASIL {level} Requirements: {len(asil_requirements[level])}")
    for req in asil_requirements[level][:3]:
        print(f"  {req['section']}: {req['title']}")
```

### Example 11: Cross-Reference Validation

```python
from markdown_parser import parse_markdown_standard

clauses = parse_markdown_standard("iso_26262_part_4.md")

# Collect all cross-references
all_references = {}
for clause in clauses:
    for ref in clause.get('cross_references', []):
        key = f"Part {ref['part']}, Section {ref['section']}"
        if key not in all_references:
            all_references[key] = []
        all_references[key].append({
            'from_section': clause['section'],
            'from_title': clause['title']
        })

# Report unresolved references
print("Cross-References Found:")
for target, sources in sorted(all_references.items()):
    print(f"\n{target}:")
    for source in sources[:3]:
        print(f"  Referenced from: {source['from_section']} - {source['from_title']}")
    if len(sources) > 3:
        print(f"  ... and {len(sources) - 3} more references")
```

### Example 12: Tag-Based Requirement Clustering

```python
from markdown_parser import parse_markdown_standard
from collections import defaultdict

clauses = parse_markdown_standard("iso_26262_part_4.md")

# Group clauses by tags
tag_clusters = defaultdict(list)
for clause in clauses:
    for tag in clause.get('tags', []):
        tag_clusters[tag].append({
            'section': clause['section'],
            'title': clause['title'],
            'type': clause['type']
        })

# Find most common tags
print("Top Safety-Related Tags:")
for tag in sorted(tag_clusters.keys(), 
                 key=lambda t: len(tag_clusters[t]), 
                 reverse=True)[:10]:
    clauses_with_tag = tag_clusters[tag]
    print(f"  {tag}: {len(clauses_with_tag)} clauses")
    
    # Show requirements with this tag
    requirements_with_tag = [c for c in clauses_with_tag if c['type'] == 'requirement']
    if requirements_with_tag:
        print(f"    Requirements: {len(requirements_with_tag)}")
        for req in requirements_with_tag[:2]:
            print(f"      - {req['section']}: {req['title']}")
```

## Automation Workflows

### Example 13: Scheduled Markdown Parsing

```python
import schedule
import time
from markdown_parser import parse_and_save

def parse_new_standards():
    """Scheduled task to parse newly converted markdown files"""
    import os
    
    input_dir = "iso_pdf_conversions/"
    output_dir = "parsed_standards/"
    
    # Create output directory if needed
    os.makedirs(output_dir, exist_ok=True)
    
    # Parse all unparsed markdown files
    for filename in os.listdir(input_dir):
        if filename.endswith('.md'):
            input_path = os.path.join(input_dir, filename)
            output_name = filename.replace('.md', '.json')
            output_path = os.path.join(output_dir, output_name)
            
            # Only parse if output doesn't exist
            if not os.path.exists(output_path):
                try:
                    parse_and_save(input_path, output_path)
                    print(f"Parsed: {filename} → {output_name}")
                except Exception as e:
                    print(f"Error parsing {filename}: {e}")

# Schedule to run daily at 2 AM
schedule.every().day.at("02:00").do(parse_new_standards)

# Keep scheduler running
while True:
    schedule.run_pending()
    time.sleep(60)
```

### Example 14: Validation Pipeline

```python
import json
from markdown_parser import parse_markdown_standard

def validate_parsed_document(md_file):
    """Validate that parsed document meets quality standards"""
    
    clauses = parse_markdown_standard(md_file)
    
    issues = []
    
    # Check 1: All clauses have required fields
    for i, clause in enumerate(clauses):
        required_fields = ['section', 'title', 'type', 'text']
        for field in required_fields:
            if not clause.get(field):
                issues.append(f"Clause {i}: Missing '{field}'")
    
    # Check 2: At least some clauses are requirements
    requirement_count = sum(1 for c in clauses if c['type'] == 'requirement')
    if requirement_count == 0:
        issues.append("No requirement clauses found")
    
    # Check 3: Cross-references are valid
    for clause in clauses:
        for ref in clause.get('cross_references', []):
            if not ref.get('part'):
                issues.append(f"Clause {clause['section']}: Invalid cross-reference (no part)")
    
    # Report results
    print(f"Validation Results for {md_file}:")
    print(f"  Total clauses: {len(clauses)}")
    print(f"  Requirements: {requirement_count}")
    print(f"  Issues found: {len(issues)}")
    
    if issues:
        print("\n  Issues:")
        for issue in issues[:5]:
            print(f"    - {issue}")
        if len(issues) > 5:
            print(f"    ... and {len(issues) - 5} more")
    
    return len(issues) == 0

# Validate all parsed documents
if validate_parsed_document("iso_26262_part_4.md"):
    print("✓ Document is valid")
else:
    print("✗ Document has issues")
```

## Tips and Tricks

### Performance Tips

1. **Cache parsed documents** for frequently used standards
2. **Process in parallel** for multiple document sets
3. **Use generators** for large document processing

### Debugging

```python
# Enable detailed output during parsing
import logging
logging.basicConfig(level=logging.DEBUG)

from markdown_parser import parse_markdown_standard

# Parser will now show detailed info
clauses = parse_markdown_standard("debug_file.md")
```

### Custom Filtering

```python
# Find all clauses related to verification
def find_verification_clauses(clauses):
    verification_tags = {'Verification', 'Testing', 'Validation', 'Review'}
    
    return [
        c for c in clauses 
        if any(tag in c['tags'] for tag in verification_tags)
    ]

# Use it
from markdown_parser import parse_markdown_standard
clauses = parse_markdown_standard("iso_26262_part_4.md")
verification_clauses = find_verification_clauses(clauses)

print(f"Found {len(verification_clauses)} verification-related clauses")
```

---

For more details, see `MARKDOWN_PARSER_README.md` for the complete API reference.
