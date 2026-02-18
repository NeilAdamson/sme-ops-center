"""
SME Ops-Center Frontend
Operational AI Demo-in-a-Box
"""
import streamlit as st
from utils import upload_document, get_document_status, query_documents, get_storage_config, API_BASE_URL
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
    tab1, tab2, tab3 = st.tabs(["📤 Upload", "📊 Status", "🔍 Query"])
    
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
                                
                                if doc.get('datastore_ref'):
                                    st.markdown(f"**Datastore Ref:** `{doc.get('datastore_ref')}`")
                else:
                    st.info("📭 No documents uploaded yet. Use the Upload tab to add documents.")
                    if request_id:
                        st.caption(f"Request ID: `{request_id}`")
            else:
                error_msg = result.get("error", "Unknown error") if result else "No response from server"
                st.error(f"❌ Failed to retrieve document status: {error_msg}")
                if result:
                    st.json(result)
    
    with tab3:
        st.subheader("Query Documents")
        st.markdown("Ask questions about your uploaded documents.")
        
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
                    result = query_documents(query_text.strip())
                    
                    if result and "error" not in result:
                        request_id = result.get("request_id")
                        # Store request_id for trust surface
                        if request_id:
                            st.session_state.last_request_ids["query"] = request_id
                        
                        answer = result.get("answer", "")
                        citations = result.get("citations", [])
                        
                        st.markdown("### Response")
                        st.caption(f"Request ID: `{request_id}`")
                        
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
