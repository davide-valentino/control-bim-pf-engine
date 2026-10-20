# Partner Rate Sheets (`/api/v1/presets`)

The engine ships with placeholder benchmark rates. A partner firm's real
localized rates enter the system as an **immutable, content-addressed rate
sheet**. Every feasibility job records exactly which version it used and copies
that version into its artifact directory, so a quote can always be reproduced.

---

## 1. Lifecycle

```
upload (JSON or multipart)
        │
        ▼
validate + normalize ──► warnings (non-blocking)
        │
        ▼
canonical JSON ──► sha256 ──► version (12 hex chars)
        │
        ▼
presetId = <slug>-<version>          e.g. bali-2026-10-e2e6a95f2408
        │
        ▼
artifacts/presets/<presetId>.json    (never overwritten)
artifacts/presets/registry.json      (createdAt, disabled, metadata)
        │
        ▼
feasibility job ──► materials.json ──► costs.json ──► rates-snapshot.json
```

* Re-uploading **identical** content is idempotent: the same `presetId` is
  returned with `created: false`.
* Changing any rate creates a **new** version and a new `presetId`. Old
  versions remain resolvable by `presetId`, so historical jobs never shift.
* Deleting is a **soft delete** (`disabled: true`). The file stays on disk for
  auditability but the version is no longer selected by name.

---

## 2. Sheet Schema

A sheet is either the single-sheet form below or the engine-native
`{"presets": {"<name>": {...}}, "metadata": {...}}` envelope. **Exactly one
preset per file** is allowed — one sheet, one source, one version.

```json
{
  "name": "Bali 2026-10",
  "metadata": {
    "currency": "IDR",
    "as_of": "2026-10-01",
    "source": "Aprianti Interiors - internal renovation rate sheet",
    "note": "Pilot benchmark; confirm before quoting a client"
  },
  "rooms": {
    "Living Room": {
      "aliases": ["Ruang Tamu", "Ruang Keluarga"],
      "walls":   {"material": "Cat interior (2 coats)", "cost_per_m2": 185000},
      "floors":  {"material": "Granit tile 60x60",       "cost_per_m2": 320000},
      "doors":   {"material": "Pintu kayu solid",        "cost_per_unit": 2500000},
      "windows": {"material": "Jendela aluminium",       "cost_per_m2": 950000}
    },
    "Bedroom": {
      "aliases": ["Kamar Tidur"],
      "walls":  {"material": "Cat interior (2 coats)", "cost_per_m2": 185000},
      "floors": {"material": "Laminate flooring",      "cost_per_m2": 280000},
      "doors":  {"material": "Pintu kayu solid",       "cost_per_unit": 2500000}
    }
  }
}
```

### Rules

| Field | Rule |
|---|---|
| `name` | 1–80 chars, unique across uploads. **Built-in names are reserved** (`Luxury Minimal`, `Rustic`, `Industrial`, case-insensitive). |
| `metadata.currency` | 3-letter ISO-4217 code, normalized to uppercase. |
| `metadata.as_of` | `YYYY-MM-DD`. |
| `metadata.source` | Who supplied the rates (3–200 chars). |
| `rooms` | 1–50 room types. Keys are the **canonical English room names**. |
| `rooms.*.aliases` | Optional localized names. Matching is case-insensitive and substring-based. |
| `walls` / `floors` / `windows` | Require `cost_per_m2` and must **not** define `cost_per_unit`. |
| `doors` | Requires `cost_per_unit` and must **not** define `cost_per_m2`. |
| Unknown keys | Rejected (`422`) — a typo cannot silently fall back to placeholder pricing. |

### Advisory warnings (never block an import)

* Currency outside the known pilot set.
* `as_of` in the future.
* `source` looks like test/placeholder data.
* No `Living Room` room (unmatched CAD rooms fall back to the first room).
* More than 30 room types.

### Room matching order

