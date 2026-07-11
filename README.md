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

```sql
-- 1. Users
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  first_name TEXT,
  last_name TEXT,
  role TEXT DEFAULT 'rep',
  created_at TIMESTAMP DEFAULT NOW()
);

-- 2. Accounts (Stores)
CREATE TABLE IF NOT EXISTS accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  location TEXT,
  region TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 3. Shelf Audits
CREATE TABLE IF NOT EXISTS shelf_audits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rep_id UUID NOT NULL REFERENCES users(id),
  account_id UUID NOT NULL REFERENCES accounts(id),
  image_path TEXT NOT NULL,
  capture_quality JSONB,
  status TEXT DEFAULT 'captured',
  captured_at TIMESTAMP DEFAULT NOW(),
  created_at TIMESTAMP DEFAULT NOW()
);

-- 4. Observations (Extracted Products)
CREATE TABLE IF NOT EXISTS audit_observations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_id UUID NOT NULL REFERENCES shelf_audits(id),
  observation JSONB NOT NULL,
  confidence_score NUMERIC(10,2),
  verified BOOLEAN DEFAULT FALSE,
  judge_verdict JSONB,
  grounding_status TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 5. SKUs
CREATE TABLE IF NOT EXISTS skus (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sku_code TEXT UNIQUE NOT NULL,
  brand_id UUID,
  product_name TEXT NOT NULL,
  category TEXT,
  typical_facings_avg INT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 6. Brands
CREATE TABLE IF NOT EXISTS brands (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT UNIQUE NOT NULL,
  category TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 7. Metrics
CREATE TABLE IF NOT EXISTS audit_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rep_id UUID REFERENCES users(id),
  metric_date DATE,
  total_audits_count INT,
  successful_audits INT,
  avg_quality_score NUMERIC(10,2),
  created_at TIMESTAMP DEFAULT NOW()
);

-- 8. Config
CREATE TABLE IF NOT EXISTS system_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  config_key TEXT UNIQUE NOT NULL,
  config_value TEXT,
  updated_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO system_config (config_key, config_value)
VALUES ('confidence_threshold_default', '0.75');

-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Sample data
INSERT INTO brands (name, category) VALUES
  ('Coca-Cola', 'Beverages'),
  ('Pepsi', 'Beverages'),
  ('Sprite', 'Beverages');

INSERT INTO accounts (name, location, region) VALUES
  ('Mumbai Store', 'Mumbai', 'West'),
  ('Delhi Store', 'Delhi', 'North'),
  ('Bangalore Store', 'Bangalore', 'South');
```

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


