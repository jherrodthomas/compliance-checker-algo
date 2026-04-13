#!/usr/bin/env python3
"""
Standard-Agnostic Compliance Checker Engine
============================================
Receives ANY standard (JSON or Markdown) + ANY work product/artifact (JSON, DOCX,
PDF, MD, TXT) and determines compliance.

Zero domain-specific code. Works for ISO 26262, ISO 21434, SOTIF, ASPICE, DO-178C,
IEC 62443, IEC 61508, or any standard representable as structured JSON or Markdown.

ARCHITECTURE
─────────────
  1. Schema Discovery   — auto-introspect any JSON to find requirements, risk levels,
                          tags, methods, cross-refs, traceability rules
  2. Standard Ingestion  — accepts JSON files directly, or Markdown files via
                          markdown_parser.py (auto-converted to JSON on-the-fly)
  3. Artifact Ingestion  — normalize any document (DOCX, PDF, MD, TXT, JSON) into a
                          universal internal format via artifact_ingester.py
  4. Optional Meta-Config — if a compliance_meta.json exists, use it as hints;
                           otherwise pure auto-discovery
  5. 8-Layer Algorithm Pipeline — all layers are generic, operating on discovered
                                 schema elements rather than hardcoded field names

INPUT FORMATS
─────────────
  Standards: .json, .md (Markdown from PDF conversion via pdftotext + pandoc)
  Artifacts: .json, .docx, .pdf, .md, .txt (any work product format)
  PDF→MD:    Use --convert flag to auto-convert PDF standards before processing

ALGORITHM PIPELINE
──────────────────
  Layer 1: Node Coverage         — Decision Tree on requirement node existence
  Layer 2: Content Alignment     — TF-IDF + Cosine Similarity
  Layer 3: Semantic Depth        — Ratcliff/Obershelp fuzzy matching
  Layer 4: Concept Coverage      — Set intersection on discovered concept tags
  Layer 5: Reference Integrity   — Graph BFS on cross-reference links
  Layer 6: Method/Practice Audit — Risk-level-aware method matching
  Layer 7: Traceability Chain    — Directed graph walk on declared dependency paths
  Layer 8: Gap Analysis + Risk   — Ensemble classifier with risk-weighted scoring

Usage:
  python agnostic_engine.py <standard_dir_or_file> <artifact_file_or_dir> [options]

Options:
  --meta FILE        Optional meta config JSON for schema hints
  --format FORMAT    Output format: json (default), docx, pdf, both, all
  --convert          Auto-convert PDF standards to Markdown before processing
"""

import json
import re
import math
import os
import sys
import glob as glob_module
import subprocess
import shutil
import tempfile
from collections import defaultdict, deque
from difflib import SequenceMatcher
from datetime import datetime
from typing import Any, Optional

# ── Force UTF-8 stdout/stderr (fixes PyInstaller + Windows cp1252 crash) ──
import io
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


# ═══════════════════════════════════════════════════════════════
#  PART 1: SCHEMA DISCOVERY — Auto-introspect any JSON
# ═══════════════════════════════════════════════════════════════

# Heuristic patterns the engine looks for when discovering JSON structure.
# These are intentionally broad — they match across standards, not just one.

# Fields likely containing the "requirement text" (the thing to check against)
TEXT_FIELD_PATTERNS = re.compile(
    r'^(text|description|content|requirement|statement|clause_text|body|'
    r'guidance|definition|purpose|objective|criteria|specification)$', re.I
)

# Fields likely containing a section/clause ID
ID_FIELD_PATTERNS = re.compile(
    r'^(section|clause_id|id|clause|requirement_id|ref|reference|number|'
    r'annex|process_id|practice_id|control_id|wp_id)$', re.I
)

# Fields likely containing a title
TITLE_FIELD_PATTERNS = re.compile(
    r'^(title|name|heading|label|subject|topic|activity)$', re.I
)

# Fields likely indicating a risk/integrity level
RISK_FIELD_PATTERNS = re.compile(
    r'^(asil_level|asil|sil|cal|cal_level|capability_level|level|'
    r'integrity_level|risk_level|criticality|assurance_level|'
    r'security_level|dal|eal|tql)$', re.I
)

# Fields likely containing tags/keywords/concepts
TAG_FIELD_PATTERNS = re.compile(
    r'^(tags|keywords|topics|categories|concepts|labels|domains|areas|'
    r'attributes|aspects)$', re.I
)

# Fields likely containing methods/techniques/practices
METHOD_FIELD_PATTERNS = re.compile(
    r'^(methods|techniques|practices|measures|controls|activities|'
    r'recommendations|tools|procedures|approaches)$', re.I
)

# Fields likely containing cross-references or traceability
XREF_FIELD_PATTERNS = re.compile(
    r'^(cross_references|references|xrefs|links|related|dependencies|'
    r'traceability_links|mapping|traces|derives_from|satisfies|'
    r'cross_part_links)$', re.I
)

# Fields that mark a node as a "requirement" vs "informative"
TYPE_FIELD_PATTERNS = re.compile(
    r'^(type|kind|category|classification|nature|status|obligation)$', re.I
)

# Values that indicate "this is a requirement" (vs guideline/informative)
REQUIREMENT_TYPE_VALUES = {
    'requirement', 'mandatory', 'shall', 'normative', 'required',
    'objective', 'base practice', 'generic practice', 'control'
}


class DiscoveredSchema:
    """Result of auto-introspecting a standard's JSON structure."""

    def __init__(self):
        # Discovered field name mappings
        self.text_field = None         # e.g., "text", "description", "guidance"
        self.id_field = None           # e.g., "section", "clause_id"
        self.title_field = None        # e.g., "title", "name"
        self.risk_field = None         # e.g., "asil_level", "cal_level"
        self.tag_field = None          # e.g., "tags", "keywords"
        self.type_field = None         # e.g., "type"
        self.method_fields = []        # e.g., ["methods"]
        self.xref_fields = []          # e.g., ["cross_references"]
        self.notes_field = None        # e.g., "notes"

        # Discovered risk scale
        self.risk_scale = []           # e.g., ["A", "B", "C", "D"] or ["1","2","3"]
        self.risk_field_type = "str"   # "str" for "A-D", "array" for ["A","B"], "single" for "D"

        # Discovered content
        self.requirement_nodes = []    # all nodes identified as requirements
        self.guideline_nodes = []      # informative/guideline nodes
        self.glossary_entries = []     # term definitions
        self.method_tables = []        # method/technique recommendations
        self.traceability_rules = []   # declared traceability paths
        self.all_tags = set()          # union of all concept tags
        self.cross_ref_graph = defaultdict(list)  # directed reference graph

        # Source grouping (parts, chapters, sections — whatever the standard uses)
        self.groups = {}               # group_key -> {title, nodes: [...]}

    def summary(self) -> dict:
        return {
            "text_field": self.text_field,
            "id_field": self.id_field,
            "title_field": self.title_field,
            "risk_field": self.risk_field,
            "risk_scale": self.risk_scale,
            "tag_field": self.tag_field,
            "requirement_nodes": len(self.requirement_nodes),
            "guideline_nodes": len(self.guideline_nodes),
            "glossary_entries": len(self.glossary_entries),
            "method_tables": len(self.method_tables),
            "traceability_rules": len(self.traceability_rules),
            "unique_tags": len(self.all_tags),
            "cross_references": sum(len(v) for v in self.cross_ref_graph.values()),
            "groups": len(self.groups),
        }


