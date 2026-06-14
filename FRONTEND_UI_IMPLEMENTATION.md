# Frontend UI Implementation Summary

## Overview

This document summarizes the frontend UI implementation work completed for Milestone 1, including three key tasks that enable end-to-end user interaction with the Docs module (Module A).

---

## Task 1: Environment Variable Configuration ✅

### Objective
Ensure Streamlit frontend uses `API_BASE_URL` environment variable (no hardcoding).

### Implementation

**Changes Made:**
- Updated `frontend/app.py` to read `API_BASE_URL` from environment using `os.getenv()`
- Default value: `http://api-gateway:8000` (Docker Compose networking, not localhost)
- Updated `docker-compose.yml` to use `API_BASE_URL` instead of `API_GATEWAY_URL` (aligned with PRD Section 10)
- Created `frontend/utils.py` utility module that also reads `API_BASE_URL` for API calls

**Key Code:**
```python
# frontend/app.py & utils.py
API_BASE_URL = os.getenv("API_BASE_URL", "http://api-gateway:8000")
```

### Verification
- ✅ No hardcoded `localhost:8000` in frontend code
- ✅ Uses Docker Compose service name (`api-gateway:8000`) for networking
- ✅ Aligned with PRD naming convention (`API_BASE_URL`)
- ✅ Works correctly in Docker Compose network

---

## Task 2: End-to-End UI Flow Implementation ✅

