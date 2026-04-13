#!/usr/bin/env python3
"""
markdown_parser.py - Parse ISO-style markdown into compliance engine JSON structure.

This module converts markdown documents (derived from ISO PDFs via pdftotext + pandoc)
into the JSON clause format expected by agnostic_engine.py.

The parser:
1. Detects heading hierarchy and maps to section numbering
2. Extracts section IDs (6.4.2) and titles
3. Classifies clauses (requirement/recommendation/guideline/overview)
4. Extracts body text between headings
5. Detects ASIL levels, cross-references, and tags
6. Handles notes and method tables
7. Auto-detects part number from title or filename
"""

import re
import json
import os
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Optional


def detect_part_number(text: str, filename: str = "") -> str:
    """
    Extract part number from document title or filename.

    Looks for patterns like:
    - "Part 4" in title
    - "ISO 26262-4" in title
    - "iso_26262_part_4" in filename

    Args:
        text: Document title/header text
        filename: Source filename

    Returns:
        Part number as string (e.g., "4"), or "" if not found
    """
    # Try filename first (e.g., "iso_26262_part_4.md")
    filename_match = re.search(r'part[_\s-]*(\d+)', filename, re.IGNORECASE)
    if filename_match:
        return filename_match.group(1)

    # Try filename with ISO-style numbering (e.g., "ISO_DIS_26262-4.md", "26262-10.md")
    iso_file_match = re.search(r'26262[_-](\d+)', filename, re.IGNORECASE)
    if iso_file_match:
        return iso_file_match.group(1)

    # More general: any standard-like pattern "XXXXX-N" in filename
    std_file_match = re.search(r'\d{4,5}[_-](\d{1,2})', filename)
    if std_file_match:
        return std_file_match.group(1)

    # Try "Part N" in text
    part_match = re.search(r'[—–-]?\s*Part\s+(\d+)', text)
    if part_match:
        return part_match.group(1)

    # Try "ISO XXXXX-N" pattern in text
    iso_match = re.search(r'ISO[/_\s]+(?:DIS[/_\s]+)?\d+-(\d+)', text)
    if iso_match:
        return iso_match.group(1)

    return ""


def extract_section_id(heading: str) -> Tuple[str, str]:
    """
    Extract section ID and title from a heading.

    Handles patterns like:
    - "6 Specification of..." -> ("6", "Specification of...")
    - "6.4 Requirements..." -> ("6.4", "Requirements...")
    - "6.4.2 Technical safety requirements" -> ("6.4.2", "Technical safety requirements")
    - "Annex A Guidance" -> ("A", "Guidance")
    - "A.1 Sub-item guidance" -> ("A.1", "Sub-item guidance")

    Args:
        heading: Markdown heading text (without # markers)

    Returns:
        Tuple of (section_id, title) or ("", heading) if no ID found
    """
    # Remove markdown emphasis markers
    clean_heading = re.sub(r'[*_`]', '', heading).strip()

    # Match section numbers: integer, decimal, Annex A, Annex A.1, etc.
    # Pattern: optional non-digit prefix, digits/dots/letters, then space or end
    match = re.match(r'^([A-Z][\dA-Z.]*|\d[\d.]*)\s+(.*)$', clean_heading)

    if match:
        section_id = match.group(1)
        title = match.group(2).strip()
        return (section_id, title)

    return ("", clean_heading)


