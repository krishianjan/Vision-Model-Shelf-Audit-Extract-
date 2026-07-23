# Vision Model Shelf Audit Extract

A production-grade system for automated retail shelf auditing using multi-model vision extraction with hallucination control.

## What It Does

- **Captures** shelf images from mobile devices (Expo React Native)
- **Analyzes** image quality (blur, lighting, framing) via OpenCV
- **Gatekeeps** non-alcohol content via YOLO object detection + CLIP semantic verification
- **Extracts** product information using a 3-tier brand recognition system (text → visual → unknown)
- **Validates** extractions against a 154-SKU reference catalog using 3-tier RAG matching (exact → fuzzy → embedding)
- **Calibrates** confidence scores via deterministic hard rules + LLM judge notes
- **Persists** verified data to Supabase (Postgres 15+ with pgvector + pg_trgm)
- **Displays** real-time insights in mobile and web dashboards

## Architecture

```
Mobile App (Expo) → API (FastAPI) → LangGraph Pipeline
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
              Quality Gate            Guardrail              VLM Extract
              (OpenCV)              (YOLO + CLIP)        (Qwen2.5-VL-72B)
                    │                      │                      │
                    └──────────┬───────────┘                      │
                               │                                  │
                         RAG Grounding                    Judge Calibration
                         (3-tier match)                 (Hard Rules + DeepSeek)
                               │                                  │
                               └──────────┬───────────────────────┘
                                          │
                                    Persist to DB
                                    (Supabase/Postgres)
```

## Tech Stack

- **Backend:** Python FastAPI + LangGraph
- **VLM:** Qwen2.5-VL-72B (OpenRouter) → Qwen3-32B fallback (Groq)
- **Guardrail:** YOLOv11n (Ultralytics) + CLIP ViT-Base-Patch32 (OpenAI)
- **Judge:** DeepSeek v3.2 (NVIDIA NIM) — notes only, hard rules are deterministic
- **RAG:** pg_trgm fuzzy + rapidfuzz + BGE-small-en embeddings (pgvector)
- **Mobile:** Expo React Native (TypeScript)
- **Web:** React + Vite (TypeScript)
- **Database:** Supabase (Postgres 15+ with pgvector + pg_trgm)
- **Storage:** S3-compatible
- **Tunneling:** ngrok (for guest WiFi)

## Quick Start (5 minutes)

```bash
# 1. Clone
git clone https://github.com/krishianjan/Vision-Model-Shelf-Audit-Extract-.git
cd Vision-Model-Shelf-Audit-Extract-

# 2. Setup backend
cd api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with Supabase + OpenRouter + Groq + NVIDIA NIM keys

# 3. Setup mobile
cd ../mobile
npm install
cp .env.example .env
# Edit .env with API_URL

# 4. Setup web
cd ../web
npm install
cp .env.example .env

# 5. Run database migrations + seed catalog
cd ../db
python seeds/products.py  # Seeds 154 SKUs with BGE embeddings

# 6. Run (3 terminals)
# Terminal 1 (Backend):
cd api && source .venv/bin/activate && PYTHONPATH=. uvicorn src.main:app --port 8000 --reload

# Terminal 2 (Mobile):
cd mobile && npx expo start --clear

# Terminal 3 (Web):
cd web && npm run dev
```

## Key Features

### 3-Tier Brand Recognition System

The VLM pipeline uses a tiered approach to identify brands, even when labels are unreadable:

| Tier | Method | When | Fields Filled |
|------|--------|------|---------------|
| 1 | Text OCR | Label readable | `brand_read` + `field_confidence.brand` |
| 2 | Visual cues | Label unreadable but bottle is iconic | `visual_brand_guess` + `visual_brand_confidence` |
| 3 | Unknown | Cannot identify | Both null, still fills visual cues |