1. Exact canonical name.
2. Case-insensitive canonical name.
3. Compound names (`"Kitchen / Dining"`).
4. Localized aliases (`"Ruang Tamu"` → `Living Room`).
5. Substring/keyword match.
6. Fallback: `Living Room`, then the first room type.

---

## 3. API

All write endpoints accept the optional `PF_API_KEY` bearer token when
configured.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/presets` | Import a JSON body |
| `POST` | `/api/v1/presets/upload` | Import a `.json` file (multipart) |
| `GET` | `/api/v1/presets` | List built-in + uploaded sheets |
| `GET` | `/api/v1/presets/{presetId}` | Registry metadata + normalized document |
| `DELETE` | `/api/v1/presets/{presetId}` | Soft-disable an uploaded sheet |

### Import

```sh
curl -X POST http://localhost:8000/api/v1/presets \
  -H "Content-Type: application/json" \
  --data @tests/fixtures/idr_rate_sheet.json

# or multipart
curl -X POST http://localhost:8000/api/v1/presets/upload \
  -F "file=@bali-2026-10.json"
```

Response:

```json
{
  "presetId": "bali-2026-10-e2e6a95f2408",
  "name": "Bali 2026-10",
  "currency": "IDR",
  "asOf": "2026-10-01",
  "source": "Aprianti Interiors - internal renovation rate sheet",
  "origin": "upload",
  "version": "e2e6a95f2408",
  "roomTypes": ["Living Room", "Bedroom", "Kitchen"],
  "itemCount": 9,
  "warnings": [],
  "created": true,
  "disabled": false
}
```

### Apply to a feasibility job

Reference the exact version with `presetId`. If you use `preset` by name
instead, built-in sheets win first, then the newest enabled upload with that
name.

```sh
curl -X POST http://localhost:8000/api/v1/cad/feasibility/upload \
  -F "file=@RUMAH_RENOV.dxf" \
  -F "presetId=bali-2026-10-e2e6a95f2408" \
  -F "maxRoomRenders=0" \
  -F "dryRun=true"
```

The job record exposes `preset`, `presetId`, `presetVersion`, `currency`,
`asOf`, and `rateSource`. Completed artifacts include:

```
artifacts/feasibility/<runId>/
  materials.json        # metadata contains the preset identity
  costs.json            # { currency, as_of, rate_source, preset: {id,name,version,origin} }
  rates-snapshot.json   # exact sheet used for this job
  report.json           # summary.preset mirrors costs.preset
```

`costs.json` example:

```json
{
  "currency": "IDR",
  "as_of": "2026-10-01",
  "rate_source": "Aprianti Interiors - internal renovation rate sheet",
  "preset": {
    "id": "bali-2026-10-e2e6a95f2408",
    "name": "Bali 2026-10",
    "version": "e2e6a95f2408",
    "origin": "upload"
  },
  "total_cost": 18890000.0
}
```

---

## 4. Storage and Configuration

```
artifacts/presets/
  registry.json
  bali-2026-10-e2e6a95f2408.json
```

* The directory is inside the mounted `artifacts/` volume, so uploads survive
  container restarts.
* `MAX_PRESET_UPLOAD_BYTES` (default `2097152` = 2 MB) caps JSON and multipart
  imports.
* Files are written atomically (`tmp` + `os.replace`) and are never mutated.

---

## 5. Pilot Checklist

1. Receive Aprianti's sheet with `currency`, `as_of`, and `source` filled in.
2. Import it (`POST /api/v1/presets`) and review any warnings.
3. Run `RUMAH_RENOV.dxf` with the returned `presetId`.
4. Spot-check 3–5 line items against the partner's own estimate for the same
   project.
5. Only then show a client-facing number, and cite the preset version.

**Open modeling limits** (unchanged by rate sheets): shared walls are counted
per adjoining room; openings on a single `DOOR___WINDOW` layer are priced as
doors; windows require layer separation or a future explicit opening-type
field.