def classify_clause(text: str) -> str:
    """
    Classify a clause based on keyword patterns.

    Returns one of:
    - "requirement" (contains "shall")
    - "recommendation" (contains "should")
    - "permission" (contains "may" in permission context)
    - "guideline" (contains "NOTE", "EXAMPLE", "NOTE 1", etc.)
    - "overview" (Scope, Normative references, Terms & definitions)
    - "annex" (explicitly an Annex)

    Args:
        text: Clause body text

    Returns:
        Classification string
    """
    if not text:
        return "overview"

    text_lower = text.lower()

    # Check for explicit keyword patterns (must be whole words)
    if re.search(r'\bshall\b', text_lower):
        return "requirement"

    if re.search(r'\bshould\b', text_lower):
        return "recommendation"

    # "may" is ambiguous; prefer "permission" if in permission context
    if re.search(r'\bmay\b', text_lower):
        if re.search(r'(may|optionally|optional)', text_lower):
            return "permission"

    # Check for notes and examples
    if re.search(r'^\s*(NOTE\s*\d*|EXAMPLE|EXAMPLES?)', text, re.MULTILINE):
        return "guideline"

    # Check for overview keywords
    if any(keyword in text_lower for keyword in
           ['scope', 'normative references', 'terms and definitions', 'terms & definitions']):
        return "overview"

    # Default: requirement if unclassified (most ISO clauses are requirements)
    return "overview"


def extract_asil_level(text: str) -> str:
    """
    Detect ASIL level(s) from clause text.

    Looks for patterns like:
    - "ASIL A" / "ASIL B" / "ASIL C" / "ASIL D"
    - "ASIL: A, B, C, D"
    - "ASIL A-D"
    - "ASIL B-D"
    - "ASIL (A, B, C, D)"

    Returns highest level or range if multiple found.

    Args:
        text: Clause text to search

    Returns:
        ASIL level string (e.g., "A", "B", "A-D", "B-D", "A, B, C, D") or ""
    """
    if not text:
        return ""

    # Look for ASIL patterns (case-insensitive)
    # Matches: ASIL A, ASIL: A, ASIL (A), ASIL A-D, etc.
    match = re.search(
        r'ASIL\s*[:(]?\s*([A-D][\s,A-D\-&/]*[A-D]?)',
        text,
        re.IGNORECASE
    )

    if match:
        asil_str = match.group(1).strip()
        # Clean up whitespace and normalize
        asil_str = re.sub(r'\s+', ' ', asil_str)
        asil_str = re.sub(r'[()[\]]', '', asil_str)
        return asil_str

    return ""


def extract_cross_references(text: str) -> List[Dict]:
    """
    Extract cross-references from clause text.

    Looks for patterns like:
    - "see Part 3, Clause 7.4.1"
    - "see 6.4.2"
    - "in accordance with Part 8"
    - "ISO 26262-3:2018, 7.4.1"
    - "Part 4, 5.4.2"

    Args:
        text: Clause text to search

    Returns:
        List of dicts: {part, section, context}
        context is the surrounding sentence fragment for disambiguation
    """
    if not text:
        return []

    cross_refs = []

    # Pattern 1: Part N, Clause/Section M.N(.O)
    pattern1 = r'Part\s+(\d+)\s*,?\s*(?:Clause|Section|6?\.?4?\.?\d+[.\d]*)'
    # Pattern 2: Part N alone (implies entire part)
    pattern2 = r'Part\s+(\d+)'
    # Pattern 3: Section/Clause number alone (e.g., "6.4.2")
    pattern3 = r'(?:^|\s)(\d+\.\d+(?:\.\d+)?|[A-Z]\.\d+)'
    # Pattern 4: ISO XXXXX-N:YYYY, section M.N
    pattern4 = r'ISO\s+\d+-(\d+)(?::\d+)?,?\s*(\d+\.\d+(?:\.\d+)?)?'

    # Extract context: sentence containing the reference
    sentences = re.split(r'[.;:]', text)

    for match in re.finditer(r'(?:see|See|in accordance with|according to|per)\s+(.+?)(?=[.;:]|$)',
                             text, re.IGNORECASE):
        context = match.group(1).strip()

        # Try to extract part and section from context
        part_match = re.search(r'Part\s+(\d+)', context)
        section_match = re.search(r'(?:Clause|Section)?\s+(\d+\.\d+(?:\.\d+)?)', context)

        if part_match:
            part = part_match.group(1)
            section = section_match.group(1) if section_match else ""
            cross_refs.append({
                "part": part,
                "section": section,
                "context": context[:100]  # Limit context length
            })

    return cross_refs