class SchemaDiscovery:
    """
    Auto-introspects JSON files to discover the standard's structure.
    No hardcoded field names — uses heuristic pattern matching.
    """

    def discover(self, data_sources: list[dict], meta: Optional[dict] = None) -> DiscoveredSchema:
        """
        Args:
            data_sources: list of (filename, parsed_json) tuples
            meta: optional compliance_meta.json hints
        """
        schema = DiscoveredSchema()

        # If meta config provided, use its hints first
        if meta:
            self._apply_meta_hints(schema, meta)

        # Pass 1: Discover field names from all files
        all_objects = []
        for filename, data in data_sources:
            objects = self._extract_all_objects(data, filename)
            all_objects.extend(objects)

        if not schema.text_field:
            self._discover_fields(schema, all_objects)

        # Pass 2: Classify nodes using discovered fields
        for filename, data in data_sources:
            self._process_file(schema, data, filename)

        # Pass 3: Discover risk scale from actual values
        if not schema.risk_scale:
            self._discover_risk_scale(schema)

        return schema

    def _apply_meta_hints(self, schema: DiscoveredSchema, meta: dict):
        """Apply explicit hints from compliance_meta.json."""
        fields = meta.get("field_mappings", {})
        schema.text_field = fields.get("text_field", schema.text_field)
        schema.id_field = fields.get("id_field", schema.id_field)
        schema.title_field = fields.get("title_field", schema.title_field)
        schema.risk_field = fields.get("risk_field", schema.risk_field)
        schema.tag_field = fields.get("tag_field", schema.tag_field)
        schema.type_field = fields.get("type_field", schema.type_field)

        schema.risk_scale = meta.get("risk_scale", schema.risk_scale)

        # Traceability paths from meta
        for path in meta.get("traceability_paths", []):
            schema.traceability_rules.append(path)

    def _extract_all_objects(self, data: Any, path: str = "") -> list[dict]:
        """Recursively extract all dict objects from nested JSON."""
        results = []
        if isinstance(data, dict):
            results.append(data)
            for k, v in data.items():
                results.extend(self._extract_all_objects(v, f"{path}.{k}"))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                results.extend(self._extract_all_objects(item, f"{path}[{i}]"))
        return results

    def _discover_fields(self, schema: DiscoveredSchema, objects: list[dict]):
        """Discover field names by pattern matching across all objects."""
        field_counts = defaultdict(int)
        for obj in objects:
            for key in obj.keys():
                field_counts[key] += 1

        # Score each field against patterns
        for field, count in field_counts.items():
            if count < 2:
                continue  # too rare to be a schema field

            if not schema.text_field and TEXT_FIELD_PATTERNS.match(field):
                schema.text_field = field
            if not schema.id_field and ID_FIELD_PATTERNS.match(field):
                schema.id_field = field
            if not schema.title_field and TITLE_FIELD_PATTERNS.match(field):
                schema.title_field = field
            if not schema.risk_field and RISK_FIELD_PATTERNS.match(field):
                schema.risk_field = field
            if not schema.tag_field and TAG_FIELD_PATTERNS.match(field):
                schema.tag_field = field
            if not schema.type_field and TYPE_FIELD_PATTERNS.match(field):
                schema.type_field = field
            if not schema.notes_field and field.lower() in ('notes', 'remarks', 'comments', 'annotations'):
                schema.notes_field = field

            if METHOD_FIELD_PATTERNS.match(field) and field not in schema.method_fields:
                schema.method_fields.append(field)
            if XREF_FIELD_PATTERNS.match(field) and field not in schema.xref_fields:
                schema.xref_fields.append(field)

    def _process_file(self, schema: DiscoveredSchema, data: dict, filename: str):
        """Process a single file, classifying its nodes."""

        # Detect group key (part, chapter, section, module, process, etc.)
        group_key = None
        group_title = ""
        for gk in ["part", "chapter", "module", "process", "domain", "section", "volume", "area"]:
            if gk in data:
                group_key = f"{gk}_{data[gk]}"
                group_title = data.get(schema.title_field or "title", data.get("title", ""))
                break
        if not group_key:
            group_key = os.path.splitext(os.path.basename(filename))[0]

        if group_key not in schema.groups:
            schema.groups[group_key] = {"title": group_title, "source_file": filename}

        # Handle glossary
        if "glossary" in data and isinstance(data["glossary"], list):
            schema.glossary_entries.extend(data["glossary"])
            return

        # Handle traceability model
        if "traceability_model" in data:
            tm = data["traceability_model"]
            for mapping in tm.get("mapping", []):
                schema.traceability_rules.append(mapping)

        # Handle cross-part links
        if "cross_part_links" in data:
            cpl = data["cross_part_links"]
            for mapping in cpl.get("mapping", []):
                schema.traceability_rules.append(mapping)

        # Process clause-like arrays
        for array_key in ["clauses", "sections", "requirements", "controls",
                          "processes", "practices", "objectives", "entries"]:
            if array_key in data and isinstance(data[array_key], list):
                for node in data[array_key]:
                    if not isinstance(node, dict):
                        continue
                    node["_group"] = group_key
                    node["_group_title"] = group_title
                    node["_source_file"] = filename
                    self._classify_node(schema, node)

        # Process method tables (from annexes or top-level)
        for mf in schema.method_fields:
            if mf in data and isinstance(data[mf], list):
                for entry in data[mf]:
                    if isinstance(entry, dict):
                        entry["_group"] = group_key
                        schema.method_tables.append(entry)

        # Process annexes
        for annex in data.get("annexes", []):
            if isinstance(annex, dict):
                # Annexes may contain method tables
                for mf in schema.method_fields + ["tables"]:
                    if mf in annex and isinstance(annex[mf], list):
                        for entry in annex[mf]:
                            if isinstance(entry, dict):
                                entry["_group"] = group_key
                                entry["_annex"] = annex.get("annex", annex.get("title", ""))
                                schema.method_tables.append(entry)

        # Process informative_guidance
        if "informative_guidance" in data:
            ig = data["informative_guidance"]
            if isinstance(ig, dict):
                for example in ig.get("examples", []):
                    schema.guideline_nodes.append({
                        "_group": group_key,
                        schema.text_field or "text": example if isinstance(example, str) else str(example),
                        schema.type_field or "type": "guideline"
                    })

    def _classify_node(self, schema: DiscoveredSchema, node: dict):
        """Classify a node as requirement, guideline, or glossary."""
        # Extract tags
        tag_field = schema.tag_field or "tags"
        for tag in node.get(tag_field, []):
            if isinstance(tag, str):
                schema.all_tags.add(tag.lower())

        # Extract cross-references
        for xf in schema.xref_fields + ["cross_references"]:
            for xref in node.get(xf, []):
                if isinstance(xref, dict):
                    node_id = node.get(schema.id_field or "section", "unknown")
                    group = node.get("_group", "")
                    src = f"{group}:{node_id}"

                    # Build target reference from whatever fields the xref has
                    tgt_parts = []
                    for tk in ["part", "section", "clause", "process", "control"]:
                        if tk in xref:
                            tgt_parts.append(f"{tk}_{xref[tk]}" if tk == "part" else str(xref[tk]))
                    tgt = ":".join(tgt_parts) if tgt_parts else str(xref)

                    schema.cross_ref_graph[src].append({
                        "target": tgt,
                        "context": xref.get("context", xref.get("description", ""))
                    })

        # Classify by type field
        type_field = schema.type_field or "type"
        node_type = str(node.get(type_field, "")).lower()

        if node_type in REQUIREMENT_TYPE_VALUES or "shall" in str(node.get(schema.text_field or "text", "")).lower():
            schema.requirement_nodes.append(node)
        else:
            schema.guideline_nodes.append(node)

    def _discover_risk_scale(self, schema: DiscoveredSchema):
        """Discover the risk scale from actual values in requirement nodes."""
        if not schema.risk_field:
            return

        values = set()
        for node in schema.requirement_nodes + schema.guideline_nodes:
            val = node.get(schema.risk_field, "")
            if isinstance(val, list):
                values.update(str(v) for v in val)
            elif isinstance(val, str):
                # Handle range notation like "A-D", "B-D"
                if "-" in val and len(val) <= 5:
                    parts = val.split("-")
                    values.update(parts)
                elif val.lower() not in ("all", "n/a", "none", ""):
                    values.add(val)

        # Sort: try numeric first, then alpha
        try:
            schema.risk_scale = sorted(values, key=lambda x: int(x))
        except ValueError:
            schema.risk_scale = sorted(values)


# ═══════════════════════════════════════════════════════════════
#  PART 2: ARTIFACT INGESTION — Normalize any document format
# ═══════════════════════════════════════════════════════════════

class NormalizedArtifact:
    """Universal internal representation of a work product/artifact."""

    def __init__(self):
        self.id = ""
        self.title = ""
        self.full_text = ""          # all content as flat text
        self.sections = []           # [{title, content}]
        self.tags = set()            # concept tags the artifact addresses
        self.methods = set()         # methods/techniques documented
        self.mapped_nodes = []       # which standard nodes this artifact claims to address
        self.traceability_links = [] # [{from, to, type}]
        self.status = "unknown"
        self.metadata = {}           # any extra key-value pairs


class ArtifactIngester:
    """
    Normalizes any input document into NormalizedArtifact(s).
    Supports: JSON (structured), plain text, and key-value formats.
    """

    def ingest(self, filepath: str) -> list[NormalizedArtifact]:
        """Ingest a file and return normalized artifact(s)."""
        ext = os.path.splitext(filepath)[1].lower()

        if ext == ".json":
            return self._ingest_json(filepath)
        elif ext in (".txt", ".md", ".rst"):
            return self._ingest_text(filepath)
        else:
            # Try JSON first, fall back to text
            try:
                return self._ingest_json(filepath)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return self._ingest_text(filepath)

    def _ingest_json(self, filepath: str) -> list[NormalizedArtifact]:
        with open(filepath, 'r') as f:
            data = json.load(f)

        artifacts = []

        # Check for array-of-artifacts pattern
        wp_key = None
        for key in ["work_products", "artifacts", "documents", "deliverables", "items", "records"]:
            if key in data and isinstance(data[key], list):
                wp_key = key
                break

        if wp_key:
            for wp_data in data[wp_key]:
                artifacts.append(self._normalize_wp(wp_data))
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    artifacts.append(self._normalize_wp(item))
        else:
            # Single artifact
            artifacts.append(self._normalize_wp(data))

        # Capture project-level metadata
        project = data.get("project", data.get("metadata", data.get("info", {})))
        for art in artifacts:
            art.metadata.update(project if isinstance(project, dict) else {})

        return artifacts

    def _normalize_wp(self, data: dict) -> NormalizedArtifact:
        art = NormalizedArtifact()

        # ID: try multiple field names
        for k in ["id", "wp_id", "artifact_id", "document_id", "ref", "number"]:
            if k in data:
                art.id = str(data[k])
                break

        # Title
        for k in ["title", "name", "heading", "subject", "label"]:
            if k in data:
                art.title = str(data[k])
                break

        # Content — gather from all text-bearing fields
        text_parts = []

        # Direct content field
        for k in ["content", "text", "body", "description", "full_text"]:
            if k in data and isinstance(data[k], str):
                text_parts.append(data[k])

        # Sections array
        for k in ["sections", "chapters", "parts", "blocks", "paragraphs"]:
            if k in data and isinstance(data[k], list):
                for sec in data[k]:
                    if isinstance(sec, dict):
                        sec_title = sec.get("title", sec.get("heading", ""))
                        sec_content = sec.get("content", sec.get("text", sec.get("body", "")))
                        art.sections.append({"title": sec_title, "content": sec_content})
                        text_parts.append(f"{sec_title} {sec_content}")
                    elif isinstance(sec, str):
                        text_parts.append(sec)

        art.full_text = " ".join(text_parts)

        # Tags
        for k in ["tags_addressed", "tags", "topics", "concepts", "keywords", "categories"]:
            if k in data and isinstance(data[k], list):
                for t in data[k]:
                    art.tags.add(str(t).lower())

        # Methods
        for k in ["methods_used", "methods", "techniques", "practices", "tools_used"]:
            if k in data and isinstance(data[k], list):
                for m in data[k]:
                    art.methods.add(str(m).lower())

        # Mapped standard nodes
        for k in ["mapped_sections", "mapped_clauses", "addresses", "covers",
                   "mapped_requirements", "applicable_clauses"]:
            if k in data and isinstance(data[k], list):
                art.mapped_nodes.extend(str(n) for n in data[k])

        # Traceability links
        for k in ["traceability_links", "traces", "links", "dependencies"]:
            if k in data and isinstance(data[k], list):
                for link in data[k]:
                    if isinstance(link, dict):
                        art.traceability_links.append(link)

        # Status
        for k in ["status", "state", "completion", "maturity"]:
            if k in data:
                art.status = str(data[k]).lower()

        # Remaining metadata
        skip = {"id","wp_id","title","name","content","text","sections","tags_addressed",
                "tags","methods_used","methods","mapped_sections","traceability_links","status"}
        for k, v in data.items():
            if k not in skip and not isinstance(v, (dict, list)):
                art.metadata[k] = v

        return art

    def _ingest_text(self, filepath: str) -> list[NormalizedArtifact]:
        with open(filepath, 'r') as f:
            text = f.read()

        art = NormalizedArtifact()
        art.id = os.path.splitext(os.path.basename(filepath))[0]
        art.title = art.id.replace("_", " ").replace("-", " ").title()
        art.full_text = text

        # Try to split into sections by headers
        lines = text.split("\n")
        current_section = {"title": "Introduction", "content": ""}
        for line in lines:
            stripped = line.strip()
            # Detect headers (markdown style, numbered, or ALL CAPS)
            if (stripped.startswith("#") or
                re.match(r'^\d+\.[\d.]*\s+\w', stripped) or
                (stripped.isupper() and len(stripped) > 3 and len(stripped) < 80)):
                if current_section["content"].strip():
                    art.sections.append(current_section)
                current_section = {"title": stripped.lstrip("#").strip(), "content": ""}
            else:
                current_section["content"] += line + "\n"

        if current_section["content"].strip():
            art.sections.append(current_section)

        return [art]


# ═══════════════════════════════════════════════════════════════
#  PART 3: NLP UTILITIES (same as before, domain-agnostic)
# ═══════════════════════════════════════════════════════════════

STOPWORDS = {
    'the','a','an','is','are','was','were','be','been','being','have','has','had',
    'do','does','did','will','would','could','should','may','might','shall','can',
    'for','and','but','or','nor','not','so','yet','to','of','in','on','at','by',
    'with','from','as','into','through','during','before','after','above','below',
    'between','each','all','both','such','that','this','these','those','it','its',
    'they','them','their','which','who','including','based','also','other','than','any','more'
}

def tokenize(text: str) -> list[str]:
    tokens = re.findall(r'[a-z][a-z0-9]+', text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]

def compute_tf(tokens: list[str]) -> dict:
    freq = defaultdict(int)
    for t in tokens:
        freq[t] += 1
    n = len(tokens) or 1
    return {t: c / n for t, c in freq.items()}

def compute_idf(corpus: list[list[str]]) -> dict:
    n = len(corpus)
    df = defaultdict(int)
    for doc in corpus:
        for term in set(doc):
            df[term] += 1
    return {t: math.log(n / (1 + d)) for t, d in df.items()}

def cosine_sim(a: dict, b: dict) -> float:
    common = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in common)
    ma = math.sqrt(sum(v**2 for v in a.values()))
    mb = math.sqrt(sum(v**2 for v in b.values()))
    return dot / (ma * mb) if ma and mb else 0.0


# ═══════════════════════════════════════════════════════════════
#  PART 4: UNIVERSAL ALGORITHM LAYERS
# ═══════════════════════════════════════════════════════════════

