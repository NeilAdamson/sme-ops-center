"""
SME Ops-Center Frontend
Operational AI Demo-in-a-Box
"""
import streamlit as st
from utils import (
    upload_document,
    get_document_status,
    get_doc_browse,
    query_documents,
    get_storage_config,
    get_doc_domains,
    move_document,
    trigger_index,
    delete_document,
    delete_storage_file,
    API_BASE_URL,
)
from datetime import datetime

st.set_page_config(
    page_title="SME Ops-Center",
    page_icon="📊",
    layout="wide"
)

# Initialize session state
if "current_page" not in st.session_state:
    st.session_state.current_page = "landing"

# Initialize request ID tracking (trust surface)
if "last_request_ids" not in st.session_state:
    st.session_state.last_request_ids = {
        "upload": None,
        "move": None,
        "status": None,
        "query": None
    }


def render_landing_page():
    """Render the landing page with module tiles."""
    st.title("🏢 SME Ops-Center")
    st.markdown("**Operational AI Demo-in-a-Box**")
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 📄 Docs")
        st.markdown("**Ask Your Business**")
        st.markdown("Upload and query your business documents")
        if st.button("Open Docs Module", key="docs_btn", use_container_width=True, type="primary"):
            st.session_state.current_page = "docs"
            st.rerun()
        st.info("✅ Enabled")
    
    with col2:
        st.markdown("### 📧 Inbox")
        st.markdown("**Email Triage**")
        st.markdown("Process and approve emails")
        st.button("Open Inbox Module", key="inbox_btn", use_container_width=True, disabled=True)
        st.warning("⏳ Coming Soon")
    
    with col3:
        st.markdown("### 💰 Finance")
        st.markdown("**Finance Lens**")
        st.markdown("Query Xero financial data")
        st.button("Open Finance Module", key="finance_btn", use_container_width=True, disabled=True)
        st.warning("⏳ Coming Soon")
    
    st.markdown("---")
    st.markdown(f"*API Gateway: `{API_BASE_URL}`*")


def _format_browse_file_line(file_item: dict) -> str:
    """Format a single file row for the storage explorer tree."""
    parts = [f"📄 {file_item.get('filename', 'unknown')}"]
    status = file_item.get("indexed_status")
    if status:
        parts.append(status)
    doc_id = file_item.get("doc_id")
    if doc_id is not None:
        parts.append(f"ID {doc_id}")
    if not file_item.get("tracked", True):
        parts.append("⚠ untracked")
    return " | ".join(parts)


def _render_browse_file_rows(files: list) -> None:
    """Render file rows inside a browse group expander."""
    if not files:
        st.caption("No files.")
        return
    for file_item in files:
        st.markdown(_format_browse_file_line(file_item))
        st.caption(f"`{file_item.get('uri', '')}`")
        if file_item.get("last_error"):
            st.error(file_item.get("last_error"))


def _render_storage_explorer_tree(browse_result: dict) -> None:
    """Render domain-grouped storage explorer using flat expanders (no nesting)."""
    groups = browse_result.get("groups", [])
    source = browse_result.get("source", "unknown")
    st.caption(f"Storage source: `{source}`")

    staging_groups = [g for g in groups if g.get("id") in ("staging", "staging_archive")]
    domain_groups = [g for g in groups if g.get("id") not in ("staging", "staging_archive")]

    if staging_groups:
        staging_count = sum(g.get("file_count", 0) for g in staging_groups)
        staging_bucket = staging_groups[0].get("bucket", "unknown")
        st.markdown(f"**Staging** ({staging_count} files)")
        st.caption(f"Bucket: `{staging_bucket}`")
        for group in staging_groups:
            if group.get("id") == "staging":
                sub_label = f"Active uploads ({group.get('file_count', 0)})"
                expanded = True
            else:
                sub_label = f"Archived ({group.get('file_count', 0)})"
                expanded = False
            if group.get("error"):
                st.error(f"Could not list {sub_label}: {group.get('error')}")
            with st.expander(sub_label, expanded=expanded):
                _render_browse_file_rows(group.get("files", []))

    for group in domain_groups:
        file_count = group.get("file_count", 0)
        label = group.get("label", group.get("id", "Domain"))
        with st.expander(f"📁 {label} ({file_count} files)", expanded=False):
            st.caption(f"Bucket: `{group.get('bucket', '')}` · prefix: `{group.get('prefix', '')}`")
            if group.get("error"):
                st.error(f"Could not list bucket: {group.get('error')}")
            _render_browse_file_rows(group.get("files", []))

    orphan_docs = browse_result.get("orphan_docs", [])
    if orphan_docs:
        st.warning(
            f"{len(orphan_docs)} tracked document(s) in the database were not found in GCS listings."
        )
        for orphan in orphan_docs:
            st.caption(
                f"ID {orphan.get('doc_id')}: {orphan.get('filename')} — `{orphan.get('storage_uri')}`"
            )