def extract_tags(text: str) -> List[str]:
    """
    Extract key concept tags from clause text.

    Focuses on:
    - Known safety/engineering domain acronyms (ASIL, FMEA, FTA, etc.)
    - Recognized multi-word safety concepts
    - Common safety/compliance keywords
    - Terms in bold (**term**) or italic (*term*) that are known domain terms

    Filters OUT:
    - Generic hardware abbreviations (CPU, ALU, ADC, etc.)
    - Author last names from bibliographic references
    - Malformed table cell content
    - Single-word abbreviations that aren't safety-relevant

    Args:
        text: Clause text to analyze

    Returns:
        List of unique tag strings, sorted
    """
    if not text:
        return []

    tags = set()

    # Recognized domain acronyms relevant to functional safety / compliance
    DOMAIN_ACRONYMS = {
        # Safety analysis methods
        'FMEA', 'FMEDA', 'FTA', 'FMECA', 'ETA', 'HAZOP', 'DFA', 'CCA', 'RBD', 'DRBFM',
        # Safety concepts
        'ASIL', 'SIL', 'HARA', 'FSC', 'TSC', 'TSR', 'FSR', 'HSI', 'SOTIF', 'ODD',
        'SPFM', 'LFM', 'PMHF', 'FTTI', 'MPFDI', 'FDTI',
        # Standards and frameworks
        'AUTOSAR', 'CMMI', 'ASPICE', 'MISRA',
        # Hardware/safety metrics
        'BIST', 'ECC', 'CRC', 'WDT', 'EDC', 'LBIST', 'MBIST',
        # Process / quality
        'QMS', 'PDCA', 'CAPA', 'DVP', 'PPAP', 'PFMEA', 'DFMEA', 'APQP',
        # Vehicle systems
        'ABS', 'ESC', 'ESP', 'ACC', 'AEB', 'ADAS', 'EPS', 'EPB', 'BCM', 'ECU', 'TCU',
        # Communication
        'CAN', 'LIN', 'SPI',
        # Safety management
        'DIA', 'SEooC', 'COTS', 'GSN', 'CAE',
        # Documentation
        'SRS', 'SDD', 'STP', 'STR', 'SVP',
    }

    # Exclude list — common abbreviations that are NOT safety-relevant concepts
    EXCLUDE_TERMS = {
        # Document structure words
        'ISO', 'EN', 'IEC', 'SAE', 'IEEE', 'DIN', 'NOTE', 'EXAMPLE', 'TABLE', 'CLAUSE',
        'ANNEX', 'FIGURE', 'SEE', 'AND', 'THE', 'FOR', 'NOT', 'WITH', 'FROM', 'BUT',
        'THAT', 'THIS', 'ARE', 'WAS', 'HAS', 'CAN', 'MAY', 'SHALL', 'SHOULD', 'WILL',
        # Hardware component abbreviations (not safety concepts)
        'CPU', 'GPU', 'ALU', 'ADC', 'DAC', 'RAM', 'ROM', 'PLL', 'VCO', 'LDO', 'FET',
        'MOS', 'CMOS', 'BJT', 'LED', 'LCD', 'USB', 'SSD', 'HDD', 'NVM', 'SRAM',
        'DRAM', 'FPGA', 'DSP', 'MMU', 'TLB', 'DMA', 'GPIO', 'PWM', 'UART', 'SPI',
        'ASIC', 'SOC', 'MCU', 'MPU', 'PCB', 'SMD', 'BGA', 'QFP', 'EEPROM',
        'AGC', 'IPC', 'EMC', 'EMI', 'ESD', 'RFI', 'FLASH',
        # Quality document numbers
        'AEC', 'MIL', 'STD', 'JEDEC', 'FMVSS', 'ECE',
        # Generic terms
        'GBP', 'BPD', 'CDV', 'CCP', 'CPVSG', 'DFI',
    }

    # Extract bold/italic terms
    for match in re.finditer(r'[*_]{1,2}([A-Za-z\s]+?)[*_]{1,2}', text):
        term = match.group(1).strip().upper()
        if term in DOMAIN_ACRONYMS:
            tags.add(term)

    # Extract acronyms — only those in the recognized domain list
    for match in re.finditer(r'\b([A-Z][A-Z0-9]{2,})\b', text):
        term = match.group(1)
        if term in DOMAIN_ACRONYMS and term not in EXCLUDE_TERMS:
            tags.add(term)

    # Add common safety/compliance keywords found in text
    keywords = [
        'safety', 'hazard', 'risk', 'assessment', 'analysis', 'requirement',
        'verification', 'validation', 'review', 'audit', 'design', 'testing',
        'failure', 'mitigation', 'control', 'measure', 'specification',
        'traceability', 'decomposition', 'independence', 'integration',
        'calibration', 'diagnostic', 'monitoring', 'redundancy', 'diversity',
    ]
    for keyword in keywords:
        if re.search(rf'\b{keyword}\b', text, re.IGNORECASE):
            tags.add(keyword.title())

    return sorted(list(tags))