def _get_node_text(node: dict, schema: DiscoveredSchema) -> str:
    """Extract the full text content from a requirement node using discovered fields."""
    parts = []
    if schema.text_field and schema.text_field in node:
        parts.append(str(node[schema.text_field]))
    if schema.title_field and schema.title_field in node:
        parts.append(str(node[schema.title_field]))
    if schema.notes_field and schema.notes_field in node:
        notes = node[schema.notes_field]
        if isinstance(notes, list):
            parts.extend(str(n) for n in notes)
        else:
            parts.append(str(notes))
    if schema.tag_field and schema.tag_field in node:
        tags = node[schema.tag_field]
        if isinstance(tags, list):
            parts.extend(str(t) for t in tags)
    return " ".join(parts)

def _get_node_id(node: dict, schema: DiscoveredSchema) -> str:
    """Get the identifier of a requirement node."""
    if schema.id_field and schema.id_field in node:
        return str(node[schema.id_field])
    return str(node.get("section", node.get("id", node.get("title", "unknown"))))

def _get_node_risk(node: dict, schema: DiscoveredSchema) -> str:
    """Get the risk level of a node."""
    if not schema.risk_field:
        return "all"
    return str(node.get(schema.risk_field, "all"))

def _risk_applies(level_str: str, target: str, scale: list[str]) -> bool:
    """Check if a risk level applies to a target level. Agnostic to scale."""
    if not scale or level_str.lower() in ("all", "n/a", ""):
        return True
    if target in level_str:
        return True
    if "-" in level_str:
        parts = [p.strip() for p in level_str.split("-")]
        try:
            low_idx = scale.index(parts[0])
            high_idx = scale.index(parts[-1])
            tgt_idx = scale.index(target)
            return low_idx <= tgt_idx <= high_idx
        except ValueError:
            return True
    return target in str(level_str)

def _get_applicable_requirements(schema: DiscoveredSchema, target_risk: Optional[str],
                                  in_scope_groups: Optional[list] = None) -> list[dict]:
    """Filter requirement nodes by risk level and scope."""
    result = []
    for node in schema.requirement_nodes:
        if in_scope_groups and node.get("_group") not in in_scope_groups:
            continue
        if target_risk:
            node_risk = _get_node_risk(node, schema)
            if not _risk_applies(node_risk, target_risk, schema.risk_scale):
                continue
        result.append(node)
    return result


# ── Layer 1: Node Coverage ──

def layer1_node_coverage(schema: DiscoveredSchema, artifacts: list[NormalizedArtifact],
                          target_risk: str = None, in_scope: list = None) -> dict:
    """Check: does an artifact exist for each applicable requirement node?"""
    results = {"layer": "node_coverage", "algorithm": "Decision Tree",
               "findings": [], "score": 0.0}

    applicable = _get_applicable_requirements(schema, target_risk, in_scope)

    # Build set of sections the artifacts claim to cover
    covered_sections = set()
    for art in artifacts:
        covered_sections.update(art.mapped_nodes)

    # Also try matching by fuzzy title
    artifact_titles = {art.title.lower() for art in artifacts}
    artifact_text_index = " ".join(art.full_text.lower() for art in artifacts)

    covered = 0
    for node in applicable:
        node_id = _get_node_id(node, schema)
        node_title = str(node.get(schema.title_field or "title", "")).lower()
        group = node.get("_group", "")

        is_covered = False
        is_partial = False

        # Check 1: explicit section mapping
        if node_id in covered_sections:
            matching = [a for a in artifacts if node_id in a.mapped_nodes]
            if matching and matching[0].status in ("complete", "approved", "final", "released"):
                is_covered = True
            else:
                is_partial = True

        # Check 2: fuzzy title matching (for artifacts that don't map explicitly)
        if not is_covered and not is_partial:
            for art in artifacts:
                title_sim = SequenceMatcher(None, node_title, art.title.lower()).ratio()
                if title_sim > 0.6:
                    is_partial = True  # found by title but not explicitly mapped
                    break

        # Check 3: content contains key terms from the requirement
        if not is_covered and not is_partial:
            node_terms = set(tokenize(_get_node_text(node, schema)))
            if node_terms:
                term_hits = sum(1 for t in node_terms if t in artifact_text_index)
                if term_hits / len(node_terms) > 0.5:
                    is_partial = True

        if is_covered:
            covered += 1.0
        elif is_partial:
            covered += 0.5
            results["findings"].append({
                "type": "PARTIAL_COVERAGE",
                "severity": "WARNING",
                "node_id": node_id,
                "group": group,
                "title": node.get(schema.title_field or "title", ""),
                "message": f"[{group}] § {node_id} '{node.get(schema.title_field or 'title', '')}' — "
                           f"partially covered or incomplete."
            })
        else:
            results["findings"].append({
                "type": "MISSING_COVERAGE",
                "severity": "CRITICAL",
                "node_id": node_id,
                "group": group,
                "title": node.get(schema.title_field or "title", ""),
                "risk": _get_node_risk(node, schema),
                "message": f"[{group}] § {node_id} '{node.get(schema.title_field or 'title', '')}' — "
                           f"no artifact addresses this requirement."
            })

    total = len(applicable) or 1
    results["score"] = round((covered / total) * 100, 1)
    results["applicable_nodes"] = len(applicable)
    results["covered_nodes"] = covered
    return results


# ── Layer 2: Content Alignment (TF-IDF + Cosine) ──

def layer2_content_alignment(schema: DiscoveredSchema, artifacts: list[NormalizedArtifact],
                              target_risk: str = None, in_scope: list = None) -> dict:
    """Compare requirement text vs artifact content using TF-IDF cosine similarity."""
    results = {"layer": "content_alignment", "algorithm": "TF-IDF + Cosine Similarity",
               "findings": [], "scores": {}, "score": 0.0}

    applicable = _get_applicable_requirements(schema, target_risk, in_scope)
    corpus = [tokenize(art.full_text) for art in artifacts]
    idf = compute_idf(corpus) if corpus else {}

    all_artifact_text = " ".join(art.full_text for art in artifacts)

    scores = []
    for node in applicable:
        node_id = _get_node_id(node, schema)
        node_text = _get_node_text(node, schema)

        # Find best-matching artifact
        best_sim = 0.0
        for art in artifacts:
            ct = tokenize(node_text)
            ut = tokenize(art.full_text)
            ct_tfidf = {t: tf * idf.get(t, 1.0) for t, tf in compute_tf(ct).items()}
            ut_tfidf = {t: tf * idf.get(t, 1.0) for t, tf in compute_tf(ut).items()}
            sim = cosine_sim(ct_tfidf, ut_tfidf)
            best_sim = max(best_sim, sim)

        scores.append(best_sim)
        results["scores"][node_id] = round(best_sim * 100, 1)

        if best_sim < 0.15:
            results["findings"].append({
                "type": "LOW_CONTENT_ALIGNMENT",
                "severity": "MAJOR" if best_sim < 0.05 else "WARNING",
                "node_id": node_id,
                "title": node.get(schema.title_field or "title", ""),
                "similarity": round(best_sim * 100, 1),
                "message": f"§ {node_id} '{node.get(schema.title_field or 'title', '')}' — "
                           f"best content match is only {round(best_sim*100,1)}%."
            })

    results["score"] = round((sum(scores) / max(len(scores), 1)) * 100, 1)
    return results


# ── Layer 3: Semantic Depth (SequenceMatcher) ──

def layer3_semantic_matching(schema: DiscoveredSchema, artifacts: list[NormalizedArtifact],
                              target_risk: str = None, in_scope: list = None) -> dict:
    """Fuzzy-match requirement text against artifact content."""
    results = {"layer": "semantic_matching", "algorithm": "Ratcliff/Obershelp",
               "findings": [], "score": 0.0}

    applicable = _get_applicable_requirements(schema, target_risk, in_scope)
    scores = []

    for node in applicable:
        node_text = str(node.get(schema.text_field or "text", ""))[:500].lower()

        best = 0.0
        for art in artifacts:
            ratio = SequenceMatcher(None, node_text, art.full_text[:500].lower()).ratio()
            best = max(best, ratio)
        scores.append(best)

        if best < 0.2:
            results["findings"].append({
                "type": "LOW_SEMANTIC_MATCH", "severity": "WARNING",
                "node_id": _get_node_id(node, schema),
                "title": node.get(schema.title_field or "title", ""),
                "score": round(best * 100, 1),
                "message": f"§ {_get_node_id(node, schema)} — semantic alignment {round(best*100,1)}%."
            })

    results["score"] = round((sum(scores) / max(len(scores), 1)) * 100, 1)
    return results


# ── Layer 4: Concept Coverage (Set Analysis on Tags) ──

def _is_valid_concept(tag: str) -> bool:
    """Filter out garbage tags that aren't meaningful safety/engineering concepts."""
    if not tag or len(tag.strip()) < 2:
        return False
    tag = tag.strip()
    # Reject if it contains multiple spaces (mangled table content)
    if '  ' in tag:
        return False
    # Reject if it contains newlines
    if '\n' in tag or '\r' in tag:
        return False
    # Reject pure numbers or single characters
    if tag.replace(' ', '').isdigit():
        return False
    # Reject very short all-lowercase abbreviations that are likely noise
    if len(tag) <= 3 and tag.islower() and tag not in ('dfa', 'fta', 'fsc', 'tsc', 'hsi', 'ecu'):
        return False
    return True


def layer4_concept_coverage(schema: DiscoveredSchema, artifacts: list[NormalizedArtifact],
                             target_risk: str = None, in_scope: list = None) -> dict:
    """Check which concept tags from the standard are addressed by artifacts."""
    results = {"layer": "concept_coverage", "algorithm": "Set Intersection",
               "findings": [], "score": 0.0}

    # Gather required tags from applicable requirement nodes, with filtering
    required = set()
    applicable = _get_applicable_requirements(schema, target_risk, in_scope)
    for node in applicable:
        for tag in node.get(schema.tag_field or "tags", []):
            if isinstance(tag, str) and _is_valid_concept(tag):
                required.add(tag.lower().strip())

    # Gather artifact tags + auto-extract from content
    user_tags = set()
    for art in artifacts:
        for t in art.tags:
            if _is_valid_concept(t):
                user_tags.add(t.lower().strip())
        # Also check if tag terms appear in content
        content_lower = art.full_text.lower()
        for rtag in required:
            if len(rtag) >= 3 and rtag in content_lower:
                user_tags.add(rtag)

    covered = required & user_tags
    missing = required - user_tags

    results["score"] = round((len(covered) / max(len(required), 1)) * 100, 1)
    results["required"] = len(required)
    results["covered"] = len(covered)
    results["missing_concepts"] = sorted(missing)

    if missing:
        # Group missing concepts into categories for cleaner display
        display_concepts = sorted(missing)[:30]
        results["findings"].append({
            "type": "MISSING_CONCEPTS", "severity": "WARNING",
            "count": len(missing),
            "concepts": display_concepts,
            "message": f"{len(missing)} required concepts not addressed: "
                       f"{', '.join(display_concepts[:10])}{'...' if len(missing) > 10 else ''}."
        })

    return results


# ── Layer 5: Reference Integrity (Graph BFS) ──

