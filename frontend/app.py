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
    """Render domain-grouped storage explorer using nested expanders."""
    groups = browse_result.get("groups", [])
    source = browse_result.get("source", "unknown")
    st.caption(f"Storage source: `{source}`")

    staging_groups = [g for g in groups if g.get("id") in ("staging", "staging_archive")]
    domain_groups = [g for g in groups if g.get("id") not in ("staging", "staging_archive")]

    if staging_groups:
        staging_count = sum(g.get("file_count", 0) for g in staging_groups)
        staging_bucket = staging_groups[0].get("bucket", "unknown")
        with st.expander(f"📁 Staging ({staging_count} files)", expanded=True):
            st.caption(f"Bucket: `{staging_bucket}`")
            for group in staging_groups:
                if group.get("id") == "staging":
                    sub_label = f"Active uploads ({group.get('file_count', 0)})"
                else:
                    sub_label = f"Archived ({group.get('file_count', 0)})"
                if group.get("error"):
                    st.error(f"Could not list {sub_label}: {group.get('error')}")
                with st.expander(sub_label, expanded=group.get("id") == "staging"):
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
        st.subheader("File Manager")
        st.markdown("Move staged uploads into their business domain bucket before indexing.")

        domains_result = get_doc_domains()
        status_result = get_document_status()

        if domains_result and "error" not in domains_result:
            domains = domains_result.get("domains", [])
            staging = domains_result.get("staging", {})
            st.caption(f"Staging bucket: `{staging.get('bucket', 'unknown')}`")
        else:
            domains = []
            st.error("Could not load domain configuration.")
            if domains_result:
                st.json(domains_result)

        st.markdown("### Storage explorer")
        with st.spinner("Loading bucket contents..."):
            browse_result = get_doc_browse()

        if browse_result and "error" not in browse_result:
            _render_storage_explorer_tree(browse_result)
        else:
            st.error("Could not load storage explorer.")
            if browse_result:
                st.json(browse_result)

        st.markdown("---")
        st.markdown("### Move staged documents")

        if status_result and "error" not in status_result:
            documents = status_result.get("documents", [])
            staged_docs = [
                doc for doc in documents
                if not doc.get("domain")
                and doc.get("indexed_status") in ["staged", "pending", "failed"]
                and str(doc.get("storage_uri", "")).startswith("gs://")
            ]

            if not staged_docs:
                st.info("No staged documents waiting for classification.")
            elif not domains:
                st.warning("No target domains are configured.")
            else:
                domain_labels = {
                    domain["display_name"]: domain["domain"]
                    for domain in domains
                }
                for doc in staged_docs:
                    with st.expander(f"📄 {doc.get('filename')} (ID: {doc.get('id')})"):
                        st.markdown(f"**Current URI:** `{doc.get('storage_uri')}`")
                        if doc.get("last_error"):
                            st.error(doc.get("last_error"))
                        selected_label = st.selectbox(
                            "Target domain",
                            list(domain_labels.keys()),
                            key=f"domain_select_{doc.get('id')}"
                        )
                        archive_staging = st.checkbox(
                            "Archive staging copy after move",
                            value=True,
                            key=f"archive_{doc.get('id')}"
                        )
                        target_domain = domain_labels[selected_label]
                        domain_config = next(
                            (domain for domain in domains if domain["domain"] == target_domain),
                            {}
                        )
                        if not domain_config.get("data_store_id"):
                            st.warning("This domain is missing a Data Store ID; move will fail until GCP search assets are provisioned.")
                        if st.button("Move to domain", type="primary", key=f"move_{doc.get('id')}"):
                            with st.spinner("Moving document and queueing indexing..."):
                                result = move_document(doc.get("id"), target_domain, archive_staging)
                                if result and "error" not in result:
                                    request_id = result.get("request_id")
                                    if request_id:
                                        st.session_state.last_request_ids["move"] = request_id
                                    if result.get("indexing_error"):
                                        st.warning(result.get("message", "Document moved; indexing needs retry."))
                                    else:
                                        st.success("Document moved and indexing queued.")
                                    st.rerun()
                                else:
                                    st.error("Document move failed.")
                                    if result:
                                        st.json(result)
        else:
            st.error("Could not load document status.")
            if status_result:
                st.json(status_result)

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