def extract_notes(text: str) -> List[str]:
    """
    Extract NOTE and EXAMPLE blocks from text.

    Returns each NOTE/EXAMPLE paragraph as a separate list item.

    Args:
        text: Clause text

    Returns:
        List of note/example strings
    """
    notes = []

    # Match NOTE N, EXAMPLE N, EXAMPLES, etc.
    pattern = r'(NOTE\s*\d*|EXAMPLE[S]?)\s+(.+?)(?=NOTE|EXAMPLE|$)'

    for match in re.finditer(pattern, text, re.DOTALL | re.IGNORECASE):
        note_text = match.group(2).strip()
        # Remove excessive whitespace
        note_text = re.sub(r'\s+', ' ', note_text)
        if note_text:
            notes.append(note_text[:300])  # Limit length

    return notes


def parse_heading_level(heading_text: str) -> int:
    """
    Determine the hierarchy level of a heading.

    Counts the number of # characters before the heading text.
    ISO standard structure typically maps:
    - # = Part title
    - ## = Major clause (e.g., "6 Specification...")
    - ### = Subclause (e.g., "6.4 Requirements...")
    - #### = Sub-subclause (e.g., "6.4.2 Technical...")

    Args:
        heading_text: Raw heading line from markdown (e.g., "### 6.4 Title")

    Returns:
        Heading level (1-6), or 0 if not a heading
    """
    match = re.match(r'^(#+)', heading_text)
    return len(match.group(1)) if match else 0


# Noise patterns from pdftotext conversion (watermarks, footers, headers)
_NOISE_PATTERNS = [
    re.compile(r'Normen-Download-Beuth', re.I),
    re.compile(r'©\s*ISO\s+\d{4}'),
    re.compile(r'All rights reserved'),
    re.compile(r'ISO/DIS\s+\d+-\d+:\d{4}'),
    re.compile(r'^\s*\d+\s*﻿?\s*$'),  # page numbers
    re.compile(r'DRAFT INTERNATIONAL STANDARD'),
    re.compile(r'COPYRIGHT PROTECTED DOCUMENT'),
    re.compile(r'KdNr\.\d+'),
    re.compile(r'^\s*﻿\s*$'),  # blank with BOM
]


def _is_noise_line(line: str) -> bool:
    """Check if a line is a pdftotext noise artifact (watermark, footer, etc.)."""
    stripped = line.strip()
    if not stripped:
        return False
    return any(p.search(stripped) for p in _NOISE_PATTERNS)