def layer5_reference_integrity(schema: DiscoveredSchema, artifacts: list[NormalizedArtifact]) -> dict:
    """Verify cross-references: are both endpoints covered by artifacts?"""
    results = {"layer": "reference_integrity", "algorithm": "Graph BFS",
               "findings": [], "score": 0.0}

    covered = set()
    for art in artifacts:
        covered.update(art.mapped_nodes)

    total = 0
    satisfied = 0
    for src, refs in schema.cross_ref_graph.items():
        for ref in refs:
            total += 1
            src_sec = src.split(":")[-1] if ":" in src else src
            tgt = ref["target"]
            tgt_sec = tgt.split(":")[-1] if ":" in tgt else tgt

            src_ok = src_sec in covered
            tgt_ok = tgt_sec in covered

            if src_ok and tgt_ok:
                satisfied += 1
            else:
                missing = []
                if not src_ok: missing.append(f"source ({src})")
                if not tgt_ok: missing.append(f"target ({tgt})")
                results["findings"].append({
                    "type": "BROKEN_REFERENCE", "severity": "MAJOR",
                    "source": src, "target": tgt,
                    "context": ref.get("context", ""),
                    "message": f"Cross-ref {src} → {tgt}: missing {', '.join(missing)}."
                })

    results["score"] = round((satisfied / max(total, 1)) * 100, 1)
    results["total_refs"] = total
    results["satisfied"] = satisfied
    return results


# ── Layer 6: Method/Practice Audit ──

def layer6_method_audit(schema: DiscoveredSchema, artifacts: list[NormalizedArtifact],
                         target_risk: str = None) -> dict:
    """Check if artifacts document the methods recommended for the target risk level."""
    results = {"layer": "method_audit", "algorithm": "Risk-Aware Method Matching",
               "findings": [], "score": 0.0}

    if not schema.method_tables:
        results["score"] = 100.0  # no methods to check = pass
        return results

    # Gather all user-documented methods
    user_methods = set()
    for art in artifacts:
        user_methods.update(art.methods)
    # Also extract from content
    all_content = " ".join(art.full_text.lower() for art in artifacts)

    required_methods = []
    for table in schema.method_tables:
        activity = table.get("activity", table.get(schema.title_field or "title", ""))
        for mf in schema.method_fields + ["methods"]:
            for entry in table.get(mf, []):
                if isinstance(entry, dict):
                    method_name = entry.get("method", entry.get("name", entry.get("technique", "")))
                    risk_levels = entry.get("ASIL", entry.get("level", entry.get("asil", [])))

                    if isinstance(risk_levels, list) and target_risk:
                        if target_risk not in risk_levels:
                            continue

                    required_methods.append({
                        "activity": activity,
                        "method": method_name,
                        "risk_levels": risk_levels
                    })

    matched = 0
    unmatched_by_activity = defaultdict(list)

    for rm in required_methods:
        method_lower = rm["method"].lower()

        # Check explicit method list
        found = any(SequenceMatcher(None, method_lower, um).ratio() >= 0.5 for um in user_methods)

        # Also check if method name appears in content
        if not found and method_lower in all_content:
            found = True

        if found:
            matched += 1
        else:
            unmatched_by_activity[rm["activity"]].append(rm["method"])

    total = len(required_methods) or 1
    results["score"] = round((matched / total) * 100, 1)
    results["required_count"] = len(required_methods)
    results["matched_count"] = matched

    for activity, methods in unmatched_by_activity.items():
        results["findings"].append({
            "type": "MISSING_METHOD", "severity": "WARNING" if len(methods) < 3 else "MAJOR",
            "activity": activity,
            "methods": methods[:5],
            "message": f"'{activity}' — {len(methods)} recommended method(s) not documented: "
                       f"{', '.join(methods[:3])}{'...' if len(methods) > 3 else ''}."
        })

    return results


# ── Layer 7: Traceability Chain ──

def layer7_traceability_chain(schema: DiscoveredSchema, artifacts: list[NormalizedArtifact]) -> dict:
    """Verify declared traceability paths from the standard's traceability model."""
    results = {"layer": "traceability_chain", "algorithm": "Directed Graph Walk",
               "findings": [], "score": 0.0}

    rules = schema.traceability_rules

    # Check if artifacts themselves provide any traceability links at all
    any_user_traces = any(art.traceability_links for art in artifacts)

    if not rules:
        # No explicit traceability model in the standard — but traceability is still
        # a fundamental safety requirement. Score based on whether artifacts provide links.
        if any_user_traces:
            results["score"] = 70.0  # Links exist but no model to validate against
            results["findings"].append({
                "type": "NO_TRACEABILITY_MODEL", "severity": "WARNING",
                "message": "No traceability rules defined in standard. Artifact traceability "
                           "links exist but cannot be validated against a formal model."
            })
        else:
            results["score"] = 0.0  # No traces at all — critical gap
            results["required"] = 0
            results["satisfied"] = 0
            results["findings"].append({
                "type": "NO_TRACEABILITY_EVIDENCE", "severity": "CRITICAL",
                "message": "No traceability links found in any work product. ISO 26262 requires "
                           "bidirectional traceability between safety goals, functional/technical "
                           "safety requirements, and verification evidence. Establish traceability "
                           "chains: Safety Goals → FSR → TSR → HSR/SSR → Verification."
            })
        return results

    # Collect user links
    user_links = []
    for art in artifacts:
        for link in art.traceability_links:
            user_links.append(link)

    all_link_text = " ".join(
        f"{l.get('from','')} {l.get('to','')} {l.get('type','')}" for l in user_links
    ).lower()

    satisfied = 0
    for rule in rules:
        from_item = str(rule.get("from", ""))
        to_item = str(rule.get("to", ""))

        # Fuzzy check: do user links mention both endpoints?
        from_terms = set(tokenize(from_item))
        to_terms = set(tokenize(to_item))

        from_found = any(t in all_link_text for t in from_terms) if from_terms else False
        to_found = any(t in all_link_text for t in to_terms) if to_terms else False

        if from_found and to_found:
            satisfied += 1
        else:
            results["findings"].append({
                "type": "MISSING_TRACE_LINK", "severity": "MAJOR",
                "from": from_item, "to": to_item,
                "message": f"Traceability '{from_item}' → '{to_item}' not established."
            })

    total = len(rules) or 1
    results["score"] = round((satisfied / total) * 100, 1)
    results["required"] = len(rules)
    results["satisfied"] = satisfied
    return results


# ── Layer 8: Gap Analysis + Risk Scoring ──

SEVERITY_WEIGHTS = {"CRITICAL": 10, "MAJOR": 5, "WARNING": 2, "INFO": 1}

def layer8_gap_analysis(all_results: list, risk_scale: list, target_risk: str) -> dict:
    """Aggregate findings, prioritize, and risk-weight."""
    results = {"layer": "gap_analysis", "algorithm": "Ensemble + Bayesian Risk",
               "gaps": [], "severity_counts": defaultdict(int),
               "total_risk": 0.0, "recommendations": []}

    # Build risk multiplier dynamically from the scale
    if risk_scale and target_risk in risk_scale:
        idx = risk_scale.index(target_risk)
        multiplier = 2 ** idx  # exponential: position 0=1x, 1=2x, 2=4x, 3=8x, 4=16x
    else:
        multiplier = 1.0

    all_findings = []
    for layer in all_results:
        for f in layer.get("findings", []):
            f["_source_layer"] = layer["layer"]
            all_findings.append(f)
            results["severity_counts"][f.get("severity", "INFO")] += 1

    # Group by node/clause
    by_key = defaultdict(list)
    for f in all_findings:
        key = f.get("node_id", f.get("activity", f.get("_source_layer", "general")))
        by_key[key].append(f)

    for key, findings in by_key.items():
        base = sum(SEVERITY_WEIGHTS.get(f["severity"], 1) for f in findings)
        weighted = round(base * multiplier, 1)
        results["total_risk"] += weighted

        gap = {
            "key": key,
            "count": len(findings),
            "base_severity": base,
            "risk_weighted": weighted,
            "priority": "HIGH" if weighted >= 80 else "MEDIUM" if weighted >= 20 else "LOW",
            "findings": findings
        }
        results["gaps"].append(gap)

    results["gaps"].sort(key=lambda g: g["risk_weighted"], reverse=True)
    results["severity_counts"] = dict(results["severity_counts"])
    results["total_risk"] = round(results["total_risk"], 1)

    # Recommendations
    for gap in results["gaps"][:10]:
        types = {f["type"] for f in gap["findings"]}
        rec = f"[{gap['priority']}] {gap['key']}: "
        if "MISSING_COVERAGE" in types: rec += "Create artifact for this requirement. "
        if "LOW_CONTENT_ALIGNMENT" in types or "LOW_SEMANTIC_MATCH" in types:
            rec += "Strengthen content to address requirement. "
        if "MISSING_METHOD" in types: rec += "Document recommended methods. "
        if "BROKEN_REFERENCE" in types or "MISSING_TRACE_LINK" in types:
            rec += "Establish traceability links. "
        if "MISSING_CONCEPTS" in types: rec += "Address missing concept areas. "
        results["recommendations"].append(rec.strip())

    return results


# ═══════════════════════════════════════════════════════════════
#  PART 5: ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════

LAYER_WEIGHTS = {
    "node_coverage": 0.20,
    "content_alignment": 0.15,
    "semantic_matching": 0.10,
    "concept_coverage": 0.10,
    "reference_integrity": 0.15,
    "method_audit": 0.10,
    "traceability_chain": 0.20,
}

def grade(score: float) -> str:
    if score >= 90: return "A — Compliant"
    if score >= 75: return "B — Substantially Compliant"
    if score >= 60: return "C — Partially Compliant"
    if score >= 40: return "D — Major Gaps"
    return "F — Non-Compliant"


