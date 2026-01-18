# Frontend Service

**Streamlit-based UI for SME Ops-Center**

This service provides the user interface for interacting with the SME Ops-Center system. It's a thin UI shell that communicates exclusively with the API Gateway via HTTP.

## Overview

The frontend is built with Streamlit and implements:
- Module-based navigation (Docs, Inbox, Finance)
- Document upload and management (Module A)
- Document status viewing
- Document querying (stub until Vertex AI Search integrated)
- Request ID tracking for traceability (trust surface)

## Architecture

- **Framework:** Streamlit (Python 3.12)
- **API Client:** `requests` library
- **API Gateway:** All business logic via `API_BASE_URL` environment variable
- **No Hardcoding:** All URLs use environment variables

## Configuration

### Environment Variables

The frontend reads `API_BASE_URL` from environment variables (set in `docker-compose.yml`):

```bash
API_BASE_URL=http://api-gateway:8000  # Docker Compose networking
```

**Default Value:** `http://api-gateway:8000` (for Docker Compose networking)

**No hardcoding:** The frontend never uses hardcoded `localhost:8000` URLs.

## Features

### Landing Page

- Three module tiles:
  - **Docs** - Ask Your Business (enabled)
  - **Inbox** - Email Triage (coming soon)
  - **Finance** - Finance Lens (coming soon)
- Click "Open Docs Module" to navigate to Docs functionality

### Docs Module

Three tabs with full functionality:

#### 📤 Upload Tab
- File uploader (supports PDF, TXT, DOCX, MD)
- Upload button with loading spinner
- Success message showing:
  - `doc_id` (integer)
  - `request_id` (UUID)
  - `filename`
  - `message`
- Duplicate warning (if applicable)
- Error handling

#### 📊 Status Tab
- "Refresh Status" button
- Auto-loads document status
- Displays all uploaded documents in expandable cards:
  - Document ID
  - Filename
  - Indexed status (pending/indexing/ready/failed)
  - Upload timestamp
  - Storage URI
  - Datastore reference (if available)
- Shows `request_id` for traceability
- Empty state message when no documents

#### 🔍 Query Tab
- Text area for entering questions
- "Query Documents" button
- Displays response:
  - `request_id` (UUID)
  - `answer` (currently refusal: "Information not found in internal records.")
  - `citations[]` (empty array until Vertex AI Search integrated)
- Proper formatting for refusal messages
- Error handling

### Trust Surface: Request ID Panel

- **Location:** Sidebar on Docs page
- **Purpose:** Show last `request_id` for each operation type (upload, status, query)
- **Features:**
  - Automatically updates when operations succeed
  - Persists across tab switches (session state)
  - Easy-to-copy format (code blocks)
  - Empty state messages
  - Help text: "💡 Use these IDs to trace operations in audit logs"

This is the first visible trust hook, enabling traceability without needing a full audit screen.

## Project Structure

```
frontend/
├── app.py              # Main Streamlit application
├── utils.py            # API client utility functions
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container definition
└── README.md           # This file
```

## Dependencies

- `streamlit==1.31.0` - UI framework
- `requests==2.31.0` - HTTP client for API Gateway

## API Client Functions

All API calls are made through utility functions in `utils.py`:

### `upload_document(file_bytes, filename)`
Uploads a document to the API Gateway.
- **Endpoint:** `POST /docs/upload`
- **Returns:** Response dictionary with `doc_id`, `request_id`, `filename`, `message`

### `get_document_status()`
Retrieves status of all uploaded documents.
- **Endpoint:** `GET /docs/status`
- **Returns:** Response dictionary with `request_id` and `documents[]` array

### `query_documents(query)`
Queries documents (stub until Vertex AI Search integrated).
- **Endpoint:** `POST /docs/query`
- **Returns:** Response dictionary with `request_id`, `answer`, `citations[]`

All functions:
- Use `API_BASE_URL` from environment
- Handle errors gracefully
- Return structured response data or error dictionaries
- Include logging for debugging

## Development