def _detect_pdftotext_format(content: str) -> bool:
    """
    Detect if content is raw pdftotext output (no # headings, lots of leading whitespace).

    Returns True if the content appears to be pdftotext output.
    """
    lines = content.split('\n')[:100]
    has_hash_headings = any(line.startswith('#') for line in lines)
    has_deep_indent = sum(1 for line in lines if len(line) > 40 and line != line.lstrip() and len(line) - len(line.lstrip()) > 30) > 10
    return not has_hash_headings and has_deep_indent


def _section_level_from_id(section_id: str) -> int:
    """
    Determine heading level from section ID depth.

    "6" → level 2, "6.4" → level 3, "6.4.2" → level 4, etc.
    Annex IDs like "A" → level 2, "A.1" → level 3.
    """
    if not section_id:
        return 0
    parts = section_id.split('.')
    return len(parts) + 1  # +1 because level 1 is reserved for doc title


def split_pdftotext_into_sections(content: str) -> List[Tuple[int, str, str]]:
    """
    Split pdftotext-converted content into sections by detecting section-numbered lines.

    Handles the typical pdftotext layout where section headings appear as:
        "      6.4.2  Technical safety requirements"
    with lots of leading whitespace.

    Also handles Annex headings like:
        "      Annex A"
        "      A.1  Sub-item"

    Args:
        content: Full pdftotext-converted file content

    Returns:
        List of (level, heading, body) tuples
    """
    lines = content.split('\n')
    sections = []

    # Pattern for section headings: optional whitespace, then section number, then title
    # Matches: "6", "6.4", "6.4.2", "A", "A.1", "A.1.2", "Annex A", "Annex B"
    section_pattern = re.compile(
        r'^\s+'                          # leading whitespace (pdftotext indent)
        r'(?:'
        r'(Annex\s+[A-Z](?:\.\d+)*)'    # "Annex A" or "Annex A.1"
        r'|'
        r'(\d+(?:\.\d+)*)'              # "6" or "6.4" or "6.4.2"
        r'|'
        r'([A-Z](?:\.\d+)+)'            # "A.1" or "A.1.2" (Annex sub-items)
        r')'
        r'\s+'                            # space after number
        r'([A-Z][A-Za-z].*?)'           # title starting with capital letter
        r'\s*$'                           # end of line
    )

    # Also match top-level single-digit sections that might have different formatting
    # like "1 Scope" at the start of the document body
    alt_pattern = re.compile(
        r'^\s+'
        r'(\d{1,2})'                     # 1 or 2 digit number
        r'\s{2,}'                         # at least 2 spaces
        r'([A-Z][A-Za-z].*?)'           # title
        r'(?:\s*\.+\s*\d+)?'            # optional ".... 6" page reference from TOC
        r'\s*$'
    )

    current_heading = None
    current_level = None
    current_body = []
    in_toc = False

    for line in lines:
        stripped = line.strip()

        # Skip noise lines
        if _is_noise_line(line):
            continue

        # Detect and skip table of contents (lines with "....." page references)
        if re.search(r'\.{3,}\s*\d+\s*$', stripped):
            in_toc = True
            continue

        # End of TOC detection: a non-TOC line after TOC lines
        if in_toc and stripped and not re.search(r'\.{3,}', stripped):
            in_toc = False

        if in_toc:
            continue

        # Try to match section heading
        m = section_pattern.match(line)
        section_id = None
        title = None

        if m:
            if m.group(1):  # Annex A
                annex_id = m.group(1).replace('Annex ', '')
                section_id = annex_id
                title = m.group(4)
            elif m.group(2):  # 6.4.2
                section_id = m.group(2)
                title = m.group(4)
            elif m.group(3):  # A.1
                section_id = m.group(3)
                title = m.group(4)

        if not m and not in_toc:
            # Try alternate pattern for simple "1 Scope" style
            m2 = alt_pattern.match(line)
            if m2:
                candidate_id = m2.group(1)
                candidate_title = m2.group(2)
                # Verify this isn't just a list item "a) something" or similar
                if candidate_title and len(candidate_title) > 3 and not candidate_title.startswith('('):
                    section_id = candidate_id
                    title = candidate_title

        if section_id and title:
            # Determine level from section ID depth
            level = _section_level_from_id(section_id)

            # Save previous section
            if current_heading is not None:
                body_text = '\n'.join(current_body).strip()
                # Clean body: strip leading whitespace from each line
                body_lines = [bl.strip() for bl in body_text.split('\n')]
                body_text = '\n'.join(bl for bl in body_lines if bl)
                sections.append((current_level, current_heading, body_text))

            current_heading = f"{section_id} {title.strip()}"
            current_level = level
            current_body = []
        else:
            # Add to current body (strip the heavy indentation)
            if current_heading is not None and stripped:
                current_body.append(stripped)

    # Don't forget last section
    if current_heading is not None:
        body_text = '\n'.join(current_body).strip()
        body_lines = [bl.strip() for bl in body_text.split('\n')]
        body_text = '\n'.join(bl for bl in body_lines if bl)
        sections.append((current_level, current_heading, body_text))

    return sections


