# DXF to BIM & BOM Pipeline Architecture

This document describes the modular architecture of the **CAD Tests (DXF to BIM & BOM)** pipeline.

---

## 🗂️ Directory Structure

```
cad-tests/
│
├── pyproject.toml              # Dependencies & pytest configuration
├── poetry.lock
│
├── src/                        # Core Source Modules
│   ├── __init__.py
│   ├── geometry.py             # Math & polygon utilities (area, centroid, containment)
│   ├── breakdown.py            # Per-room breakdown generation logic
│   ├── summary.py              # Overall summary aggregation
│   ├── visualization.py        # 2D SVG overlay generator
│   ├── report_generator.py     # Main report orchestrator
│   └── pipeline/               # Staged DXF -> BIM pipeline
│       ├── __init__.py
│       ├── parser.py           # DXF entity extraction (walls, doors, text/labels)
│       ├── semantics.py        # Wall stitching & room classification
│       ├── materials.py        # Material catalog assignment
│       ├── costing.py          # BOM estimation & pricing engine
│       └── export.py           # Export utilities (CSV, IFC, etc.)
│
├── tests/                      # Test Suite (Unit & Integration)
│   ├── __init__.py
│   ├── test_geometry.py        # Unit tests for geometry utilities
│   ├── test_breakdown.py       # Unit tests for breakdown generation
│   ├── test_summary.py         # Unit tests for summary aggregation
│   ├── test_visualization.py   # Unit tests for SVG generation
│   ├── test_export.py          # Unit tests for CSV/data exports
│   ├── test_parse.py           # DXF parsing tests
│   ├── test_semantic.py        # Semantic classification & spatial label tests
│   ├── test_materials.py       # Material assignment tests
│   ├── test_costs.py           # Costing tests
│   ├── test_integration.py     # End-to-end integration tests
│   ├── test_report.py          # Consolidated report structure tests
│   ├── test_report_breakdown.py
│   ├── test_report_room_names.py
│   ├── test_report_rooms.py
│   └── test_report_summary.py
│
├── docs/
│   └── pipeline.md             # This document
│
├── .output/                    # Generated pipeline artifacts (.gitignore)
│   ├── raw_geometry.json
│   ├── semantic.json
│   ├── materials.json
│   ├── costs.json
│   ├── report.json
│   └── visualization.svg
│
└── simple_room.dxf             # Sample input CAD drawing
```

---

## 🔄 Data Flow

```
simple_room.dxf
      │
      ▼
1. Parser (src/pipeline/parser.py)
      │ ──> .output/raw_geometry.json (walls, doors, labels)
      ▼
2. Semantics (src/pipeline/semantics.py)
      │ ──> .output/semantic.json (closed boundaries, room names, doors)
      ▼
3. Materials (src/pipeline/materials.py)
      │ ──> .output/materials.json (assigned wall & door catalog items)
      ▼
4. Costing (src/pipeline/costing.py)
      │ ──> .output/costs.json (calculated areas, unit costs, totals)
      ▼
5. Report Orchestrator (src/report_generator.py)
      │ ──> .output/report.json (consolidated breakdown & summary)
      ▼
6. Visualization (src/visualization.py)
      │ ──> .output/visualization.svg (2D floorplan with dimensions & labels)
```

---

## 🧪 Testing Strategy

Run all unit and integration tests with:

```sh
poetry run pytest -v
```

The test suite covers:
- **Unit level**: Polygon math (`polygon_area`, `polygon_centroid`, `point_in_polygon`), label normalization, room breakdown computation, summary generation, SVG rendering, and export serialization.
- **Stage level**: Verification of output schemas for parser, semantics, materials, costs, and report.
- **Integration level**: Full end-to-end execution of the CLI pipeline.