### Running Locally

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variable:**
   ```bash
   export API_BASE_URL=http://localhost:8000  # For local API Gateway
   ```

3. **Run Streamlit:**
   ```bash
   streamlit run app.py
   ```

4. **Access UI:**
   - Open browser to http://localhost:8501

### Running in Docker

The frontend is automatically started via Docker Compose:

```bash
docker compose up frontend
```

Access at: http://localhost:8501

## Testing

### Manual Testing Checklist

1. **Landing Page:**
   - [ ] Three tiles visible (Docs, Inbox, Finance)
   - [ ] Only Docs tile is enabled
   - [ ] Click "Open Docs Module" navigates correctly

2. **Upload Tab:**
   - [ ] File uploader works
   - [ ] Upload button triggers API call
   - [ ] Success message shows `doc_id` + `request_id`
   - [ ] Request ID appears in sidebar
   - [ ] Duplicate warning appears (if applicable)

3. **Status Tab:**
   - [ ] Document list loads automatically
   - [ ] All document details visible
   - [ ] Request ID appears in sidebar
   - [ ] "Refresh Status" button works

4. **Query Tab:**
   - [ ] Query input accepts text
   - [ ] Query button triggers API call
   - [ ] Refusal text displays correctly
   - [ ] Empty citations array shown
   - [ ] Request ID appears in sidebar

5. **Request ID Panel:**
   - [ ] Appears in sidebar on Docs page
   - [ ] Updates automatically after operations
   - [ ] Shows correct request IDs for each operation
   - [ ] Empty state messages appear when no requests

## Configuration Verification

To verify the frontend uses `API_BASE_URL` (no hardcoding):

```bash
# Check frontend code
grep -r "localhost:8000" frontend/  # Should return nothing
grep -r "API_BASE_URL" frontend/    # Should find usage

# Check environment variable
docker compose config | grep API_BASE_URL  # Should show: API_BASE_URL=http://api-gateway:8000
```

## Error Handling

The frontend includes comprehensive error handling:

- **API Errors:** Displays user-friendly error messages
- **Network Errors:** Shows connection failure messages
- **Validation Errors:** Displays form validation messages
- **Loading States:** Shows spinners during async operations
- **Empty States:** Shows helpful messages when no data exists

## Security Notes

- All API calls go through API Gateway (no direct database access)
- No secrets stored in frontend code
- CORS configured on API Gateway for Streamlit origin
- Request IDs enable audit trail tracking

## Future Enhancements

1. **Module B (Inbox):**
   - Email upload interface
   - Approval workflow UI
   - Email status display

2. **Module C (Finance):**
   - Xero connection status
   - Finance query interface
   - Verification rows display

3. **Additional Trust Surfaces:**
   - Full audit screen
   - Request history
   - Citation display improvements

4. **UI Improvements:**
   - Document preview
   - Better error messages
   - Loading state improvements
   - Responsive design enhancements

## Troubleshooting

### Frontend won't connect to API Gateway

1. **Check API_BASE_URL:**
   ```bash
   docker compose exec frontend env | grep API_BASE_URL
   ```
   Should show: `API_BASE_URL=http://api-gateway:8000`

2. **Verify API Gateway is running:**
   ```bash
   docker compose ps api-gateway
   curl http://localhost:8000/health
   ```

3. **Check network connectivity:**
   ```bash
   docker compose exec frontend ping api-gateway
   ```

### Request IDs not appearing

- Ensure operations complete successfully (check for errors)
- Verify session state is preserved (don't clear browser session)
- Check browser console for JavaScript errors

### Upload fails

- Verify file size is reasonable
- Check file format is supported (PDF, TXT, DOCX, MD)
- Verify API Gateway uploads directory has write permissions
- Check API Gateway logs for errors

## Related Documentation

- [Main README](../README.md) - Project overview
- [Milestone 1 Status](../MILESTONE1_STATUS.md) - Backend API status
- [Frontend UI Implementation](../FRONTEND_UI_IMPLEMENTATION.md) - Detailed UI implementation summary
- [API Gateway README](../api-gateway/README.md) - Backend API documentation