def split_markdown_into_sections(content: str) -> List[Tuple[int, str, str]]:
    """
    Split content into heading + body pairs.

    Auto-detects whether the content is:
    1. Standard markdown with # headings
    2. Raw pdftotext output with indented section numbers

    Returns list of (level, heading, body) tuples where:
    - level is the heading hierarchy depth
    - heading is the section text (e.g., "6.4.2 Technical safety requirements")
    - body is all content until the next heading

    Args:
        content: Full file content (markdown or pdftotext)

    Returns:
        List of (level, heading, body) tuples
    """
    # Auto-detect format
    if _detect_pdftotext_format(content):
        return split_pdftotext_into_sections(content)

    # Standard markdown parsing (original logic)
    sections = []
    lines = content.split('\n')

    current_heading = None
    current_level = None
    current_body = []

    for line in lines:
        level = parse_heading_level(line)

        if level > 0:
            # Save previous section if exists
            if current_heading is not None:
                body_text = '\n'.join(current_body).strip()
                sections.append((current_level, current_heading, body_text))

            # Start new section
            current_heading = re.sub(r'^#+\s*', '', line)
            current_level = level
            current_body = []
        else:
            # Add to current body
            if current_heading is not None:
                current_body.append(line)

    # Don't forget the last section
    if current_heading is not None:
        body_text = '\n'.join(current_body).strip()
        sections.append((current_level, current_heading, body_text))

    return sections


def parse_markdown_standard(md_path: str) -> List[Dict]:
    """
    Parse a markdown file into a list of clause dictionaries.

    Output matches the JSON structure expected by agnostic_engine.py:
    {
        "part": "4",
        "title": "System level development",
        "clauses": [
            {
                "section": "6.4.2",
                "title": "Technical safety requirements",
                "type": "requirement",
                "text": "...",
                "tags": [...],
                "asil_level": "B-D",
                "notes": [...],
                "cross_references": [...]
            }
        ]
    }

    Args:
        md_path: Path to markdown file

    Returns:
        List of clause dictionaries (will be wrapped in output structure by caller)
    """
    if not os.path.exists(md_path):
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract part number from title and filename
    title_match = re.search(r'^#+\s*(.+?)(?:\n|$)', content)
    doc_title = title_match.group(1) if title_match else ""
    part_number = detect_part_number(doc_title, os.path.basename(md_path))

    # Split into sections
    sections = split_markdown_into_sections(content)

    clauses = []

    # Process each section (skip level 1, which is the document title)
    for level, heading, body in sections:
        if level <= 1:
            # Skip document title
            continue

        section_id, section_title = extract_section_id(heading)

        if not section_id:
            # Skip headings without section IDs
            continue

        # Skip overview sections (Scope, Normative references, etc.) if desired
        # For now, include them with type "overview"

        clause = {
            "section": section_id,
            "title": section_title,
            "type": classify_clause(body),
            "text": body,
            "tags": extract_tags(body),
            "asil_level": extract_asil_level(body),
            "notes": extract_notes(body),
            "cross_references": extract_cross_references(body)
        }

        clauses.append(clause)

    return clauses


