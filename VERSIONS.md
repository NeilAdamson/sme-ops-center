# Pinned Versions

Critical dependency versions for reproducibility. See PRD Section 6.5.

## Base Images (Docker)
- Python services: python:3.12-slim
- Node (mcp-bridge): node:20-slim
- Postgres: postgres:16-alpine
- Redis: redis:7-alpine

## API Gateway (Python)
- google-cloud-storage==2.14.0
- google-cloud-discoveryengine==0.17.0

## Vertex AI Search / Discovery Engine
- DATA_STORE_ID, ENGINE_ID: Per GCP project (console Steps 13-15); import prefix `gs://<bucket>/docs/`
- DISCOVERY_ENGINE_LOCATION: global (recommended)
- Permissions: Discovery Engine SA needs project-level storage.admin and bucket-level storage.objectAdmin; see GC-Build.ps1 / GC-Fix-DiscoveryEngine-Permissions.ps1