**Visual cue fields (always extracted, survive when text doesn't):**
- `bottle_shape`: tall_neck, short_squat, handle, flask, wine, can, custom
- `glass_tint`: clear, green, brown, blue, frosted, opaque
- `cap_type`: screw, cork, crown, plastic, t_top
- `label_color`: dominant color
- `label_design`: minimal, ornate, vintage, modern, bold_text, illustrated
- `damage_flags`: torn_label, dust, broken_seal, faded, dented
- `stock_level`: full, partial, low, empty
- `alcohol_subcategory`: single_malt_scotch, silver_tequila, ipa, cabernet, etc.

### Hallucination Control

- **Honesty Contract:** VLM transcribes ONLY literal visible text. Brand_read requires readable label text.
- **Hard Rules (deterministic):** Confidence < 0.70 → field set to NULL. Image quality < 0.6 caps all confidences.
- **Visual brand guess is separate:** Does NOT override `brand_read`. Uses model's own visual knowledge, not injected brand data.
- **No hardcoded brand data in VLM prompts:** Model uses its own training knowledge for visual recognition.
- **RAG matching is reference-only:** 154-SKU catalog is used post-extraction for lookup, never fed to the VLM.

### 3-Tier RAG SKU Matching

| Tier | Method | Threshold | When |
|------|--------|-----------|------|
| 1 | Exact text match | 1.0 | Brand + size match normalized string |
| 2 | Fuzzy (pg_trgm + rapidfuzz) | 0.65 | Typos, partial reads, OCR errors |
| 3 | Embedding cosine (BGE-small + pgvector) | 0.75 | Semantic similarity |
| 4 | Visual fallback | 0.60+ | If `visual_brand_guess` confident, tries RAG match on visual brand |

### Guardrail (Fast Gatekeeper)

- **YOLOv11n:** Detects bottle count + restricted objects (pizza, car, backpack)
- **CLIP fallback:** 23 positive prompts (alcohol shelf/bottle) vs 17 negative (water, food, selfies)
- **Single-bottle support:** YOLO with 1 container defers to CLIP — doesn't auto-reject
- **Low threshold:** Only rejects if CLIP avg_pos < 0.05 (truly non-alcohol)

### Product Catalog (154 SKUs)

Reference-only database used for RAG matching after VLM extraction:
- Vodka (12), Whiskey (26), Tequila (16), Rum (12), Gin (11)
- Wine (15), Beer (11), RTD (7), Liqueur (14)
- Each SKU has BGE-small-en embedding for semantic search
- UPC codes for exact UPC lookup
- No brand data injected into VLM prompts

## Environment Variables

### Backend (`api/.env`)

```env
DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@db.xxx.supabase.co:5432/postgres
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your-supabase-key
JWT_SECRET_KEY=your-secret-key-min-32-chars
OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_VLM_MODEL=qwen/qwen2.5-vl-72b-instruct
GROQ_API_KEY=your-groq-key
NVIDIA_NIM_API_KEY=your-nvidia-nim-key
S3_STORAGE_BUCKET=shelf-audits
ENVIRONMENT=development
```

### Mobile (`mobile/.env`)

```env
EXPO_PUBLIC_API_URL=http://localhost:8000
EXPO_PUBLIC_SUPABASE_URL=http://localhost:54321
EXPO_PUBLIC_SUPABASE_ANON_KEY=placeholder
```

## Database Schema

### shelf_audits
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| account_id | UUID FK | Store account |
| org_id | UUID | Organization |
| captured_by | UUID | Rep who captured |
| captured_at | TIMESTAMPTZ | When captured |
| fixture_type | TEXT | gondola, cooler, endcap, floor_display, unknown |
| capture_quality | JSONB | Image quality scores |
| status | TEXT | processing, final, retake_required, guardrail_rejected, processing_failed |
| model_version | TEXT | Which VLM model was used |
| latency_ms | INTEGER | Total pipeline latency |

### audit_observations
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| audit_id | UUID FK | Parent audit |
| matched_sku_id | UUID FK | Matched product (null = unmatched) |
| sku_guess_text | TEXT | Best text guess (brand_read or visual_brand_guess) |
| brand_read | TEXT | Brand from label text (null if unreadable) |
| visual_brand_guess | TEXT | Brand from visual cues (null if unidentifiable) |
| visual_brand_confidence | NUMERIC | 0-1 confidence in visual guess |
| product_read | TEXT | Product type from label |
| size_read | TEXT | Volume from label |
| facings | INTEGER | Count of bottles in group |
| shelf_position | TEXT | top, eye_level, reach, stoop, bottom, endcap, cooler_door |
| price_value | NUMERIC | Extracted price |
| price_confidence | NUMERIC | 0-1 price confidence |
| field_confidence | JSONB | Per-field confidence scores |
| status | TEXT | confirmed, partial, low_confidence, unmatched, occluded, unreadable |
| match_method | TEXT | exact, fuzzy, embedding, unresolved, visual_exact, visual_fuzzy |
| match_similarity | NUMERIC | 0-1 RAG match similarity |
| bottle_shape | TEXT | tall_neck, short_squat, handle, flask, wine, can, custom |
| glass_tint | TEXT | clear, green, brown, blue, frosted, opaque |
| cap_type | TEXT | screw, cork, crown, plastic, t_top |
| label_color | TEXT | Dominant label color |
| label_design | TEXT | minimal, ornate, vintage, modern, bold_text, illustrated |
| damage_flags | TEXT | torn_label, dust, broken_seal, faded, dented |
| stock_level | TEXT | full, partial, low, empty, unknown |
| alcohol_subcategory | TEXT | single_malt_scotch, silver_tequila, ipa, cabernet, etc |

### products
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| brand | TEXT | Brand name |
| product_name | TEXT | Product/variant name |
| size_ml | INTEGER | Volume in ml |
| pack_count | INTEGER | Pack size (beers) |
| category | TEXT | vodka, whiskey, tequila, rum, gin, wine, beer, rtd, liqueur, other |
| upc | TEXT UNIQUE | Barcode |
| embedding | VECTOR(384) | BGE-small-en embedding |
| bottle_shape | TEXT | (future: for visual matching) |
| glass_tint | TEXT | (future: for visual matching) |

## Running

### Terminal 1: Backend
```bash
cd api
source .venv/bin/activate
PYTHONPATH=. uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### Terminal 2: Mobile
```bash
cd mobile
npx expo start --clear
```

### Terminal 3: Web
```bash
cd web
npm run dev
```

### ngrok (Guest WiFi)
```bash
ngrok http 8000
# Copy HTTPS URL to mobile/.env: EXPO_PUBLIC_API_URL=https://xxx.ngrok-free.dev
```

## API Reference

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | None | Health check |
| `/auth/token` | POST | None | Login, get JWT |
| `/accounts` | GET | Bearer | List store accounts |
| `/audits` | POST | Bearer | Upload shelf image (multipart) |
| `/audits` | GET | Bearer | List audits |
| `/audits/{id}` | GET | Bearer | Get audit detail with observations |
| `/audits/{id}` | DELETE | Bearer | Delete audit |
| `/audits/{id}/cancel` | POST | Bearer | Cancel processing audit |
| `/reps/me/dashboard` | GET | Bearer | Rep dashboard stats |

## Pipeline Stages

1. **Quality Gate (OpenCV):** Blur detection, exposure check, resolution validation, aspect ratio
2. **Guardrail (YOLO + CLIP):** Object detection → semantic verification. Rejects non-alcohol, selfies, food
3. **VLM Extract (Qwen2.5-VL-72B):** Two-pass prompting:
   - Pass 1: Literal text transcription + visual cue capture
   - Pass 2: Structured extraction with tiered brand recognition
4. **RAG Ground (Postgres):** 3-tier SKU matching (exact → fuzzy → embedding) + visual brand fallback
5. **Judge (Hard Rules + DeepSeek):** Confidence calibration, quality degradation, glare impact
6. **Persist:** Single transaction writes audit, observations, images, events

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Module not found | `source .venv/bin/activate && pip install -r requirements.txt` |
| Port 8000 in use | `lsof -i :8000 \| awk '{print $2}' \| xargs kill -9` |
| ngrok URL expired | Restart `ngrok http 8000`, update mobile/.env |
| Mobile import errors | Use `../../../lib/api` not `../../lib/api` |
| fixture_type CHECK violation | Fixed: `table` and `hand_hold` normalize to `unknown` |
| Single bottle rejected | Fixed: YOLO 1-bottle defers to CLIP, CLIP threshold lowered to 0.05 |