def parse_markdown_directory(dir_path: str) -> Dict:
    """
    Parse all .md files in a directory into a combined structure.

    Processes each .md file separately, extracting part numbers and combining results.

    Args:
        dir_path: Path to directory containing markdown files

    Returns:
        Dict with structure {part: {title, clauses}} if multiple parts,
        or simplified structure if single file
    """
    if not os.path.isdir(dir_path):
        raise NotADirectoryError(f"Directory not found: {dir_path}")

    results = {}

    # Find all .md files
    md_files = sorted(Path(dir_path).glob('*.md'))

    for md_file in md_files:
        try:
            clauses = parse_markdown_standard(str(md_file))

            # Extract part number and title
            with open(md_file, 'r', encoding='utf-8') as f:
                first_line = f.readline()

            title_match = re.search(r'^#+\s*(.+?)(?:\n|$)', first_line)
            doc_title = title_match.group(1) if title_match else md_file.stem
            part_number = detect_part_number(doc_title, md_file.name)

            if part_number:
                results[part_number] = {
                    "title": doc_title,
                    "clauses": clauses
                }
        except Exception as e:
            print(f"Warning: Failed to parse {md_file}: {e}")

    return results


def build_compliance_json(clauses: List[Dict], part: str, title: str) -> Dict:
    """
    Build the final JSON structure expected by the compliance engine.

    Args:
        clauses: List of clause dictionaries from parser
        part: Part number (e.g., "4")
        title: Part title

    Returns:
        Dictionary with structure: {part, title, clauses}
    """
    return {
        "part": part,
        "title": title,
        "clauses": clauses
    }


def parse_and_save(md_path: str, output_json: str = None) -> str:
    """
    Parse markdown and save to JSON file.

    Args:
        md_path: Input markdown file path
        output_json: Output JSON file path (defaults to input with .json extension)

    Returns:
        Path to output JSON file
    """
    if output_json is None:
        output_json = os.path.splitext(md_path)[0] + '.json'

    # Parse the markdown
    clauses = parse_markdown_standard(md_path)

    # Extract part and title info
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    title_match = re.search(r'^#+\s*(.+?)(?:\n|$)', content)
    doc_title = title_match.group(1) if title_match else "Unknown"
    part_number = detect_part_number(doc_title, os.path.basename(md_path))

    # Build output structure
    output = build_compliance_json(clauses, part_number, doc_title)

    # Write JSON
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return output_json


def main():
    """CLI entry point for parsing markdown files."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python markdown_parser.py <input.md|directory> [output.json]")
        print()
        print("Examples:")
        print("  python markdown_parser.py iso_26262_part_4.md")
        print("  python markdown_parser.py iso_26262_part_4.md output.json")
        print("  python markdown_parser.py ./iso_standards/")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        if os.path.isfile(input_path):
            # Parse single markdown file
            result_path = parse_and_save(input_path, output_path)
            print(f"Success: Parsed {input_path}")
            print(f"Output: {result_path}")

            # Print preview
            with open(result_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"Part: {data['part']}")
            print(f"Title: {data['title']}")
            print(f"Clauses: {len(data['clauses'])}")

        elif os.path.isdir(input_path):
            # Parse directory
            results = parse_markdown_directory(input_path)
            print(f"Parsed {len(results)} markdown files")
            for part, data in results.items():
                print(f"  Part {part}: {data['title']} ({len(data['clauses'])} clauses)")

        else:
            print(f"Error: {input_path} is neither a file nor directory")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
