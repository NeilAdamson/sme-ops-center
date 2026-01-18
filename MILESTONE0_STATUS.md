# Milestone 0 Status - Docker Compose Scaffold

## Status: ✅ Complete

All containers build and start successfully.

## Issues Encountered and Resolved

### 1. **UID 1000 Conflict in Node Images**
**Problem:** Node images already have a user with UID 1000 (`node` user), causing `useradd -m -u 1000` to fail with "UID 1000 is not unique".

**Solution:** 
- Updated `mcp-bridge/Dockerfile` to use the existing `node` user instead of creating a new one
- Updated Python Dockerfiles to check if UID 1000 exists before creating users

**Files Changed:**
- `mcp-bridge/Dockerfile` - Uses existing `node` user
- `frontend/Dockerfile` - Conditional user creation
- `api-gateway/Dockerfile` - Conditional user creation
- `worker/Dockerfile` - Conditional user creation

---

### 2. **Empty requirements.txt Causing Pip Errors**
**Problem:** Empty `worker/requirements.txt` could cause pip install to fail.

**Solution:** 
- Added conditional check in `worker/Dockerfile` to skip pip install if requirements.txt is empty or contains only comments

**Files Changed:**
- `worker/Dockerfile` - Added conditional pip install

---

### 3. **npm ci Requiring package-lock.json**
**Problem:** `npm ci --only=production` requires `package-lock.json` which doesn't exist in scaffold phase.

**Solution:** 
- Switched to `npm install --only=production` for scaffold phase
- Can switch back to `npm ci` once package-lock.json is generated

**Files Changed:**
- `mcp-bridge/Dockerfile` - Uses `npm install` instead of `npm ci`

---

### 4. **Express Module Not Found (Volume Mount Issue)**
**Problem:** Bind mount `./mcp-bridge:/app` was overwriting the `node_modules` directory installed during Docker build, causing "Cannot find module 'express'" error.

**Solution:** 
- Added anonymous volume `/app/node_modules` to preserve installed dependencies
- Bind mount still allows source code editing, but node_modules persists from image

**Files Changed:**
- `docker-compose.yml` - Added anonymous volume for mcp-bridge node_modules

---

### 5. **Postgres/Redis Permission Errors**
**Problem:** Postgres and Redis were forced to run as `user: "999:999"`, preventing them from initializing their data directories with proper permissions.

**Solution:** 
- Removed `user: "999:999"` override from both services
- Official images already run as non-root users by default (Postgres: `postgres` user UID 70, Redis: `redis` user)

**Files Changed:**
- `docker-compose.yml` - Removed user overrides from postgres and redis services

---

### 6. **Python Version Alignment**
**Problem:** PRD specifies Python 3.12, but Dockerfiles used Python 3.11.

**Solution:** 
- Updated all Python Dockerfiles to use `python:3.12-slim`

**Files Changed:**
- `frontend/Dockerfile` - Python 3.12-slim
- `api-gateway/Dockerfile` - Python 3.12-slim
- `worker/Dockerfile` - Python 3.12-slim

---

### 7. **Environment Variable Naming Alignment**
**Problem:** `.env.example` used different variable names than PRD Section 10.

**Solution:** 
- Aligned all environment variables with PRD naming conventions:
  - `GOOGLE_CLOUD_PROJECT` (was `GCP_PROJECT_ID`)
  - `GOOGLE_GENAI_USE_VERTEXAI=True` (added)
  - `VERTEX_LOCATION` (was `VERTEX_AI_LOCATION`)
  - `DISCOVERY_ENGINE_LOCATION` (added)
  - `GEMINI_MODEL_PRIMARY` / `GEMINI_MODEL_FALLBACK` (corrected naming)
  - Database naming aligned: `smeops` user/db

**Files Changed:**
- `.env.example` - Complete alignment with PRD Section 10
- `docker-compose.yml` - Database naming updated to match

---

### 8. **Node Version Pinning**
**Problem:** PRD requires explicit version pinning for Node.

**Solution:** 
- Added `engines` field to `mcp-bridge/package.json` specifying Node >=20.0.0 <21.0.0

**Files Changed:**
- `mcp-bridge/package.json` - Added engines field

---

### 9. **Docker Compose Version Field**
**Problem:** Obsolete `version: '3.8'` field in docker-compose.yml.

**Solution:** 
- Removed version field (not needed in Docker Compose v2+)

**Files Changed:**
- `docker-compose.yml` - Removed version field

---

## Final Configuration

### Services Running:
- ✅ `frontend` (Streamlit) - Port 8501
- ✅ `api-gateway` (FastAPI) - Port 8000
- ✅ `worker` - Idle worker process
- ✅ `mcp-bridge` (Node) - Port 3000
- ✅ `postgres` - Port 5432
- ✅ `redis` - Port 6379

### Volumes:
- ✅ `pgdata` - PostgreSQL persistence
- ✅ `uploads` - File uploads storage
- ✅ `sessions` - Session data storage
- ✅ `redis-data` - Redis persistence
- ✅ Anonymous volume for mcp-bridge node_modules

### Security:
- ✅ All application containers run as non-root (UID 1000)
- ✅ Postgres/Redis use official image default non-root users
- ✅ All base images use slim/alpine variants

---

## Next Steps

Milestone 0 is complete. Ready for:
- Milestone 1: Module A (Document upload and query with citations)
- Database migrations setup
- Audit event write capability