### Objective
Implement complete UI flow in the browser (http://localhost:8501) with:
- Landing page showing 3 tiles (only Docs enabled)
- Docs page with upload, status list, and query functionality

### Implementation

**1. Landing Page (`render_landing_page()`)**
- Three-column layout with module tiles:
  - **Docs**: "Open Docs Module" button (enabled, primary style)
  - **Inbox**: Button disabled with "Coming Soon" message
  - **Finance**: Button disabled with "Coming Soon" message
- Navigation state management using Streamlit session state
- Clicking "Open Docs Module" navigates to Docs page

**2. Docs Page (`render_docs_page()`)**
Three tabs with full functionality:

**📤 Upload Tab:**
- File uploader supporting PDF, TXT, DOCX, MD formats
- File selection preview (filename, size)
- Upload button with loading spinner
- Success message displaying:
  - `doc_id` (integer)
  - `request_id` (UUID)
  - `filename`
  - `message`
- Duplicate warning display (if applicable)
- Error handling with user-friendly messages

**📊 Status Tab:**
- "Refresh Status" button
- Auto-loads document status on tab open
- Displays list of uploaded documents in expandable cards:
  - Document ID
  - Filename
  - Indexed status (`pending`, `indexing`, `ready`, `failed`)
  - Upload timestamp (formatted)
  - Storage URI
  - Datastore reference (if available)
- Shows request_id for traceability
- Empty state message when no documents exist

**🔍 Query Tab:**
- Text area for entering questions
- "Query Documents" button
- Displays response with:
  - `request_id` (UUID)
  - `answer` (refusal text: "Information not found in internal records.")
  - `citations[]` (empty array, as expected for stub)
- Proper formatting for refusal messages
- Error handling for failed queries

**3. Utility Functions (`utils.py`)**
Created reusable API client functions:
- `upload_document(file_bytes, filename)` - POST to `/docs/upload`
- `get_document_status()` - GET `/docs/status`
- `query_documents(query)` - POST `/docs/query`
- All functions use `API_BASE_URL` from environment
- Error handling with try/except and logging
- Returns structured response data or error dictionaries

### Dependencies Added
- `requests==2.31.0` added to `frontend/requirements.txt`

### Features
- ✅ Landing page with 3 module tiles (Docs enabled, others coming soon)
- ✅ Complete Docs workflow (upload → status → query)
- ✅ Success messages show `doc_id` + `request_id`
- ✅ Status list shows all uploaded documents
- ✅ Query displays refusal text and empty citations array
- ✅ All API calls use `API_BASE_URL` environment variable
- ✅ Error handling with user-friendly messages
- ✅ Loading spinners for async operations
- ✅ Request ID displayed for traceability

---

## Task 3: Trust Surface - Request ID Panel ✅

### Objective
Add lightweight "Request ID" panel showing last `request_id` for upload, status, and query operations. This is the first visible trust hook without building a full audit screen.

### Implementation

**1. Session State Tracking**
- Added `last_request_ids` dictionary to Streamlit session state
- Tracks last `request_id` for three operation types:
  - `upload` - Last upload request ID
  - `status` - Last status query request ID
  - `query` - Last query request ID
- Initialized at startup with `None` values

**2. Request ID Panel (Sidebar)**
- Location: Streamlit sidebar on Docs page
- Title: "🔒 Request IDs"
- Subtitle: "Last request ID for each operation (for traceability)"
- Displays three sections:
  - **Upload**: Shows last upload request ID (or "_No requests yet_")
  - **Status**: Shows last status request ID (or "_No requests yet_")
  - **Query**: Shows last query request ID (or "_No requests yet_")
- Request IDs displayed in code blocks for easy copying
- Help text: "💡 Use these IDs to trace operations in audit logs"

**3. Automatic Tracking**
- **Upload tab**: Stores `request_id` in session state when upload succeeds
- **Status tab**: Stores `request_id` in session state when status query succeeds
- **Query tab**: Stores `request_id` in session state when query succeeds
- Updates happen automatically after successful API responses

### Features
- ✅ Lightweight design (sidebar panel, minimal UI footprint)
- ✅ Persistent across tab switches (uses Streamlit session state)
- ✅ Automatic updates when operations succeed
- ✅ Trust hook for traceability without full audit screen
- ✅ Clear labels showing which operation each request ID belongs to
- ✅ Easy-to-copy format (code blocks)
- ✅ Empty state messages for clarity

### User Experience
- Users can see their last request ID for each operation type at a glance
- Request IDs are visible in sidebar for quick reference
- No need to scroll or search - always visible while on Docs page
- Enables users to trace operations in audit logs using request IDs

---

## Files Created/Modified

### New Files
- `frontend/utils.py` - API client utility functions

### Modified Files
- `frontend/app.py` - Complete UI implementation with landing page, Docs page, and Request ID panel
- `frontend/requirements.txt` - Added `requests==2.31.0`
- `docker-compose.yml` - Changed `API_GATEWAY_URL` to `API_BASE_URL` for frontend service

---

## Testing

### Manual Testing Steps

1. **Start services:**
   ```bash
   docker compose up --build
   ```

2. **Access frontend:**
   - Open browser to http://localhost:8501

3. **Test landing page:**
   - Verify 3 tiles are visible
   - Verify only Docs tile is enabled
   - Click "Open Docs Module" and verify navigation

4. **Test upload:**
   - Navigate to Docs page → Upload tab
   - Select a file (PDF, TXT, DOCX, or MD)
   - Click "Upload Document"
   - Verify success message shows `doc_id` + `request_id`
   - Verify Request ID appears in sidebar under "Upload"

5. **Test status:**
   - Navigate to Status tab
   - Verify document list appears
   - Verify request_id appears in sidebar under "Status"
   - Click "Refresh Status" and verify it updates

6. **Test query:**
   - Navigate to Query tab
   - Enter a question (e.g., "What is our refund policy?")
   - Click "Query Documents"
   - Verify refusal text appears: "Information not found in internal records."
   - Verify citations array is empty
   - Verify request_id appears in sidebar under "Query"

### Verification Checklist
- ✅ Landing page shows 3 tiles (only Docs enabled)
- ✅ Docs page has all three tabs (Upload, Status, Query)
- ✅ Upload shows `doc_id` + `request_id` on success
- ✅ Status list shows uploaded documents
- ✅ Query shows refusal text and empty citations
- ✅ Request ID panel appears in sidebar
- ✅ Request IDs update automatically after operations
- ✅ All API calls use `API_BASE_URL` (no hardcoding)
- ✅ Error handling works correctly
- ✅ Loading spinners appear during async operations

---

## Next Steps

1. **Vertex AI Search Query Integration** (Milestone 1 remaining):
   - Replace query stub with Vertex AI Search search/answer API
   - Display real citations from search results
   - Status already shows indexed_status (pending/indexing/ready/failed); backend triggers import on upload when GCS is used
2. **Optional:** Add UI to trigger `POST /docs/index` for re-indexing PENDING docs (e.g. "Index now" button on Status tab)

2. **Additional Trust Surfaces**:
   - Expand Request ID panel to show timestamp
   - Add link to full audit screen (when implemented)
   - Show request status (success/failure) in panel

3. **UI Enhancements**:
   - Add document preview in status tab
   - Add citation display in query results
   - Add download functionality for uploaded documents
   - Improve error messages and user feedback

---

**Status: ✅ All three tasks complete and tested**