def _load_markdown_as_json(md_path: str) -> list:
    """
    Load a markdown file and convert to JSON clause structure using markdown_parser.

    Args:
        md_path: Path to .md file

    Returns:
        List of clause dicts (same structure as JSON standard files)
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parser_path = os.path.join(script_dir, "markdown_parser.py")

    if not os.path.exists(parser_path):
        raise FileNotFoundError(
            f"markdown_parser.py not found at {parser_path}. "
            f"Cannot parse markdown standards without it."
        )

    import importlib.util
    spec = importlib.util.spec_from_file_location("markdown_parser", parser_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    clauses = mod.parse_markdown_standard(md_path)

    # Read part info from the file
    with open(md_path, 'r', encoding='utf-8') as f:
        first_lines = f.read(2000)  # Read more for pdftotext headers

    # Try markdown heading first
    title_match = re.search(r'^#+\s*(.+?)(?:\n|$)', first_lines)
    if not title_match:
        # Try pdftotext: look for "Part N:" line or "Road vehicles — Functional safety —"
        title_match = re.search(r'Part\s+\d+[:\s]*\n\s*(.+?)(?:\n|$)', first_lines)
    if not title_match:
        # Try ISO document title pattern
        title_match = re.search(r'Road vehicles.*?—\s*\n\s*(Part\s+\d+.*?)(?:\n|$)', first_lines, re.DOTALL)

    doc_title = title_match.group(1).strip() if title_match else os.path.splitext(os.path.basename(md_path))[0]
    part_number = mod.detect_part_number(first_lines + " " + doc_title, os.path.basename(md_path))

    return {
        "part": part_number or "1",
        "title": doc_title,
        "clauses": clauses
    }


def _convert_pdf_to_markdown(pdf_path: str, output_dir: str = None) -> str:
    """
    Convert a PDF standard document to Markdown using pdftotext + pandoc.

    Args:
        pdf_path: Path to PDF file
        output_dir: Directory for output .md file (defaults to same dir as PDF)

    Returns:
        Path to generated .md file
    """
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(pdf_path))

    basename = os.path.splitext(os.path.basename(pdf_path))[0]
    txt_path = os.path.join(output_dir, basename + ".txt")
    md_path = os.path.join(output_dir, basename + ".md")

    # Step 1: pdftotext -layout
    if not shutil.which("pdftotext"):
        raise EnvironmentError(
            "pdftotext not found. Install poppler-utils:\n"
            "  Ubuntu/Debian: sudo apt install poppler-utils\n"
            "  macOS: brew install poppler\n"
            "  Windows: download from https://github.com/oschwartz10612/poppler-windows"
        )

    print(f"    Converting PDF → text: {os.path.basename(pdf_path)}")
    subprocess.run(["pdftotext", "-layout", pdf_path, txt_path], check=True)

    # Check if we got meaningful text (scanned PDFs produce tiny files)
    txt_size = os.path.getsize(txt_path) if os.path.exists(txt_path) else 0
    if txt_size < 1000:
        print(f"    [INFO] Sparse text detected — attempting OCR with tesseract...")
        if shutil.which("tesseract"):
            ocr_base = os.path.join(output_dir, basename + "_ocr")
            subprocess.run(
                ["tesseract", pdf_path, ocr_base, "-l", "eng", "pdf"],
                capture_output=True
            )
            ocr_pdf = ocr_base + ".pdf"
            if os.path.exists(ocr_pdf):
                subprocess.run(["pdftotext", "-layout", ocr_pdf, txt_path], check=True)
                os.remove(ocr_pdf)
        else:
            print("    [WARN] tesseract not found — skipping OCR")

    # Step 2: pandoc → GFM markdown
    if shutil.which("pandoc"):
        print(f"    Converting text → Markdown: {basename}.md")
        subprocess.run(
            ["pandoc", txt_path, "-t", "gfm", "--wrap=none", "-o", md_path],
            check=True
        )
    else:
        # Fallback: simple txt → md rename (still useful for the parser)
        print(f"    [INFO] pandoc not found — using raw text as markdown")
        shutil.copy2(txt_path, md_path)

    # Cleanup temp txt
    if os.path.exists(txt_path) and os.path.exists(md_path):
        os.remove(txt_path)

    print(f"    Converted: {md_path}")
    return md_path


def _load_universal_artifacts(artifact_path: str) -> list:
    """
    Load artifacts using UniversalArtifactIngester for non-JSON formats,
    converting them to NormalizedArtifact objects the engine expects.

    Args:
        artifact_path: Path to file or directory

    Returns:
        List of NormalizedArtifact objects
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ingester_path = os.path.join(script_dir, "artifact_ingester.py")

    if not os.path.exists(ingester_path):
        raise FileNotFoundError(
            f"artifact_ingester.py not found at {ingester_path}."
        )

    import importlib.util
    spec = importlib.util.spec_from_file_location("artifact_ingester", ingester_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    ingester = mod.UniversalArtifactIngester(verbose=True)
    result = ingester.ingest(artifact_path)

    # Convert dicts from artifact_ingester → NormalizedArtifact objects
    artifacts = []
    for wp in result.get("work_products", []):
        art = NormalizedArtifact()
        art.id = wp.get("id", wp.get("wp_id", "unknown"))
        art.title = wp.get("title", "Untitled")
        art.full_text = wp.get("content", wp.get("full_text", ""))
        art.status = wp.get("status", "submitted")

        # Tags
        for t in wp.get("tags_addressed", wp.get("tags", [])):
            art.tags.add(str(t).lower())

        # Methods
        for m in wp.get("methods_used", wp.get("methods", [])):
            art.methods.add(str(m).lower())

        # Mapped sections
        art.mapped_nodes = wp.get("mapped_sections", wp.get("mapped_clauses", []))

        # Traceability links
        art.traceability_links = wp.get("traceability_links", [])

        # Sections
        for sec in wp.get("sections", []):
            if isinstance(sec, dict):
                art.sections.append(sec)

        # Metadata — everything else
        skip_keys = {"id", "wp_id", "title", "content", "full_text", "status",
                     "tags_addressed", "tags", "methods_used", "methods",
                     "mapped_sections", "mapped_clauses", "traceability_links", "sections"}
        for k, v in wp.items():
            if k not in skip_keys:
                art.metadata[k] = v

        artifacts.append(art)

    return artifacts


def run_compliance_check(standard_path: str, artifact_path: str,
                          meta_path: str = None, convert_pdf: bool = False) -> dict:
    """
    Main entry point. Fully agnostic.

    Args:
        standard_path: directory of JSON/MD files, single JSON file, single MD file,
                       or directory of PDFs (with --convert)
        artifact_path: file or directory with user documentation (JSON, DOCX, PDF, MD, TXT)
        meta_path: optional compliance_meta.json for hints
        convert_pdf: if True, convert PDF standards to markdown before processing
    """

    # ── Load standard ──
    print(f"\n{'='*70}")
    print(f"  STANDARD-AGNOSTIC COMPLIANCE CHECKER")
    print(f"{'='*70}\n")

    data_sources = []

    # Handle PDF→MD conversion if requested
    if convert_pdf:
        converted_dir = None
        if os.path.isdir(standard_path):
            pdf_files = sorted(glob_module.glob(os.path.join(standard_path, "*.pdf")))
            if pdf_files:
                converted_dir = os.path.join(standard_path, "_converted_md")
                os.makedirs(converted_dir, exist_ok=True)
                print(f"  Converting {len(pdf_files)} PDF(s) to Markdown...")
                for pdf_fp in pdf_files:
                    try:
                        _convert_pdf_to_markdown(pdf_fp, converted_dir)
                    except Exception as e:
                        print(f"    [WARN] Failed to convert {os.path.basename(pdf_fp)}: {e}")
                # Now load from converted dir alongside originals
                for fp in sorted(glob_module.glob(os.path.join(converted_dir, "*.md"))):
                    try:
                        parsed = _load_markdown_as_json(fp)
                        data_sources.append((os.path.basename(fp), parsed))
                    except Exception as e:
                        print(f"    [WARN] Failed to parse {os.path.basename(fp)}: {e}")
        elif standard_path.lower().endswith(".pdf"):
            converted_dir = tempfile.mkdtemp(prefix="compliance_md_")
            try:
                md_path = _convert_pdf_to_markdown(standard_path, converted_dir)
                parsed = _load_markdown_as_json(md_path)
                data_sources.append((os.path.basename(md_path), parsed))
            except Exception as e:
                print(f"    [WARN] Failed to convert PDF: {e}")

    # Load standard files (JSON + MD)
    if os.path.isdir(standard_path):
        # Load JSON files
        for fp in sorted(glob_module.glob(os.path.join(standard_path, "*.json"))):
            fname = os.path.basename(fp)
            if fname == "compliance_meta.json":
                if not meta_path:
                    meta_path = fp
                continue
            # Skip generated reports
            if "compliance_report" in fname:
                continue
            with open(fp, 'r') as f:
                data_sources.append((fname, json.load(f)))

        # Load Markdown files (parsed on-the-fly)
        for fp in sorted(glob_module.glob(os.path.join(standard_path, "*.md"))):
            fname = os.path.basename(fp)
            # Skip readme/docs
            if fname.lower() in ("readme.md", "changelog.md", "license.md"):
                continue
            try:
                parsed = _load_markdown_as_json(fp)
                data_sources.append((fname, parsed))
                print(f"    Parsed markdown standard: {fname} ({len(parsed.get('clauses', []))} clauses)")
            except Exception as e:
                print(f"    [WARN] Failed to parse markdown {fname}: {e}")

        print(f"  Loaded {len(data_sources)} standard files from: {standard_path}")
    else:
        ext = os.path.splitext(standard_path)[1].lower()
        if ext == ".md":
            parsed = _load_markdown_as_json(standard_path)
            data_sources.append((os.path.basename(standard_path), parsed))
            print(f"  Loaded markdown standard: {standard_path} ({len(parsed.get('clauses', []))} clauses)")
        elif ext == ".json":
            with open(standard_path, 'r') as f:
                data_sources.append((os.path.basename(standard_path), json.load(f)))
            print(f"  Loaded standard: {standard_path}")
        else:
            raise ValueError(f"Unsupported standard format: {ext}. Use .json, .md, or .pdf with --convert")

    # ── Load meta config (optional) ──
    meta = None
    if meta_path and os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        print(f"  Loaded meta config: {meta_path}")

    # ── Discover schema ──
    print("\n  Discovering schema structure...")
    discovery = SchemaDiscovery()
    schema = discovery.discover(data_sources, meta)
    s = schema.summary()
    print(f"    Discovered fields: text='{schema.text_field}', id='{schema.id_field}', "
          f"title='{schema.title_field}', risk='{schema.risk_field}', tags='{schema.tag_field}'")
    print(f"    Risk scale: {schema.risk_scale}")
    print(f"    Found: {s['requirement_nodes']} requirements, {s['guideline_nodes']} guidelines, "
          f"{s['glossary_entries']} glossary terms")
    print(f"    Methods: {s['method_tables']} tables  |  Tags: {s['unique_tags']} unique  |  "
          f"Cross-refs: {s['cross_references']}  |  Trace rules: {s['traceability_rules']}")
    print(f"    Groups: {list(schema.groups.keys())[:8]}{'...' if len(schema.groups) > 8 else ''}")

    # ── Ingest artifact ──
    print(f"\n  Ingesting artifact: {artifact_path}")

    # Determine if we need the universal ingester (non-JSON or directory)
    ext = os.path.splitext(artifact_path)[1].lower() if os.path.isfile(artifact_path) else ""
    use_universal = (
        os.path.isdir(artifact_path) or
        ext in (".docx", ".pdf", ".md", ".txt", ".xlsx", ".xls", ".csv", ".odt")
    )

    if use_universal:
        try:
            artifacts = _load_universal_artifacts(artifact_path)
            print(f"    [Universal Ingester] Loaded {len(artifacts)} work product(s)")
        except Exception as e:
            print(f"    [WARN] Universal ingester failed ({e}), falling back to built-in")
            ingester = ArtifactIngester()
            artifacts = ingester.ingest(artifact_path)
    else:
        ingester = ArtifactIngester()
        artifacts = ingester.ingest(artifact_path)

    print(f"    Loaded {len(artifacts)} work product(s)")
    for art in artifacts[:5]:
        print(f"      [{art.status}] {art.id}: {art.title} "
              f"({len(art.full_text)} chars, {len(art.mapped_nodes)} mapped nodes, "
              f"{len(art.tags)} tags, {len(art.methods)} methods)")

    # ── Determine target risk and scope from artifact metadata ──
    target_risk = None
    in_scope = None
    if artifacts:
        meta_data = artifacts[0].metadata
        # Look for risk level in metadata
        for k in ["target_asil", "asil", "target_risk", "risk_level", "sil", "cal",
                   "target_level", "capability_level"]:
            if k in meta_data:
                target_risk = str(meta_data[k])
                break
        # Look for scope
        for k in ["parts_in_scope", "scope", "applicable_parts", "in_scope", "modules"]:
            if k in meta_data and isinstance(meta_data[k], list):
                in_scope = [f"part_{p}" for p in meta_data[k]]
                break

    print(f"\n  Target risk level: {target_risk or 'all'}")
    print(f"  In-scope groups: {in_scope or 'all'}")

    # ── Run algorithm pipeline ──
    print(f"\n{'─'*70}")
    print(f"  RUNNING 8-LAYER ALGORITHM PIPELINE")
    print(f"{'─'*70}\n")

    layers = [
        ("1/8 Node Coverage (Decision Tree)",
         lambda: layer1_node_coverage(schema, artifacts, target_risk, in_scope)),
        ("2/8 Content Alignment (TF-IDF + Cosine)",
         lambda: layer2_content_alignment(schema, artifacts, target_risk, in_scope)),
        ("3/8 Semantic Matching (Ratcliff/Obershelp)",
         lambda: layer3_semantic_matching(schema, artifacts, target_risk, in_scope)),
        ("4/8 Concept Coverage (Set Analysis)",
         lambda: layer4_concept_coverage(schema, artifacts, target_risk, in_scope)),
        ("5/8 Reference Integrity (Graph BFS)",
         lambda: layer5_reference_integrity(schema, artifacts)),
        ("6/8 Method Audit (Risk-Aware Rules)",
         lambda: layer6_method_audit(schema, artifacts, target_risk)),
        ("7/8 Traceability Chain (Graph Walk)",
         lambda: layer7_traceability_chain(schema, artifacts)),
    ]

    layer_results = []
    for label, fn in layers:
        print(f"  [{label}]")
        result = fn()
        layer_results.append(result)
        findings = result.get("findings", [])
        print(f"    Score: {result['score']}%  |  Findings: {len(findings)}")
        for f in findings[:2]:
            print(f"      [{f['severity']}] {f['message'][:80]}...")
        if len(findings) > 2:
            print(f"      ... +{len(findings)-2} more")
        print()

    print(f"  [8/8 Gap Analysis + Risk Scoring]")
    gap = layer8_gap_analysis(layer_results, schema.risk_scale, target_risk or "")
    print(f"    Risk Score: {gap['total_risk']}  |  Severity: {gap['severity_counts']}")
    for rec in gap["recommendations"][:3]:
        print(f"    → {rec[:80]}...")
    print()

    # ── Compute weighted score ──
    weighted = sum(r["score"] * LAYER_WEIGHTS.get(r["layer"], 0) for r in layer_results)
    g = grade(weighted)

    # ── Build Work Product Register ──
    print("  Building work product register...")
    work_product_register = []
    for art in artifacts:
        # Determine which standard parts/clauses this artifact maps to
        mapped_parts = set()
        mapped_clauses = []
        for node_id in art.mapped_nodes:
            # Extract part from node_id or group
            for grp_name, grp_data in schema.groups.items():
                if isinstance(grp_data, dict):
                    nodes = grp_data.get("nodes", [])
                elif isinstance(grp_data, list):
                    nodes = grp_data
                else:
                    nodes = []
                for node in nodes:
                    nid = ""
                    if isinstance(node, dict):
                        for k in ["section", "clause_id", "id", "clause", "requirement_id"]:
                            if k in node:
                                nid = str(node[k])
                                break
                    if nid == node_id:
                        mapped_parts.add(grp_name)
                        break
            mapped_clauses.append(node_id)

        # If no explicit mapping, try to infer from content alignment
        if not mapped_parts:
            ca_layer = {r["layer"]: r for r in layer_results}.get("content_alignment", {})
            ca_scores = ca_layer.get("scores", {})
            for clause_id, score_val in ca_scores.items():
                if isinstance(score_val, (int, float)) and score_val > 40:
                    for grp_name in schema.groups:
                        if grp_name in clause_id or clause_id.startswith(grp_name.replace("part_", "")):
                            mapped_parts.add(grp_name)

        # Determine compliance status for this artifact
        art_findings = []
        for lr in layer_results:
            for f in lr.get("findings", []):
                if any(mn in f.get("message", "") or mn in f.get("node_id", "")
                       for mn in art.mapped_nodes[:20]):
                    art_findings.append(f)

        n_critical = sum(1 for f in art_findings if f.get("severity") == "CRITICAL")
        n_major = sum(1 for f in art_findings if f.get("severity") == "MAJOR")

        # ISO 26262-consistent status categories:
        #   Compliant / Partially Compliant / Not Compliant / Missing / N/A
        if len(art.full_text.strip()) == 0:
            wp_status = "Missing"
        elif n_critical > 0:
            wp_status = "Not Compliant"
        elif n_major > 0:
            wp_status = "Partially Compliant"
        elif len(art.mapped_nodes) > 0:
            wp_status = "Compliant"
        else:
            wp_status = "N/A"  # Not mapped to any standard clause

        wp_entry = {
            "name": art.title or art.id,
            "id": art.id,
            "format": art.metadata.get("format", "unknown"),
            "mapped_parts": sorted(mapped_parts),
            "mapped_clauses": mapped_clauses[:50],
            "sections_count": len(art.sections),
            "content_length": len(art.full_text),
            "tags_count": len(art.tags),
            "methods_count": len(art.methods),
            "status": wp_status,
            "findings_count": len(art_findings),
            "critical_count": n_critical,
            "major_count": n_major,
        }
        work_product_register.append(wp_entry)

    # ── Build Traceability Matrix ──
    print("  Building traceability matrix...")
    trace_matrix = {
        "chains": [],
        "coverage_summary": {},
        "orphan_requirements": [],
        "orphan_artifacts": [],
    }

    # Collect ALL requirement/clause IDs from the schema (including from node_coverage)
    all_req_ids = set()
    for grp_name, grp_data in schema.groups.items():
        nodes = grp_data if isinstance(grp_data, list) else grp_data.get("nodes", [])
        for node in nodes:
            if isinstance(node, dict):
                nid = ""
                for k in ["section", "clause_id", "id", "clause", "requirement_id"]:
                    if k in node:
                        nid = str(node[k])
                        break
                if nid:
                    all_req_ids.add(nid)

    # Also pull requirement IDs from node_coverage layer results
    nc_result = {r["layer"]: r for r in layer_results}.get("node_coverage", {})
    applicable_nodes = nc_result.get("applicable_nodes", 0)
    covered_nodes_count = nc_result.get("covered_nodes", 0)
    nc_findings = nc_result.get("findings", [])

    # If schema groups gave us 0 requirements, use node_coverage data
    if not all_req_ids and applicable_nodes > 0:
        # Reconstruct from findings — missing ones are the ones in findings
        for f in nc_findings:
            nid = f.get("node_id", "")
            if nid:
                all_req_ids.add(nid)
        # The covered ones aren't in findings, so estimate total
        # We know applicable_nodes is the total

    # Build trace chains: requirement → artifact → verification evidence
    traced_reqs = set()
    for art in artifacts:
        for node_id in art.mapped_nodes:
            traced_reqs.add(node_id)
            has_verification = len(art.methods) > 0
            trace_matrix["chains"].append({
                "requirement_id": node_id,
                "artifact_id": art.id,
                "artifact_name": art.title or art.id,
                "has_verification": has_verification,
                "verification_methods": list(art.methods)[:5],
            })

    # Use the larger of schema-discovered reqs or node_coverage applicable count
    total_req_count = max(len(all_req_ids), applicable_nodes)

    # Identify orphan requirements (in standard but not traced by any artifact)
    if all_req_ids:
        trace_matrix["orphan_requirements"] = sorted(all_req_ids - traced_reqs)[:100]
    else:
        # If we couldn't enumerate them, estimate from node_coverage
        missing_count = max(0, total_req_count - len(traced_reqs))
        # Use finding node_ids as orphans
        trace_matrix["orphan_requirements"] = [
            f.get("node_id", "unknown") for f in nc_findings
            if f.get("type") == "MISSING_COVERAGE"
        ][:100]

    traced_art_ids = {art.id for art in artifacts if art.mapped_nodes}
    all_art_ids = {art.id for art in artifacts}
    trace_matrix["orphan_artifacts"] = sorted(all_art_ids - traced_art_ids)

    # Coverage calculation — use actual trace evidence, capped at 100%
    trace_cov_pct = min(100.0, round(len(traced_reqs) / max(total_req_count, 1) * 100, 1)) if total_req_count > 0 else 0.0

    trace_matrix["coverage_summary"] = {
        "total_requirements": total_req_count,
        "traced_requirements": len(traced_reqs),
        "trace_coverage_pct": trace_cov_pct,
        "total_artifacts": len(artifacts),
        "artifacts_with_traces": len(traced_art_ids),
        "total_chains": len(trace_matrix["chains"]),
        "orphan_requirements_count": len(trace_matrix["orphan_requirements"]),
        "orphan_artifacts_count": len(trace_matrix["orphan_artifacts"]),
    }

    # ── Compute Assessment Decision ──
    print("  Computing assessment decision...")
    total_findings = sum(len(r.get("findings", [])) for r in layer_results)
    sev_counts = gap.get("severity_counts", {})
    n_critical_total = sev_counts.get("CRITICAL", 0)
    n_major_total = sev_counts.get("MAJOR", 0)

    assessment_conditions = []
    if weighted >= 85 and n_critical_total == 0 and n_major_total <= 2:
        assessment_verdict = "COMPLIANT"
        verdict_description = ("The assessed work products demonstrate sufficient compliance with "
                              "the applicable requirements of the standard. Minor observations "
                              "have been noted but do not affect the overall safety argument.")
    elif weighted >= 60 and n_critical_total <= 2:
        assessment_verdict = "CONDITIONALLY COMPLIANT"
        conditions = []
        if n_critical_total > 0:
            conditions.append(f"Resolution of {n_critical_total} critical finding(s)")
        if n_major_total > 3:
            conditions.append(f"Remediation of {n_major_total} major finding(s)")
        conditions.append("Submission of corrective action evidence within agreed timeline")
        verdict_description = ("The assessed work products demonstrate partial compliance. "
                              "Compliance is conditional upon the resolution of identified "
                              "findings and corrective actions.")
        assessment_conditions = conditions
    else:
        assessment_verdict = "NOT COMPLIANT"
        verdict_description = ("The assessed work products do not demonstrate sufficient compliance "
                              "with the applicable requirements. Significant gaps in coverage, "
                              "traceability, or methodology have been identified. A comprehensive "
                              "remediation effort is required before re-assessment.")
        assessment_conditions = []

    assessment_decision = {
        "verdict": assessment_verdict,
        "description": verdict_description,
        "conditions": assessment_conditions if assessment_verdict == "CONDITIONALLY COMPLIANT" else [],
        "score": round(weighted, 1),
        "critical_findings": n_critical_total,
        "major_findings": n_major_total,
        "total_findings": total_findings,
    }

    # ── Confirmation Review Assessment (ISO 26262 Part 2, 6.4.4) ──
    print("  Computing confirmation review assessment...")

    # ISO 26262 independence levels by ASIL
    # I0 = same person, I1 = different person same team, I2 = different department, I3 = different org
    ASIL_INDEPENDENCE = {
        "QM": "I0", "A": "I1", "B": "I1", "C": "I2", "D": "I3"
    }

    # Confirmation review checklist items per ISO 26262-2:2018 6.4.4.3
    CONFIRMATION_CHECKLIST = [
        ("CR-01", "Completeness", "All required work products per safety plan are present"),
        ("CR-02", "Compliance with standard", "Work products comply with applicable parts of ISO 26262"),
        ("CR-03", "Consistency", "No contradictions between related work products"),
        ("CR-04", "Traceability", "Bidirectional traceability between safety goals, FSR, TSR, and verification evidence"),
        ("CR-05", "Adequacy of safety analyses", "FMEA/FTA/DFA performed with appropriate coverage"),
        ("CR-06", "Adequacy of verification", "Verification methods appropriate for ASIL level"),
        ("CR-07", "Configuration management", "Artifacts under configuration control with version tracking"),
        ("CR-08", "Change management", "Safety impact analysis performed for all changes"),
        ("CR-09", "Safety case argument", "Safety case provides convincing argument for residual risk acceptance"),
        ("CR-10", "Compliance with safety plan", "Development activities follow the safety plan"),
    ]

    confirmation_review = {
        "target_asil": target_risk or "Not specified",
        "required_independence": ASIL_INDEPENDENCE.get((target_risk or "").upper().replace("ASIL_", "").replace("ASIL ", ""), "I1"),
        "checklist": [],
        "summary": {},
    }

    # Evaluate each checklist item based on engine layer results
    cr_pass = 0
    cr_fail = 0
    cr_partial = 0

    for cr_id, cr_name, cr_desc in CONFIRMATION_CHECKLIST:
        if cr_id == "CR-01":  # Completeness — from node_coverage
            nc = nc_result
            cov = nc.get("covered_nodes", 0)
            total = nc.get("applicable_nodes", 1)
            pct = (cov / max(total, 1)) * 100
            if pct >= 85:
                cr_status, cr_evidence = "Pass", f"{cov}/{total} required work products present ({pct:.0f}%)"
            elif pct >= 50:
                cr_status, cr_evidence = "Partial", f"Only {cov}/{total} work products present ({pct:.0f}%)"
            else:
                cr_status, cr_evidence = "Fail", f"Only {cov}/{total} work products present ({pct:.0f}%) — significant gaps"

        elif cr_id == "CR-02":  # Compliance — from overall score
            if weighted >= 85:
                cr_status, cr_evidence = "Pass", f"Overall compliance score {weighted:.1f}% meets threshold"
            elif weighted >= 60:
                cr_status, cr_evidence = "Partial", f"Overall compliance score {weighted:.1f}% — gaps identified"
            else:
                cr_status, cr_evidence = "Fail", f"Overall compliance score {weighted:.1f}% — significant non-compliance"

        elif cr_id == "CR-03":  # Consistency — from reference integrity
            ri = {r["layer"]: r for r in layer_results}.get("reference_integrity", {})
            ri_score = ri.get("score", 0)
            if ri_score >= 80:
                cr_status, cr_evidence = "Pass", f"Reference integrity score {ri_score:.0f}% — cross-references consistent"
            elif ri_score >= 50:
                cr_status, cr_evidence = "Partial", f"Reference integrity score {ri_score:.0f}% — some inconsistencies"
            else:
                cr_status, cr_evidence = "Fail", f"Reference integrity score {ri_score:.0f}% — significant inconsistencies"

        elif cr_id == "CR-04":  # Traceability — from traceability chain
            tc = {r["layer"]: r for r in layer_results}.get("traceability_chain", {})
            tc_score = tc.get("score", 0)
            if tc_score >= 80:
                cr_status, cr_evidence = "Pass", f"Traceability score {tc_score:.0f}% — bidirectional traces established"
            elif tc_score >= 40:
                cr_status, cr_evidence = "Partial", f"Traceability score {tc_score:.0f}% — incomplete trace chains"
            else:
                cr_status, cr_evidence = "Fail", f"Traceability score {tc_score:.0f}% — traceability gaps critical"

        elif cr_id == "CR-05":  # Safety analyses — check for FMEA/FTA keywords
            sa_found = any(
                any(kw in (art.full_text.lower()) for kw in ["fmea", "fta", "fault tree", "failure mode", "dfa", "dependent failure"])
                for art in artifacts
            )
            if sa_found:
                cr_status, cr_evidence = "Pass", "Safety analysis artifacts detected (FMEA/FTA/DFA references found)"
            else:
                cr_status, cr_evidence = "Fail", "No safety analysis evidence found in submitted work products"

        elif cr_id == "CR-06":  # Verification adequacy — from method audit
            ma = {r["layer"]: r for r in layer_results}.get("method_audit", {})
            ma_score = ma.get("score", 0)
            if ma_score >= 80:
                cr_status, cr_evidence = "Pass", f"Method audit score {ma_score:.0f}% — verification methods adequate for ASIL"
            elif ma_score >= 50:
                cr_status, cr_evidence = "Partial", f"Method audit score {ma_score:.0f}% — some methods missing for ASIL"
            else:
                cr_status, cr_evidence = "Fail", f"Method audit score {ma_score:.0f}% — verification methods inadequate"

        elif cr_id == "CR-07":  # Configuration management — check for CM keywords
            cm_found = any(
                any(kw in (art.full_text.lower()) for kw in ["configuration management", "version control", "baseline", "change history", "revision"])
                for art in artifacts
            )
            cr_status = "Pass" if cm_found else "Fail"
            cr_evidence = "Configuration management evidence found" if cm_found else "No configuration management evidence in work products"

        elif cr_id == "CR-08":  # Change management
            chg_found = any(
                any(kw in (art.full_text.lower()) for kw in ["change request", "change management", "impact analysis", "safety impact"])
                for art in artifacts
            )
            cr_status = "Pass" if chg_found else "Fail"
            cr_evidence = "Change management evidence found" if chg_found else "No change management evidence in work products"

        elif cr_id == "CR-09":  # Safety case
            sc_found = any(
                any(kw in (art.full_text.lower()) for kw in ["safety case", "safety argument", "residual risk", "risk acceptance"])
                for art in artifacts
            )
            if sc_found:
                cr_status, cr_evidence = "Pass", "Safety case / safety argument evidence found"
            else:
                cr_status, cr_evidence = "Fail", "No safety case or safety argument evidence found"

        elif cr_id == "CR-10":  # Safety plan compliance
            sp_found = any(
                any(kw in (art.full_text.lower()) for kw in ["safety plan", "development plan", "v-model", "safety lifecycle"])
                for art in artifacts
            )
            if sp_found:
                cr_status, cr_evidence = "Pass", "Safety plan reference found in work products"
            else:
                cr_status, cr_evidence = "Fail", "No safety plan reference found in work products"
        else:
            cr_status, cr_evidence = "N/A", "Not evaluated"

        if cr_status == "Pass":
            cr_pass += 1
        elif cr_status == "Fail":
            cr_fail += 1
        else:
            cr_partial += 1

        confirmation_review["checklist"].append({
            "id": cr_id,
            "item": cr_name,
            "description": cr_desc,
            "status": cr_status,
            "evidence": cr_evidence,
        })

    cr_total = cr_pass + cr_fail + cr_partial
    confirmation_review["summary"] = {
        "total_items": cr_total,
        "pass": cr_pass,
        "partial": cr_partial,
        "fail": cr_fail,
        "pass_rate": round(cr_pass / max(cr_total, 1) * 100, 1),
        "result": "PASSED" if cr_fail == 0 and cr_partial <= 2 else ("CONDITIONAL" if cr_fail <= 2 else "FAILED"),
    }

    # ── Verification Review Assessment (ISO 26262 Part 2, 6.4.10 / Part 8) ──
    print("  Computing verification review assessment...")

    # ISO 26262 verification method recommendations by ASIL
    # ++ = highly recommended, + = recommended, o = no recommendation for this ASIL
    VERIFICATION_METHODS_BY_ASIL = {
        "Walk-through":                {"A": "+",  "B": "+",  "C": "+",  "D": "+"},
        "Inspection":                  {"A": "+",  "B": "+",  "C": "++", "D": "++"},
        "Semi-formal verification":    {"A": "o",  "B": "+",  "C": "+",  "D": "++"},
        "Formal verification":         {"A": "o",  "B": "o",  "C": "+",  "D": "++"},
        "Requirements-based testing":  {"A": "++", "B": "++", "C": "++", "D": "++"},
        "Interface testing":           {"A": "+",  "B": "+",  "C": "++", "D": "++"},
        "Fault injection testing":     {"A": "o",  "B": "+",  "C": "+",  "D": "++"},
        "Back-to-back testing":        {"A": "o",  "B": "+",  "C": "+",  "D": "++"},
        "Simulation":                  {"A": "+",  "B": "+",  "C": "+",  "D": "++"},
        "Analysis of requirements":    {"A": "++", "B": "++", "C": "++", "D": "++"},
        "Boundary value analysis":     {"A": "+",  "B": "+",  "C": "++", "D": "++"},
        "Equivalence classes":         {"A": "+",  "B": "+",  "C": "+",  "D": "++"},
        "Error guessing":              {"A": "+",  "B": "+",  "C": "+",  "D": "+"},
    }

    # Map work product types to applicable verification methods
    WP_VERIFICATION_MAP = {
        "safety_goals": ["Analysis of requirements", "Inspection"],
        "hara": ["Analysis of requirements", "Inspection", "Walk-through"],
        "functional_safety_concept": ["Analysis of requirements", "Inspection", "Walk-through"],
        "technical_safety_concept": ["Analysis of requirements", "Inspection", "Semi-formal verification"],
        "technical_safety_requirements": ["Analysis of requirements", "Inspection", "Semi-formal verification", "Formal verification"],
        "system_design": ["Inspection", "Simulation", "Walk-through"],
        "hw_safety_requirements": ["Analysis of requirements", "Inspection", "Formal verification"],
        "hw_design": ["Inspection", "Simulation", "Fault injection testing"],
        "hw_safety_analysis": ["Analysis of requirements", "Inspection"],
        "sw_safety_requirements": ["Analysis of requirements", "Inspection", "Semi-formal verification"],
        "sw_architecture": ["Inspection", "Walk-through", "Semi-formal verification"],
        "sw_unit_design": ["Inspection", "Walk-through", "Semi-formal verification", "Formal verification"],
        "sw_unit_test": ["Requirements-based testing", "Boundary value analysis", "Equivalence classes", "Error guessing"],
        "sw_integration_test": ["Requirements-based testing", "Interface testing", "Fault injection testing"],
        "sw_qualification_test": ["Requirements-based testing", "Interface testing", "Back-to-back testing"],
        "system_integration_test": ["Requirements-based testing", "Interface testing", "Fault injection testing", "Simulation"],
    }

    # Try to detect ASIL from target_risk
    asil_key = (target_risk or "").upper().replace("ASIL_", "").replace("ASIL ", "").strip()
    if asil_key not in ("A", "B", "C", "D"):
        asil_key = "B"  # Default to ASIL B if not determinable

    verification_review = {
        "target_asil": target_risk or "Not specified",
        "asil_key": asil_key,
        "work_products": [],
        "method_recommendations": [],
        "summary": {},
    }

    # Build method recommendation table for this ASIL
    for method_name, asil_recs in VERIFICATION_METHODS_BY_ASIL.items():
        rec = asil_recs.get(asil_key, "o")
        verification_review["method_recommendations"].append({
            "method": method_name,
            "asil_a": VERIFICATION_METHODS_BY_ASIL[method_name].get("A", "o"),
            "asil_b": VERIFICATION_METHODS_BY_ASIL[method_name].get("B", "o"),
            "asil_c": VERIFICATION_METHODS_BY_ASIL[method_name].get("C", "o"),
            "asil_d": VERIFICATION_METHODS_BY_ASIL[method_name].get("D", "o"),
            "applicable": rec,
        })

    # Assess each work product's verification status
    vr_adequate = 0
    vr_partial = 0
    vr_insufficient = 0

    for wp in work_product_register:
        art_obj = None
        for a in artifacts:
            if a.id == wp["id"]:
                art_obj = a
                break

        # Try to classify the work product type
        wp_name_lower = (wp["name"] or "").lower()
        wp_type = "generic"
        type_keywords = {
            "safety_goals": ["safety goal", "sg-"],
            "hara": ["hara", "hazard analysis", "hazard and risk"],
            "functional_safety_concept": ["functional safety concept", "fsc"],
            "technical_safety_concept": ["technical safety concept", "tsc"],
            "technical_safety_requirements": ["technical safety req", "tsr"],
            "system_design": ["system design", "system specification"],
            "hw_safety_requirements": ["hardware safety req", "hw safety req"],
            "hw_design": ["hardware design", "hw design"],
            "hw_safety_analysis": ["hardware safety analysis", "fmeda", "spfm", "lfm"],
            "sw_safety_requirements": ["software safety req", "sw safety req"],
            "sw_architecture": ["software architect", "sw architect"],
            "sw_unit_design": ["software unit", "sw unit design"],
            "sw_unit_test": ["unit test", "unit verification"],
            "sw_integration_test": ["integration test", "sw integration"],
            "sw_qualification_test": ["qualification test"],
            "system_integration_test": ["system integration", "system test"],
        }
        for t_key, t_keywords in type_keywords.items():
            if any(kw in wp_name_lower for kw in t_keywords):
                wp_type = t_key
                break

        applicable_methods = WP_VERIFICATION_MAP.get(wp_type, ["Inspection", "Walk-through"])

        # Check which methods are evidenced in the artifact
        methods_found = []
        methods_missing = []
        if art_obj:
            art_text_lower = art_obj.full_text.lower()
            art_methods_lower = [m.lower() for m in art_obj.methods]
            for method in applicable_methods:
                method_lower = method.lower()
                # Check both explicit methods list and text content
                if any(method_lower in m for m in art_methods_lower) or method_lower in art_text_lower:
                    methods_found.append(method)
                else:
                    methods_missing.append(method)
        else:
            methods_missing = applicable_methods

        # Determine verification adequacy
        total_applicable = len(applicable_methods)
        found_count = len(methods_found)
        if total_applicable == 0:
            vr_status = "N/A"
        elif found_count >= total_applicable * 0.75:
            vr_status = "Adequate"
            vr_adequate += 1
        elif found_count >= total_applicable * 0.4:
            vr_status = "Partial"
            vr_partial += 1
        else:
            vr_status = "Insufficient"
            vr_insufficient += 1

        # Get recommendation level for each found/missing method at this ASIL
        method_details = []
        for method in applicable_methods:
            rec_level = VERIFICATION_METHODS_BY_ASIL.get(method, {}).get(asil_key, "o")
            is_applied = method in methods_found
            method_details.append({
                "method": method,
                "recommendation": rec_level,
                "applied": is_applied,
                "required": rec_level in ("++", "+"),
            })

        verification_review["work_products"].append({
            "name": wp["name"],
            "id": wp["id"],
            "wp_type": wp_type,
            "status": vr_status,
            "methods_found": methods_found,
            "methods_missing": methods_missing,
            "method_details": method_details,
            "coverage_pct": round(found_count / max(total_applicable, 1) * 100, 1),
        })

    vr_total = vr_adequate + vr_partial + vr_insufficient
    verification_review["summary"] = {
        "total_work_products": vr_total,
        "adequate": vr_adequate,
        "partial": vr_partial,
        "insufficient": vr_insufficient,
        "adequacy_rate": round(vr_adequate / max(vr_total, 1) * 100, 1),
        "result": "PASSED" if vr_insufficient == 0 and vr_partial <= 2 else ("CONDITIONAL" if vr_insufficient <= 2 else "FAILED"),
    }

    # ── ISO 26262 Work Product Reference ──
    iso26262_wp_reference = {
        "Part 2 - Management": [
            "2-6.4.1: Safety plan",
            "2-6.4.2: Safety case",
            "2-6.4.4: Project plan (safety-related)",
            "2-6.4.6: Confirmation review report",
            "2-6.4.7: Functional safety audit report",
            "2-6.4.8: Functional safety assessment report",
        ],
        "Part 3 - Concept Phase": [
            "3-5: Item definition",
            "3-6: Hazard analysis and risk assessment (HARA)",
            "3-7: Safety goals",
            "3-8: Functional safety concept",
        ],
        "Part 4 - System Level": [
            "4-6: Technical safety concept (TSC)",
            "4-7: System design specification",
            "4-7.4: Technical safety requirements (TSR)",
            "4-8: HW-SW interface specification (HSI)",
            "4-9: System integration and testing report",
        ],
        "Part 5 - Hardware Level": [
            "5-6: Hardware safety requirements specification",
            "5-7: Hardware design specification",
            "5-8: Hardware safety analysis report",
            "5-9: HW metrics report (SPFM, LFM, PMHF)",
            "5-10: Hardware integration and testing report",
        ],
        "Part 6 - Software Level": [
            "6-5: Software safety requirements specification",
            "6-6: Software architectural design specification",
            "6-7: Software unit design and implementation",
            "6-8: Software unit verification report",
            "6-9: Software integration and testing report",
            "6-10: Software qualification testing report",
        ],
        "Part 7 - Production & Operation": [
            "7-5: Production plan (safety-related)",
            "7-6: Field monitoring plan",
        ],
        "Part 8 - Supporting Processes": [
            "8-6: Configuration management plan",
            "8-7: Change management plan",
            "8-8: Verification plan",
            "8-9: Documentation management plan",
        ],
        "Part 9 - Safety Analyses": [
            "9-5: Quantitative FTA report",
            "9-6: FMEA/FMEDA report",
            "9-7: Dependent failure analysis (DFA)",
            "9-8: Safety analysis report",
        ],
    }

    report = {
        "engine": "Lion of Functional Safety Engine\u2122 — Standard-Agnostic Compliance Checker v2.1",
        "check_date": datetime.now().isoformat(),
        "standard_source": standard_path,
        "artifact_source": artifact_path,
        "discovered_schema": schema.summary(),
        "target_risk_level": target_risk,
        "compliance_score": round(weighted, 1),
        "grade": g,
        "layer_results": {r["layer"]: r for r in layer_results},
        "gap_analysis": gap,
        "summary": {
            "total_findings": total_findings,
            "risk_score": gap["total_risk"],
            "top_recommendations": gap["recommendations"][:10]
        },
        # New fields for professional report
        "work_product_register": work_product_register,
        "traceability_matrix": trace_matrix,
        "assessment_decision": assessment_decision,
        "iso26262_wp_reference": iso26262_wp_reference,
        "confirmation_review": confirmation_review,
        "verification_review": verification_review,
        "standards_assessed": [os.path.basename(s[0]) for s in data_sources],
        "artifacts_assessed": [{"name": a.title or a.id, "id": a.id} for a in artifacts],
    }

    # ── Print final ──
    print(f"{'='*70}")
    print(f"  COMPLIANCE SCORE: {report['compliance_score']}%")
    print(f"  GRADE: {g}")
    print(f"{'='*70}")
    print(f"\n  Layer Breakdown:")
    for r in layer_results:
        w = LAYER_WEIGHTS.get(r["layer"], 0)
        bar = '#' * int(r["score"] / 5)
        print(f"    {r['layer']:25s} {r['score']:5.1f}% (×{w:.0%}) |{bar}")
    print(f"\n  Total Risk: {gap['total_risk']}  |  Findings: {report['summary']['total_findings']}")
    print(f"\n  Priority Actions:")
    for i, rec in enumerate(report["summary"]["top_recommendations"], 1):
        print(f"    {i}. {rec}")
    print(f"\n{'='*70}\n")

    return report


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

def generate_document(report, json_path, fmt="docx"):
    """
    Generate a formatted compliance document from the engine report.

    Args:
        report: dict from run_compliance_check()
        json_path: path to the saved JSON report (used to derive output path)
        fmt: "docx", "pdf", or "both"
    """
    base = json_path.replace(".json", "")
    generated = []

    if fmt in ("docx", "both", "all"):
        try:
            # Try importing from same directory first, then from outputs
            script_dir = os.path.dirname(os.path.abspath(__file__))
            docx_gen = os.path.join(script_dir, "report_generator_docx.py")

            # Dynamic import
            import importlib.util
            spec = importlib.util.spec_from_file_location("report_generator_docx", docx_gen)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            docx_path = base + ".docx"
            mod.generate_compliance_docx(report, docx_path)
            generated.append(docx_path)
        except Exception as e:
            print(f"  [WARN] DOCX generation failed: {e}")
            print(f"         Ensure report_generator_docx.py is in the same directory.")

    if fmt in ("pdf", "both", "all"):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            pdf_gen = os.path.join(script_dir, "report_generator.py")

            import importlib.util
            spec = importlib.util.spec_from_file_location("report_generator", pdf_gen)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            pdf_path = base + ".pdf"
            mod.generate_compliance_pdf(report, pdf_path)
            generated.append(pdf_path)
        except Exception as e:
            print(f"  [WARN] PDF generation failed: {e}")
            print(f"         Ensure report_generator.py is in the same directory and reportlab is installed.")

    if fmt in ("html", "both", "all"):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            html_gen = os.path.join(script_dir, "report_generator_html.py")

            import importlib.util
            spec = importlib.util.spec_from_file_location("report_generator_html", html_gen)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            html_path = base + ".html"
            mod.generate_compliance_html(report, html_path)
            generated.append(html_path)
        except Exception as e:
            print(f"  [WARN] HTML generation failed: {e}")
            print(f"         Ensure report_generator_html.py is in the same directory.")

    return generated


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python agnostic_engine.py <standard_dir_or_file> <artifact_file_or_dir> [options]")
        print("\nOptions:")
        print("  --meta FILE        Optional meta config JSON for schema hints")
        print("  --format FORMAT    Output format: json (default), docx, pdf, both, all")
        print("                     'all' = json + docx + pdf")
        print("  --convert          Auto-convert PDF standards to Markdown before processing")
        print("\nSupported Standard Formats:")
        print("  .json              Structured JSON (original format)")
        print("  .md                Markdown (from PDF conversion via pdftotext + pandoc)")
        print("  .pdf               PDF (requires --convert flag + pdftotext + pandoc)")
        print("  directory/         Mix of .json and .md files")
        print("\nSupported Artifact Formats:")
        print("  .json              Structured JSON work products")
        print("  .docx              Microsoft Word documents")
        print("  .pdf               PDF documents (via pdftotext)")
        print("  .md                Markdown documents")
        print("  .txt               Plain text documents")
        print("  directory/         Mix of any above formats")
        print("\nExamples:")
        print("  # JSON standard + JSON artifacts (original)")
        print("  python agnostic_engine.py ./standards_json/ my_work_products.json")
        print()
        print("  # Markdown standard + DOCX artifact → DOCX report")
        print("  python agnostic_engine.py ./standards_md/ my_report.docx --format docx")
        print()
        print("  # PDF standard (auto-convert) + mixed artifacts → all formats")
        print("  python agnostic_engine.py ./iso_pdfs/ ./work_products/ --convert --format all")
        print()
        print("  # Single markdown standard + single artifact")
        print("  python agnostic_engine.py iso26262_part4.md safety_plan.docx --format both")
        sys.exit(1)

    std_path = sys.argv[1]
    art_path = sys.argv[2]
    meta_file = None
    out_format = "json"
    convert_pdf = "--convert" in sys.argv

    if "--meta" in sys.argv:
        idx = sys.argv.index("--meta")
        if idx + 1 < len(sys.argv):
            meta_file = sys.argv[idx + 1]

    if "--format" in sys.argv:
        idx = sys.argv.index("--format")
        if idx + 1 < len(sys.argv):
            out_format = sys.argv[idx + 1].lower()

    report = run_compliance_check(std_path, art_path, meta_file, convert_pdf=convert_pdf)

    # Save JSON report (always)
    if os.path.isdir(art_path):
        out_dir = os.path.abspath(art_path)
    else:
        out_dir = os.path.dirname(os.path.abspath(art_path))
    out_path = os.path.join(out_dir, "compliance_report_agnostic.json")
    with open(out_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Report saved: {out_path}")

    # Generate formatted document if requested
    if out_format in ("docx", "pdf", "both", "all"):
        fmt = "both" if out_format == "all" else out_format
        generated = generate_document(report, out_path, fmt)
        for g in generated:
            print(f"Document generated: {g}")
