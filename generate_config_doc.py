"""
generate_config_doc.py
Generates the exact 'Model, Prompts & Configuration' PDF documentation
matching our AUTOSAR HLD project setup and the reference document format.
"""
import pymupdf

def create_config_pdf(output_filename="Model_Prompts_Configuration.pdf"):
    doc = pymupdf.open()
    
    # -------------------------------------------------------------
    # PAGE 1: Model, Prompts & Configuration
    # -------------------------------------------------------------
    p1 = doc.new_page(width=595, height=842) # A4 size in points
    
    # Header Title
    p1.insert_text(
        (150, 80),
        "Model, Prompts & Configuration",
        fontsize=18,
        fontname="times-bold"
    )
    
    body_p1 = """1. LLM Configuration
The system uses the Google Gemini API (via google-genai SDK) for generating answers and performing architectural analysis from the retrieved AUTOSAR HLD context.
1. Current Provider: Google AI Studio
2. Alternative Provider: Vertex AI
3. Model: gemini-2.5-flash
4. API Interface: Google GenAI Python SDK
5. Purpose: Generate document-grounded responses, extract AUTOSAR components, ports, interfaces, signals, and identify architectural inconsistencies.
6. API Key: Stored securely through environment variables (.env) and excluded from version control.
The LLM is called only after relevant document chunks have been retrieved from FAISS and passed through the relevance filtering stage.

2. Embedding Configuration
Embedding Framework: Google GenAI Embeddings
Embedding Model: gemini-embedding-001
The embedding model converts both document chunks and user questions into 3072-dimensional numerical vector representations. These vectors are L2-normalized and used for cosine semantic similarity search.
The model is loaded dynamically when processing uploads and user queries.

3. Vector Store / Knowledge Base
The project uses FAISS (Facebook AI Similarity Search) as a persistent vector store.
1. Vector Store: FAISS (IndexFlatIP with L2 Normalization)
2. Metadata: Python Pickle / SQLite DB
3. Storage Path: vector_store/doc_{id}.faiss
The FAISS index stores document embeddings, while metadata maintains information such as:
1. Document name & Document ID
2. Page number (exact source citation)
3. Chunk text & Chunk ID
This metadata enables the system to provide accurate, grounded document and page-level citations with every generated answer."""

    rect1 = pymupdf.Rect(54, 115, 541, 780)
    p1.insert_textbox(rect1, body_p1, fontsize=10.5, fontname="times-roman", lineheight=1.4)
    
    # -------------------------------------------------------------
    # PAGE 2: RAG Configuration, Table, Prompts & Citations
    # -------------------------------------------------------------
    p2 = doc.new_page(width=595, height=842)
    
    p2.insert_text((54, 75), "4. RAG Configuration", fontsize=12, fontname="times-bold")
    
    # Draw Table
    # Table bounds
    t_left = 54
    t_right = 541
    t_top = 95
    row_height = 24
    col_split = 260
    
    table_data = [
        ("Parameter", "Value"),
        ("Embedding Model", "gemini-embedding-001"),
        ("Top-K Retrieval", "6"),
        ("Chunk Size", "800 characters"),
        ("Chunk Overlap", "150 characters"),
        ("Vector Store", "FAISS (IndexFlatIP)"),
        ("Similarity Metric", "Cosine Similarity (Normalized IP)"),
        ("Storage Engine", "Local Vector Store + SQLite")
    ]
    
    # Draw table rows
    y = t_top
    for i, (param, val) in enumerate(table_data):
        is_header = (i == 0)
        # Background for header
        if is_header:
            p2.draw_rect(pymupdf.Rect(t_left, y, t_right, y + row_height), color=(0.7, 0.7, 0.7), fill=(0.95, 0.95, 0.95))
        else:
            p2.draw_rect(pymupdf.Rect(t_left, y, t_right, y + row_height), color=(0.6, 0.6, 0.6))
        
        # Vertical divider
        p2.draw_line(pymupdf.Point(col_split, y), pymupdf.Point(col_split, y + row_height), color=(0.6, 0.6, 0.6))
        
        # Text
        f_name = "times-bold" if is_header else "times-roman"
        p2.insert_text((t_left + 10, y + 16), param, fontsize=10, fontname=f_name)
        p2.insert_text((col_split + 10, y + 16), val, fontsize=10, fontname=f_name)
        
        y += row_height
    
    # Section 5: RAG Prompt
    body_p2 = """5. RAG System Prompt
You are an AUTOSAR HLD document analysis assistant.
Answer questions ONLY based on the provided document context.
If the answer is not in the context, say so clearly.
Always cite the page numbers where information was found.
Be precise and technical.

If the provided context does not contain sufficient information to answer the question, respond:
"This information is not found in the provided document sections."

Keep the response concise, technically rigorous, and grounded strictly in the retrieved AUTOSAR HLD document context.

6. Citation Configuration
Citations are generated dynamically from the page metadata associated with the retrieved FAISS chunks.
The system provides: Document name, Specific Page Number(s)
Only sources associated with the top-ranked relevant chunks are cited. Redundant citations from multiple chunks on the identical page are automatically deduplicated.
This guarantees that all displayed source tags strictly correspond to the technical sections used to formulate the engineering response."""

    rect2 = pymupdf.Rect(54, y + 25, 541, 800)
    p2.insert_textbox(rect2, body_p2, fontsize=10.5, fontname="times-roman", lineheight=1.4)

    # -------------------------------------------------------------
    # PAGE 3: Environment Configuration
    # -------------------------------------------------------------
    p3 = doc.new_page(width=595, height=842)
    
    p3.insert_text((54, 75), "7. Environment Configuration", fontsize=12, fontname="times-bold")
    
    env_content = """# Google Gemini API Credentials
GEMINI_API_KEY=YOUR_GEMINI_API_KEY_HERE
GEMINI_MODEL=gemini-2.5-flash
GEMINI_EMBED_MODEL=gemini-embedding-001

# Flask Application Settings
SECRET_KEY=autosar-secure-key-2026
FLASK_DEBUG=false

# Vector Store and Storage Paths
FAISS_INDEX_DIR=vector_store/
UPLOAD_FOLDER=static/uploads/
SQLALCHEMY_DATABASE_URI=sqlite:///autosar_hld.db

# RAG & Chunking Parameters
TOP_K=6
CHUNK_SIZE=800
CHUNK_OVERLAP=150
MAX_CONTENT_LENGTH=52428800  # 50 MB Max PDF Size"""

    rect3 = pymupdf.Rect(54, 100, 541, 400)
    p3.insert_textbox(rect3, env_content, fontsize=10.5, fontname="courier", lineheight=1.5)

    doc.save(output_filename)
    doc.close()
    print(f"Successfully generated: {output_filename}")

if __name__ == "__main__":
    create_config_pdf()