def render_docs_page():
    """Render the Docs module page."""
    st.title("📄 Docs - Ask Your Business")
    
    # Navigation back to landing
    if st.button("← Back to Home"):
        st.session_state.current_page = "landing"
        st.rerun()
    
    # Storage backend badge
    try:
        config = get_storage_config()
        storage_backend = config.get("storage_backend", "local") if config else "local"
        if storage_backend == "gcs":
            st.info("🗄️ **Storage:** GCS (Google Cloud Storage)")
        else:
            st.info("💾 **Storage:** Local")
    except Exception:
        # Fallback if config endpoint fails
        st.info("💾 **Storage:** Local")
    
    # Trust surface: Request ID panel (minimal)
    with st.sidebar:
        st.markdown("### 🔒 Request IDs")
        st.caption("Last request ID for each operation (for traceability)")
        st.markdown("---")
        
        upload_id = st.session_state.last_request_ids.get("upload")
        status_id = st.session_state.last_request_ids.get("status")
        move_id = st.session_state.last_request_ids.get("move")
        query_id = st.session_state.last_request_ids.get("query")
        
        if upload_id:
            st.markdown("**Upload:**")
            st.code(upload_id, language=None)
        else:
            st.markdown("**Upload:**")
            st.caption("_No requests yet_")
        
        if status_id:
            st.markdown("**Status:**")
            st.code(status_id, language=None)
        else:
            st.markdown("**Status:**")
            st.caption("_No requests yet_")

        if move_id:
            st.markdown("**Move:**")
            st.code(move_id, language=None)
        else:
            st.markdown("**Move:**")
            st.caption("_No requests yet_")
        
        if query_id:
            st.markdown("**Query:**")
            st.code(query_id, language=None)
        else:
            st.markdown("**Query:**")
            st.caption("_No requests yet_")
        
        st.markdown("---")
        st.caption("💡 Use these IDs to trace operations in audit logs")
    
    st.markdown("---")
    
    # Tabs for different operations
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload", "🗂️ File Manager", "📊 Status", "🔍 Query"])
    
    with tab1:
        st.subheader("Upload Document")
        st.markdown("Upload a document to your knowledge base.")
        
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=["pdf", "txt", "docx", "md"],
            help="Supported formats: PDF, TXT, DOCX, Markdown"
        )
        
        if uploaded_file is not None:
            st.info(f"📄 Selected: **{uploaded_file.name}** ({uploaded_file.size:,} bytes)")
            
            if st.button("Upload Document", type="primary"):
                with st.spinner("Uploading document..."):
                    file_bytes = uploaded_file.read()
                    result = upload_document(file_bytes, uploaded_file.name)
                    
                    if result and "error" not in result:
                        request_id = result.get("request_id")
                        # Store request_id for trust surface
                        if request_id:
                            st.session_state.last_request_ids["upload"] = request_id
                        
                        st.success("✅ Document uploaded successfully!")
                        st.json({
                            "doc_id": result.get("doc_id"),
                            "request_id": request_id,
                            "filename": result.get("filename"),
                            "message": result.get("message")
                        })
                        
                        # Show duplicate warning if present
                        if result.get("duplicate_warning"):
                            st.warning(f"⚠️ {result.get('duplicate_warning')}")
                    else:
                        error_msg = result.get("error", "Unknown error") if result else "No response from server"
                        st.error(f"❌ Upload failed: {error_msg}")
                        if result:
                            st.json(result)
    
    with tab2:
        st.subheader("File Explorer")
        st.markdown("Browse staging and domain storage. Manage document classification, indexing, and deletion.")

        domains_result = get_doc_domains()
        status_result = get_document_status()

        if domains_result and "error" not in domains_result:
            domains = domains_result.get("domains", [])
            staging = domains_result.get("staging", {})
        else:
            domains = []
            st.error("Could not load domain configuration.")

        if status_result and "error" not in status_result:
            documents = status_result.get("documents", [])
        else:
            documents = []

        with st.spinner("Loading storage contents..."):
            browse_result = get_doc_browse()

        if not browse_result or "error" in browse_result:
            st.error("Could not load storage contents.")
            browse_result = {"groups": [], "orphan_docs": []}

        # Dynamic calculation of folder lists and counts
        staged_files = []
        archive_files = []
        ops_files = []
        comp_files = []
        fin_files = []
        problem_files = []
        all_files = []
        
        # Deduplication map based on storage URI
        seen_uris = set()

        groups = browse_result.get("groups", [])
        for group in groups:
            g_id = group.get("id")
            g_files = group.get("files", [])
            for item in g_files:
                if g_id == "staging":
                    staged_files.append(item)
                elif g_id == "staging_archive":
                    archive_files.append(item)
                elif g_id == "operations":
                    ops_files.append(item)
                elif g_id == "compliance":
                    comp_files.append(item)
                elif g_id == "finance":
                    fin_files.append(item)
                
                uri = item.get("uri")
                if uri not in seen_uris:
                    seen_uris.add(uri)
                    all_files.append(item)

        # Identify problem files: failed status, last error, or untracked
        for item in all_files:
            if item.get("indexed_status") == "failed" or item.get("last_error"):
                prob_item = dict(item)
                if not prob_item.get("last_error"):
                    prob_item["last_error"] = "Indexing failed."
                problem_files.append(prob_item)
            elif not item.get("tracked", True):
                untracked_item = dict(item)
                untracked_item["last_error"] = "Untracked File: Exists in storage but has no database record."
                problem_files.append(untracked_item)

        # Add DB orphans to problem files
        orphan_docs = browse_result.get("orphan_docs", [])
        for orphan in orphan_docs:
            orphan_item = {
                "filename": orphan.get("filename"),
                "uri": orphan.get("storage_uri"),
                "doc_id": orphan.get("doc_id"),
                "indexed_status": orphan.get("indexed_status"),
                "domain": orphan.get("domain"),
                "tracked": True,
                "is_orphan": True,
                "last_error": "Orphan File: Tracked in database but missing from GCS/local storage."
            }
            problem_files.append(orphan_item)

        # Counts
        all_count = len(all_files)
        staging_count = len(staged_files)
        archive_count = len(archive_files)
        ops_count = len(ops_files)
        comp_count = len(comp_files)
        fin_count = len(fin_files)
        problem_count = len(problem_files)

        # Layout: Left Panel (Folders) & Right Panel (Files)
        left_col, right_col = st.columns([1, 4])

        with left_col:
            st.markdown("#### 📁 Folders")
            folder_options = [
                f"📂 All Documents ({all_count})",
                f"📥 Staging (Active) ({staging_count})",
                f"📦 Staging (Archive) ({archive_count})",
                f"📁 Operations ({ops_count})",
                f"📁 Compliance ({comp_count})",
                f"📁 Finance ({fin_count})",
                f"⚠️ Problem Files ({problem_count})"
            ]
            selected_folder = st.radio(
                "Folder Selection",
                folder_options,
                label_visibility="collapsed",
                key="folder_nav_radio"
            )

            # Map selection
            if "All Documents" in selected_folder:
                folder_id = "all"
                current_files = all_files
                folder_desc = "All tracked and untracked documents across storage locations."
            elif "Staging (Active)" in selected_folder:
                folder_id = "staging"
                current_files = staged_files
                folder_desc = "Active uploads waiting for business classification and domain movement."
            elif "Staging (Archive)" in selected_folder:
                folder_id = "staging_archive"
                current_files = archive_files
                folder_desc = "Archived staging files after they were successfully moved to domain buckets."
            elif "Operations" in selected_folder:
                folder_id = "operations"
                current_files = ops_files
                folder_desc = "Documents assigned to the Operations domain bucket."
            elif "Compliance" in selected_folder:
                folder_id = "compliance"
                current_files = comp_files
                folder_desc = "Documents assigned to the Compliance domain bucket."
            elif "Finance" in selected_folder:
                folder_id = "finance"
                current_files = fin_files
                folder_desc = "Documents assigned to the Finance domain bucket."
            else:
                folder_id = "problem"
                current_files = problem_files
                folder_desc = "Files containing indexing issues, database-storage orphans, or untracked assets."

            st.markdown("---")
            st.caption(f"**Description:**\n{folder_desc}")

        with right_col:
            st.markdown(f"### Selected Folder: `{selected_folder.split(' (')[0]}`")
            
            # Search / Filter box
            search_query = st.text_input("🔍 Search files...", key=f"file_search_{folder_id}", placeholder="Filter files by name, ID, status...")

            # Filter files
            if search_query:
                filtered_files = [
                    f for f in current_files
                    if search_query.lower() in f.get("filename", "").lower()
                    or search_query.lower() in str(f.get("doc_id", "") or "").lower()
                    or search_query.lower() in str(f.get("indexed_status", "") or "").lower()
                    or search_query.lower() in str(f.get("last_error", "") or "").lower()
                ]
            else:
                filtered_files = current_files

            if not filtered_files:
                st.info("No files found in this folder.")
            else:
                # Table headers
                col_name, col_id, col_status, col_actions = st.columns([3, 1, 1, 2])
                with col_name:
                    st.markdown("**Name / Storage URI**")
                with col_id:
                    st.markdown("**Doc ID**")
                with col_status:
                    st.markdown("**Status**")
                with col_actions:
                    st.markdown("**Actions**")
                st.markdown("---")

                # Render file rows
                for idx, item in enumerate(filtered_files):
                    col_name, col_id, col_status, col_actions = st.columns([3, 1, 1, 2])
                    
                    filename = item.get("filename", "unknown")
                    doc_id = item.get("doc_id")
                    status = item.get("indexed_status")
                    uri = item.get("uri", "")
                    last_error = item.get("last_error")
                    is_orphan = item.get("is_orphan", False)
                    is_tracked = item.get("tracked", True)

                    # Determine file icon
                    icon = "📄"
                    if filename.lower().endswith(".pdf"):
                        icon = "📕"
                    elif filename.lower().endswith(".txt"):
                        icon = "📝"
                    elif filename.lower().endswith(".docx"):
                        icon = "📘"
                    elif filename.lower().endswith(".md"):
                        icon = "Ⓜ️"

                    with col_name:
                        st.markdown(f"**{icon} {filename}**")
                        st.caption(f"`{uri}`")
                        if last_error:
                            st.caption(f"⚠️ :red[{last_error}]")

                    with col_id:
                        if doc_id is not None:
                            st.markdown(f"`{doc_id}`")
                        else:
                            st.markdown("*- (untracked)*")

                    with col_status:
                        # Badge logic
                        if is_orphan:
                            st.markdown("⚠️ :red[orphan]")
                        elif not is_tracked:
                            st.markdown("⚪ :gray[untracked]")
                        else:
                            st_lower = str(status).lower() if status else ""
                            if st_lower == "ready":
                                st.markdown("🟢 :green[ready]")
                            elif st_lower in ("indexing", "moving"):
                                st.markdown("🟡 :orange[indexing]")
                            elif st_lower == "failed":
                                st.markdown("🔴 :red[failed]")
                            elif st_lower in ("staged", "pending"):
                                st.markdown("🔵 :blue[staged]")
                            elif st_lower == "archived":
                                st.markdown("⚪ :gray[archived]")
                            else:
                                st.markdown(f"⚪ :gray[{status or 'unknown'}]")

                    with col_actions:
                        # Contextual actions using st.popover or buttons
                        # Action 1: Move (if staged/pending and has doc_id)
                        if is_tracked and doc_id is not None and not item.get("domain") and folder_id in ("all", "staging", "problem"):
                            # Render Move Popover
                            with st.popover("Move ➡️", use_container_width=True, key=f"pop_move_{doc_id}_{idx}"):
                                st.markdown(f"**Move Document:**\n`{filename}`")
                                if domains:
                                    domain_labels = {d["display_name"]: d["domain"] for d in domains}
                                    selected_label = st.selectbox(
                                        "Target Domain",
                                        list(domain_labels.keys()),
                                        key=f"move_sel_{doc_id}_{idx}"
                                    )
                                    archive_staging = st.checkbox(
                                        "Archive staging copy after move",
                                        value=True,
                                        key=f"archive_chk_{doc_id}_{idx}"
                                    )
                                    target_domain = domain_labels[selected_label]
                                    
                                    # Warn if data store id is missing
                                    domain_config = next((d for d in domains if d["domain"] == target_domain), {})
                                    if not domain_config.get("data_store_id"):
                                        st.warning("⚠️ Data Store ID is missing for this domain; indexing will fail.")

                                    if st.button("Confirm Move", type="primary", key=f"move_btn_{doc_id}_{idx}", use_container_width=True):
                                        with st.spinner("Moving document..."):
                                            result = move_document(doc_id, target_domain, archive_staging)
                                            if result and "error" not in result:
                                                req_id = result.get("request_id")
                                                if req_id:
                                                    st.session_state.last_request_ids["move"] = req_id
                                                st.success("Moved and indexing queued.")
                                                st.rerun()
                                            else:
                                                st.error(result.get("error", "Move failed"))
                                else:
                                    st.error("No target domains configured.")

                        # Action 2: Retry Indexing (if failed/classified and tracked)
                        elif is_tracked and doc_id is not None and item.get("domain") and status in ("failed", "classified", "pending") and folder_id in ("all", "operations", "compliance", "finance", "problem"):
                            if st.button("🔄 Index", use_container_width=True, key=f"retry_idx_btn_{doc_id}_{idx}"):
                                with st.spinner("Queueing indexing job..."):
                                    result = trigger_index(doc_id)
                                    if result and "error" not in result:
                                        st.success("Indexing job queued successfully.")
                                        st.rerun()
                                    else:
                                        st.error(result.get("error", "Indexing queue request failed"))

                        # Action 3: Cleanup DB Record (for database orphans)
                        elif is_orphan and doc_id is not None:
                            if st.button("🧹 Clean DB", use_container_width=True, key=f"clean_db_btn_{doc_id}_{idx}", help="Clean database record since file is missing from storage"):
                                with st.spinner("Cleaning database record..."):
                                    result = delete_document(doc_id, hard_delete=True, delete_storage=False)
                                    if result and "error" not in result:
                                        st.success("Database record cleaned up.")
                                        st.rerun()
                                    else:
                                        st.error(result.get("error", "Failed to clean DB record"))

                        # Action 4: Delete storage file (for untracked storage files)
                        elif not is_tracked and uri:
                            if st.button("🗑️ Delete File", use_container_width=True, key=f"del_untracked_btn_{idx}", help="Permanently delete file from storage"):
                                with st.spinner("Deleting storage file..."):
                                    result = delete_storage_file(uri)
                                    if result and "error" not in result:
                                        st.success("Storage file deleted.")
                                        st.rerun()
                                    else:
                                        st.error(result.get("error", "Failed to delete storage file"))

                        # Action 5: Delete (for tracked documents)
                        if is_tracked and doc_id is not None and not is_orphan:
                            with st.popover("🗑️ Delete", use_container_width=True, key=f"pop_del_{doc_id}_{idx}"):
                                st.markdown(f"**Delete Document:**\n`{filename}`")
                                delete_mode = st.radio(
                                    "Delete options",
                                    ["Soft-delete (preserves record, sets deleted_at)", "Hard-delete (permanently removes from DB)"],
                                    key=f"del_mode_radio_{doc_id}_{idx}"
                                )
                                delete_from_storage = st.checkbox(
                                    "Delete file from local/GCS storage",
                                    value=True,
                                    key=f"del_storage_chk_{doc_id}_{idx}"
                                )
                                is_hard = "Hard-delete" in delete_mode

                                if st.button("Confirm Delete", type="primary", key=f"del_btn_{doc_id}_{idx}", use_container_width=True):
                                    with st.spinner("Deleting..."):
                                        result = delete_document(doc_id, hard_delete=is_hard, delete_storage=delete_from_storage)
                                        if result and "error" not in result:
                                            st.success(result.get("message", "Document deleted"))
                                            st.rerun()
                                        else:
                                            st.error(result.get("error", "Delete failed"))

    with tab3:
        st.subheader("Document Status")
        st.markdown("View all uploaded documents and their indexing status.")
        
        # Auto-load status on tab open or manual refresh
        if st.button("Refresh Status", type="primary"):
            st.rerun()
        
        with st.spinner("Loading document status..."):
            result = get_document_status()
            
            if result and "error" not in result:
                request_id = result.get("request_id")
                # Store request_id for trust surface
                if request_id:
                    st.session_state.last_request_ids["status"] = request_id
                
                documents = result.get("documents", [])
                
                if documents:
                    st.success(f"Found {len(documents)} document(s)")
                    st.caption(f"Request ID: `{request_id}`")
                    
                    # Display documents in a table
                    for doc in documents:
                        with st.expander(f"📄 {doc.get('filename', 'Unknown')} (ID: {doc.get('id')})"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.markdown(f"**Document ID:** {doc.get('id')}")
                                st.markdown(f"**Filename:** {doc.get('filename')}")
                                st.markdown(f"**Status:** `{doc.get('indexed_status', 'pending')}`")
                                if doc.get("domain"):
                                    st.markdown(f"**Domain:** `{doc.get('domain')}`")
                            
                            with col2:
                                uploaded_at = doc.get('uploaded_at')
                                if uploaded_at:
                                    # Parse ISO format datetime
                                    try:
                                        dt = datetime.fromisoformat(uploaded_at.replace('Z', '+00:00'))
                                        st.markdown(f"**Uploaded:** {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                                    except:
                                        st.markdown(f"**Uploaded:** {uploaded_at}")
                                st.markdown(f"**Storage URI:** `{doc.get('storage_uri')}`")
                                if doc.get('staging_uri'):
                                    st.markdown(f"**Staging URI:** `{doc.get('staging_uri')}`")
                                
                                if doc.get('datastore_ref'):
                                    st.markdown(f"**Datastore Ref:** `{doc.get('datastore_ref')}`")
                                if doc.get('index_job_id'):
                                    st.markdown(f"**Index Job:** `{doc.get('index_job_id')}`")
                                if doc.get('last_error'):
                                    st.error(doc.get('last_error'))
                                if doc.get("domain") and doc.get("indexed_status") in ["classified", "failed"]:
                                    if st.button("Queue indexing", key=f"index_{doc.get('id')}"):
                                        with st.spinner("Queueing indexing job..."):
                                            index_result = trigger_index(doc.get("id"))
                                            if index_result and "error" not in index_result:
                                                st.success("Indexing queued.")
                                                st.json(index_result)
                                            else:
                                                st.error("Indexing queue request failed.")
                                                if index_result:
                                                    st.json(index_result)
                else:
                    st.info("📭 No documents uploaded yet. Use the Upload tab to add documents.")
                    if request_id:
                        st.caption(f"Request ID: `{request_id}`")
            else:
                error_msg = result.get("error", "Unknown error") if result else "No response from server"
                st.error(f"❌ Failed to retrieve document status: {error_msg}")
                if result:
                    st.json(result)
    
    with tab4:
        st.subheader("Query Documents")
        st.markdown("Ask questions about your uploaded documents.")

        domains_result = get_doc_domains()
        domain_options = {"All domains": "all"}
        if domains_result and "error" not in domains_result:
            for domain in domains_result.get("domains", []):
                label = domain.get("display_name", domain.get("domain", "")).strip()
                if not domain.get("query_ready"):
                    label = f"{label} (not query-ready)"
                domain_options[label] = domain.get("domain")

        selected_domain_label = st.selectbox("Search scope", list(domain_options.keys()))
        selected_domain = domain_options[selected_domain_label]
        
        query_text = st.text_area(
            "Enter your question",
            height=100,
            placeholder="e.g., What is our refund policy?"
        )
        
        if st.button("Query Documents", type="primary"):
            if not query_text or not query_text.strip():
                st.warning("⚠️ Please enter a question before querying.")
            else:
                with st.spinner("Querying documents..."):
                    result = query_documents(query_text.strip(), selected_domain)
                    
                    if result and "error" not in result:
                        request_id = result.get("request_id")
                        # Store request_id for trust surface
                        if request_id:
                            st.session_state.last_request_ids["query"] = request_id
                        
                        answer = result.get("answer", "")
                        citations = result.get("citations", [])
                        domains_queried = result.get("domains_queried", [])
                        
                        st.markdown("### Response")
                        st.caption(f"Request ID: `{request_id}`")
                        if domains_queried:
                            st.caption(f"Domains queried: `{', '.join(domains_queried)}`")
                        if result.get("grounding_score") is not None:
                            st.caption(f"Grounding score: `{result.get('grounding_score')}`")
                        
                        # Display answer
                        st.markdown("#### Answer")
                        if answer:
                            if "not found" in answer.lower() or "no information" in answer.lower():
                                st.info(f"ℹ️ {answer}")
                            else:
                                st.success(answer)
                        else:
                            st.warning("No answer provided.")
                        
                        # Display citations
                        st.markdown("#### Citations")
                        if citations and len(citations) > 0:
                            st.success(f"Found {len(citations)} citation(s)")
                            for idx, citation in enumerate(citations, 1):
                                with st.expander(f"Citation {idx}: {citation.get('doc_name', 'Unknown')}"):
                                    if citation.get('domain'):
                                        st.markdown(f"**Domain:** `{citation.get('domain')}`")
                                    st.markdown(f"**Snippet:** {citation.get('snippet', 'N/A')}")
                                    if citation.get('page_or_section'):
                                        st.markdown(f"**Page/Section:** {citation.get('page_or_section')}")
                                    if citation.get('uri_or_id'):
                                        st.markdown(f"**URI/ID:** `{citation.get('uri_or_id')}`")
                        else:
                            st.info("📭 No citations found. (This is expected until Vertex AI Search is integrated.)")
                    else:
                        error_msg = result.get("error", "Unknown error") if result else "No response from server"
                        st.error(f"❌ Query failed: {error_msg}")
                        if result:
                            st.json(result)


# Main app logic
def main():
    """Main application logic."""
    if st.session_state.current_page == "landing":
        render_landing_page()
    elif st.session_state.current_page == "docs":
        render_docs_page()
    else:
        st.session_state.current_page = "landing"
        st.rerun()


if __name__ == "__main__":
    main()
