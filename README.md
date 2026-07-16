# Vision Model Shelf Audit Extract — Complete Setup Guide

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture at a Glance](#architecture-at-a-glance)
3. [Prerequisites](#prerequisites)
4. [Database Setup (Supabase)](#database-setup-supabase)
5. [Project Structure](#project-structure)
6. [Installation Steps](#installation-steps)
7. [Configuration (Environment Variables)](#configuration-environment-variables)
8. [Running the System](#running-the-system)
9. [ngrok Tunneling (Guest WiFi)](#ngrok-tunneling-guest-wifi)
10. [Storage Setup (S3)](#storage-setup-s3)
11. [Testing the Setup](#testing-the-setup)
12. [Troubleshooting](#troubleshooting)
13. [API Reference](#api-reference)

---

## Project Overview

**Vision Model Shelf Audit Extract** is a production-grade system for automated retail shelf auditing using multi-model vision extraction with hallucination control.

### What It Does
- **Captures** shelf images from mobile devices
- **Analyzes** image quality (blur, lighting, framing)
- **Extracts** product information (brand, SKU, price, quantity)
- **Validates** extractions against knowledge base and business rules
- **Persists** verified data to database
- **Displays** real-time insights in mobile and web dashboards

### Tech Stack
- **Backend:** Python FastAPI + LangGraph
- **Frontend Mobile:** Expo React Native (TypeScript)
- **Frontend Web:** React + Vite (TypeScript)
- **Database:** Supabase (Postgres 15+)
- **Cache:** Redis (Supabase managed)
- **Storage:** S3-compatible (AWS S3 or similar)
- **VLM Models:** Qwen2.5-VL (via OpenRouter), Groq fallback
- **Judge Model:** DeepSeek (via OpenRouter)
- **Embeddings:** CLIP (multi-modal)
- **Tunneling:** ngrok (for guest WiFi)

---

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
# Edit .env with Supabase + OpenRouter keys

# 3. Setup mobile
cd ../mobile
npm install
cp .env.example .env
# Edit .env with API_URL

# 4. Setup web
cd ../web
npm install
cp .env.example .env

# 5. Create Supabase tables (see Database Setup section)

# 6. Run (3 terminals)
# Terminal 1 (Backend):
cd api && source .venv/bin/activate && PYTHONPATH=. uvicorn src.main:app --port 8000

# Terminal 2 (Mobile):
cd mobile && npx expo start --clear

# Terminal 3 (Web):
cd web && npm run dev
```

---

## Database Setup (Supabase)

### Step 1: Create Supabase Account

1. Go to https://supabase.com → Sign up
2. Create new project
3. Get keys from Settings → API
4. Copy `SUPABASE_URL` and `SUPABASE_KEY` to `.env`

### Step 2: Create Tables

Go to **SQL Editor** → Paste this:

sql
    -- Extensions
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    
    -- 1. ORGANIZATIONS
    CREATE TABLE IF NOT EXISTS accounts (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      org_id UUID NOT NULL,
      name TEXT NOT NULL,
      chain TEXT,
      channel_type TEXT,
      address TEXT,
      latitude DOUBLE PRECISION,
      longitude DOUBLE PRECISION,
      created_at TIMESTAMPTZ DEFAULT now()
    );
    
    -- 2. PRODUCT CATALOG (SKUs with vector embeddings for RAG)
    CREATE TABLE IF NOT EXISTS products (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      brand TEXT NOT NULL,
      product_name TEXT NOT NULL,
      size_ml INTEGER,
      pack_count INTEGER DEFAULT 1,
      category TEXT,
      upc TEXT,
      embedding VECTOR(512),
      created_at TIMESTAMPTZ DEFAULT now()
    );
    
    -- Index for pgvector similarity search
    CREATE INDEX IF NOT EXISTS idx_products_embedding ON products USING ivfflat (embedding vector_cosine_ops);
    
    -- 3. SHELF AUDITS
    CREATE TABLE IF NOT EXISTS shelf_audits (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      account_id UUID NOT NULL REFERENCES accounts(id),
      org_id UUID NOT NULL,
      captured_by UUID NOT NULL,
      captured_at TIMESTAMPTZ NOT NULL,
      received_at TIMESTAMPTZ DEFAULT now(),
      fixture_type TEXT,
      capture_quality JSONB,
      status TEXT NOT NULL,
      version INTEGER DEFAULT 1,
      superseded_by UUID REFERENCES shelf_audits(id),
      model_version TEXT,
      latency_ms INTEGER,
      created_at TIMESTAMPTZ DEFAULT now()
    );
    
    -- 4. AUDIT OBSERVATIONS (Extracted product data with confidence)
    CREATE TABLE IF NOT EXISTS audit_observations (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      audit_id UUID NOT NULL REFERENCES shelf_audits(id) ON DELETE CASCADE,
      matched_sku_id UUID REFERENCES products(id),
      sku_guess_text TEXT,
      brand_read TEXT,
      size_read TEXT,
      facings INTEGER,
      shelf_position TEXT,
      price_value NUMERIC,
      price_confidence NUMERIC,
      field_confidence JSONB DEFAULT '{}'::jsonb,
      status TEXT NOT NULL,
      match_method TEXT,
      match_similarity NUMERIC,
      notes TEXT,
      created_at TIMESTAMPTZ DEFAULT now(),
      product_read TEXT,
      flavor_variant TEXT,
      legibility TEXT DEFAULT 'fully_readable',
      object_type TEXT DEFAULT 'bottle',
      org_id UUID
    );
    
    -- 5. AUDIT IMAGES (Multiple shots per audit)
    CREATE TABLE IF NOT EXISTS audit_images (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      audit_id UUID NOT NULL REFERENCES shelf_audits(id) ON DELETE CASCADE,
      storage_path TEXT NOT NULL,
      preview_path TEXT,
      content_hash TEXT NOT NULL,
      width_px INTEGER,
      height_px INTEGER,
      size_bytes INTEGER,
      quality_score NUMERIC,
      created_at TIMESTAMPTZ DEFAULT now()
    );
    
    -- 6. PIPELINE EVENTS (Debug/audit trail)
    CREATE TABLE IF NOT EXISTS audit_events (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      audit_id UUID NOT NULL REFERENCES shelf_audits(id) ON DELETE CASCADE,
      event_type TEXT NOT NULL,
      payload JSONB DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ DEFAULT now()
    );
    
    -- 7. GUARDRAIL REJECTIONS (Non-alcohol/selfie tracking)
    CREATE TABLE IF NOT EXISTS guardrail_rejections (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      org_id UUID NOT NULL,
      captured_by UUID NOT NULL,
      account_id UUID,
      storage_path TEXT NOT NULL,
      content_hash TEXT,
      category TEXT NOT NULL,
      clip_confidence NUMERIC,
      reason TEXT,
      created_at TIMESTAMPTZ DEFAULT now()
    );
    
    -- 8. STORE ENTRY CAPTURES (Geofenced check-in)
    CREATE TABLE IF NOT EXISTS store_entry_captures (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      account_id UUID,
      org_id UUID NOT NULL,
      captured_by UUID NOT NULL,
      storage_path TEXT NOT NULL,
      ocr_store_name TEXT,
      ocr_confidence NUMERIC,
      latitude DOUBLE PRECISION,
      longitude DOUBLE PRECISION,
      captured_at TIMESTAMPTZ NOT NULL,
      created_at TIMESTAMPTZ DEFAULT now()
    );
    
    -- 9. REVIEW QUEUE (Unmatched observations for manual verification)
    CREATE TABLE IF NOT EXISTS review_queue (
      observation_id UUID,
      audit_id UUID,
      account_id UUID,
      captured_by UUID,
      brand_read TEXT,
      sku_guess_text TEXT,
      status TEXT,
      field_confidence JSONB,
      min_confidence NUMERIC,
      captured_at TIMESTAMPTZ
    );
    
    -- Sample data
    INSERT INTO products (brand, product_name, size_ml, category, upc) VALUES
      ('Coca-Cola', 'Zero Sugar', 330, 'beverages', '049000028904'),
      ('Pepsi', 'Diet Pepsi', 355, 'beverages', '012000001234'),
      ('Sprite', 'Lemon Lime', 500, 'beverages', '049000028905');
    
    INSERT INTO accounts (org_id, name, chain, channel_type) VALUES
      ('00000000-0000-0000-0000-000000000001', 'time sq Store', 'Reice', 'hypermarket'),
      ('00000000-0000-0000-0000-000000000001', 'Deli Store', NULL, 'liquor_store'),
      ('00000000-0000-0000-0000-000000000001', 'nyc Store', 'Metro', 'supermarket');
    


Click **Run** to create all tables.

---

## Installation

### Backend (Python)

```bash
cd api
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate (Windows)

pip install -r requirements.txt
cp .env.example .env
```

### Mobile (Expo)

```bash
cd mobile
npm install -g expo-cli
npm install
cp .env.example .env
```

### Web (React)

```bash
cd web
npm install
cp .env.example .env
```

---

## Environment Variables

### Backend (`api/.env`)

```env
# Database
DATABASE_URL=postgresql://postgres:PASSWORD@db.xxx.supabase.co:5432/postgres
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=..............................

# Auth
JWT_SECRET_KEY=your-secret-key-min-32-chars
ACCESS_TOKEN_EXPIRE_MINUTES=30

# VLM (OpenRouter - Qwen)
OPENROUTER_API_KEY=-...
OPENROUTER_VLM_MODEL=qwen/qwen-2.5-vl-72b-instruct

# Judge (DeepSeek)
DEEPSEEK_API_KEY=-...

# Fallback (Groq)
GROQ_API_KEY=_...

# Storage
SUPABASE_STORAGE_BUCKET=shelf-audits

# App
ENVIRONMENT=development
DEBUG=true
```

### Mobile (`mobile/.env`)

```env
# Local network
EXPO_PUBLIC_API_URL=http://1234567

# OR ngrok tunnel
EXPO_PUBLIC_API_URL=https://abc123-def456.ngrok-free.dev
```

### Web (`web/.env`)

```env
VITE_API_URL=http://localhost:8000
```

---

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
# Scan QR with Expo Go app
```

### Terminal 3: Web

```bash
cd web
npm run dev
# Open http://localhost:xxxx
```

---

## ngrok (Guest WiFi)

```bash
# 1. Signup: https://ngrok.com
# 2. Get token from dashboard
# 3. Setup
ngrok config add-authtoken <TOKEN>

# 4. Create tunnel (while API running)
ngrok http 8000

# 5. Copy HTTPS URL: https://abc123-def456.ngrok-free.dev
# 6. Update mobile/.env:
EXPO_PUBLIC_API_URL=https://abc123-def456.ngrok-free.dev

# 7. Restart mobile app
```

**Note:** URLs expire every 2 hours (free tier). Restart ngrok when needed.

---

## Testing

### Health Check

```bash
curl http://5:8000/health
# {"status":"ok"}
```

### Get Dashboard

```bash
curl http://:8000/reps/me/dashboard \
  -H "Authorization: Bearer <token>"
```

---

## Troubleshooting

### Backend Issues

**Module not found:**
```bash
source .venv/bin/activate
pip install -r requirements.txt --no-cache-dir
```

**Port 8000 in use:**
```bash
lsof -i :8000 | awk '{print $2}' | xargs kill -9
```

**Database error:**
- Check Supabase project exists
- Verify DATABASE_URL in .env
- Run SQL to create tables

### Mobile Issues

**Import path errors:**
Change `../../../lib/api` to `../../lib/api`

**API not found:**
- Check EXPO_PUBLIC_API_URL in .env
- Verify API running: `curl http://:8000/health`
- If ngrok: restart tunnel and update .env

**Bundle errors:**
```bash
npx expo start --clear
```

### ngrok Issues

**Connection refused:**
- Start API first on port 8000
- Then start ngrok

**URL expired:**
- Restart ngrok: `ngrok http 8000`
- Update .env with new URL
- Restart mobile app

---

## API Reference

### Health
```
GET /health → {"status":"ok"}
```

### Authentication
```
POST /auth/token
Body: {"email": "...", "password": "..."}
Response: {"access_token": "...", "token_type": "bearer"}
```

### Dashboard
```
GET /reps/me/dashboard
Auth: Bearer token
Response: {stores_visited, total_audits, avg_quality_score, ...}
```

### Upload Image
```
POST /audits/capture
Auth: Bearer token
Body: multipart/form-data file
Response: {audit_id, status: "processing", ...}
```

### Get Results
```
GET /audits/{audit_id}/results
Auth: Bearer token
Response: {audit_id, status, quality_score, observations: [...]}
```

### Store Insights
```
GET /stores/{account_id}/insights
Auth: Bearer token
Response: {insights: [{audit_id, captured_at, observation_count, ...}]}
```

---

## Database Schema

### shelf_audits
- `id` (UUID)
- `rep_id` (UUID FK users)
- `account_id` (UUID FK accounts)
- `image_path` (TEXT)
- `capture_quality` (JSONB)
- `status` (TEXT: captured|processing|extracted|verified|final|error)
- `captured_at` (TIMESTAMP)

### audit_observations
- `id` (UUID)
- `audit_id` (UUID FK shelf_audits)
- `observation` (JSONB: {sku, brand, price, quantity, confidence_scores, flags})
- `confidence_score` (NUMERIC)
- `verified` (BOOLEAN)
- `judge_verdict` (JSONB: {verdict, reasoning})
- `grounding_status` (TEXT: grounded|ungrounded|uncertain)

### skus
- `id` (UUID)
- `sku_code` (TEXT UNIQUE)
- `barcode` (TEXT)
- `brand_id` (UUID FK brands)
- `product_name` (TEXT)
- `category` (TEXT)
- `typical_facings_avg` (INT)

### audit_metrics
- `id` (UUID)
- `rep_id` (UUID FK users)
- `metric_date` (DATE)
- `total_audits_count` (INT)
- `successful_audits` (INT)
- `avg_quality_score` (NUMERIC)

---

## Key Features

✅ **Multi-model VLM orchestration** (Qwen + Groq fallback)  
✅ **Hallucination control** via Judge validation  
✅ **Quality scoring** (OpenCV blur/lighting/frame)  
✅ **RAG grounding** (fuzzy + semantic matching)  
✅ **Real-time dashboards** (mobile + web)  
✅ **Async processing** with LangGraph  
✅ **ngrok tunneling** for guest WiFi  
✅ **Type-safe APIs** (FastAPI + Pydantic)  


