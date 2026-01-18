# Build Issues Resolved - Quick Summary

## Issues Encountered During Milestone 0 Setup

### 1. **UID 1000 Conflict in Node Images** ✅ RESOLVED
**Error:** `useradd: UID 1000 is not unique`

**Root Cause:** Node base images already include a `node` user with UID 1000.

**Fix:** Use existing `node` user instead of creating new one.

---

### 2. **Express Module Not Found** ✅ RESOLVED
**Error:** `Error: Cannot find module 'express'`

**Root Cause:** Bind mount `./mcp-bridge:/app` overwrote `node_modules` installed during Docker build.

**Fix:** Added anonymous volume `/app/node_modules` to preserve dependencies.

---

### 3. **Postgres Permission Errors** ✅ RESOLVED
**Error:** `chmod: /var/lib/postgresql/data: Operation not permitted`

**Root Cause:** Forcing Postgres to run as `user: "999:999"` prevented initialization.

**Fix:** Removed user override; Postgres uses default `postgres` user (non-root, UID 70 in Alpine).

---

### 4. **Redis Permission Issues** ✅ RESOLVED
**Error:** Similar to Postgres - volume initialization failed.

**Root Cause:** Overriding default `redis` user prevented proper initialization.

**Fix:** Removed user override; Redis uses default non-root user.

---

### 5. **Python Version Mismatch** ✅ RESOLVED
**Issue:** PRD specifies Python 3.12, but Dockerfiles used 3.11.

**Fix:** Updated all Python Dockerfiles to `python:3.12-slim`.

---

### 6. **Environment Variable Naming** ✅ RESOLVED
**Issue:** `.env.example` didn't match PRD Section 10 naming conventions.

**Fix:** Aligned all variables with PRD (e.g., `GOOGLE_CLOUD_PROJECT`, `VERTEX_LOCATION`, etc.).

---

### 7. **Empty requirements.txt** ✅ RESOLVED
**Issue:** Worker's empty requirements.txt could cause pip install errors.

**Fix:** Added conditional check to skip pip install if file is empty.

---

### 8. **npm ci Without package-lock.json** ✅ RESOLVED
**Issue:** `npm ci` requires `package-lock.json` which doesn't exist in scaffold.

**Fix:** Use `npm install` for scaffold phase; switch to `npm ci` once lock file exists.

---

## Key Lessons

1. **Official Docker images handle users correctly** - Don't override unless absolutely necessary
2. **Bind mounts overwrite image contents** - Use anonymous volumes to preserve installed dependencies
3. **Always align with PRD specifications** - Prevents configuration drift
4. **Check for existing users before creating** - Prevents UID conflicts
5. **Use conditional installs for empty dependency files** - Gracefully handles scaffold phase

---

## Current Status

✅ All 6 services build and start successfully  
✅ All containers run as non-root  
✅ Named volumes configured for persistence  
✅ Environment variables aligned with PRD  
✅ Health endpoints functional  

**Ready for Milestone 1 implementation.**
