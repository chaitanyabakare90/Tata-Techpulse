"""
benchmark_rag.py - Automated benchmark for RAG evaluation metrics
Tests:
1. Retrieval Hit Rate: Does FAISS retrieve chunks from the ground-truth page?
2. Citation Accuracy: Does the generated answer cite the correct page?
3. Answer Relevance / Faithfulness: Does the answer contain the expected technical entity without hallucination?
4. Refusal Accuracy: Are unsupported/out-of-scope questions correctly refused?
5. Response Latency: Measured in seconds per query (retrieval + generation).
"""
import time
import json
from app import create_app
from database.models import db, Document
from services.pdf_service import PDFService

# Ground-truth test dataset for Sample_AUTOSAR_Powertrain_HLD.pdf
GROUND_TRUTH_TESTS = [
    {
        "type": "supported",
        "question": "What AUTOSAR release version is this powertrain specification based on?",
        "expected_page": 1,
        "expected_keywords": ["4.4.0", "Classic Platform", "4.4"],
    },
    {
        "type": "supported",
        "question": "What is the purpose of TorqueArbitration_SWC and which inputs does it arbitrate?",
        "expected_page": 2,
        "expected_keywords": ["TorqueArbitration_SWC", "AcceleratorPedal", "CruiseControl", "arbitrat"],
    },
    {
        "type": "supported",
        "question": "What interfaces and ports are defined on BatteryThermalMonitor_SWC?",
        "expected_page": 2,
        "expected_keywords": ["BatteryThermalMonitor_SWC", "R_BatteryTempSensor", "P_ThermalDeratingFactor"],
    },
    {
        "type": "supported",
        "question": "What is the data type and direction of signal Sig_DriverTorqueDemand?",
        "expected_page": 3,
        "expected_keywords": ["float32", "Inward"],
    },
    {
        "type": "supported",
        "question": "What communication type does If_DiagnosticsService use?",
        "expected_page": 3,
        "expected_keywords": ["ClientServer", "Dem", "Diagnostic"],
    },
    {
        "type": "supported",
        "question": "Describe Step 1 and Step 2 of the Torque Delivery Sequence Flow.",
        "expected_page": 4,
        "expected_keywords": ["AcceleratorPedal_Sensor", "RTE", "R_AccelPedalPos"],
    },
    {
        "type": "supported",
        "question": "What interface is missing between StabilityControl_SWC and TorqueArbitration_SWC?",
        "expected_page": 4,
        "expected_keywords": ["R_ESP_Intervention", "StabilityControl_SWC"],
    },
    {
        "type": "supported",
        "question": "Which microcontroller hardware unit does InverterMotorControl_SWC use for PWM gating?",
        "expected_page": 2,
        "expected_keywords": ["hardware timer", "timer", "PWM"],
    },
    # Unsupported / Out-of-Scope questions (Testing Refusal Accuracy)
    {
        "type": "unsupported",
        "question": "What is the maximum torque output of the electric motor in Nm and RPM limit?",
        "refusal_keywords": ["not found", "not specified", "not provided", "does not contain", "not mentioned"],
    },
    {
        "type": "unsupported",
        "question": "What is the baud rate of the FlexRay communication channel for the brake steer system?",
        "refusal_keywords": ["not found", "not specified", "not provided", "does not contain", "not mentioned", "not in"],
    },
    {
        "type": "unsupported",
        "question": "Who is the lead supplier for the battery cells and what is their chemistry type NMC or LFP?",
        "refusal_keywords": ["not found", "not specified", "not provided", "does not contain", "not mentioned"],
    },
]

def run_benchmark():
    app = create_app()
    with app.app_context():
        # Find or upload the sample PDF
        doc = Document.query.filter_by(original_name="Sample_AUTOSAR_Powertrain_HLD.pdf").first()
        if not doc or doc.status != "analyzed":
            print("Uploading and analyzing Sample_AUTOSAR_Powertrain_HLD.pdf first...")
            from werkzeug.utils import secure_filename
            import uuid
            from pathlib import Path
            
            src = "Sample_AUTOSAR_Powertrain_HLD.pdf"
            if not Path(src).exists():
                from create_sample_pdf import create_sample_hld_pdf
                create_sample_hld_pdf()
            
            unique_name = f"{uuid.uuid4().hex}.pdf"
            save_path = app.config["UPLOAD_FOLDER"] / unique_name
            with open(src, "rb") as f_in, open(save_path, "wb") as f_out:
                f_out.write(f_in.read())
            
            doc = Document(
                filename=unique_name,
                original_name="Sample_AUTOSAR_Powertrain_HLD.pdf",
                file_path=str(save_path),
                file_size=save_path.stat().st_size,
                page_count=PDFService.get_page_count(str(save_path)),
                status="uploaded",
            )
            db.session.add(doc)
            db.session.commit()
            
            svc = app.extensions["analysis_service"]
            svc.process_document(doc.id)
            doc = db.session.get(Document, doc.id)
            print(f"Sample PDF analyzed. Doc ID: {doc.id}")

        rag = app.extensions["rag_service"]
        gemini = app.extensions["gemini_service"]
        svc = app.extensions["analysis_service"]

        print(f"\n=======================================================")
        print(f"RUNNING RAG EVALUATION BENCHMARK ON DOC #{doc.id}")
        print(f"Document: {doc.original_name} ({doc.page_count} pages)")
        print(f"Total Test Cases: {len(GROUND_TRUTH_TESTS)}")
        print(f"=======================================================\n")

        retrieval_hits = 0
        supported_count = 0
        citation_hits = 0
        relevance_hits = 0
        refusal_hits = 0
        unsupported_count = 0
        latencies = []

        for i, t in enumerate(GROUND_TRUTH_TESTS, 1):
            q = t["question"]
            start_time = time.time()
            
            # 1. Measure Retrieval Hit Rate
            query_emb = gemini.embed_query(q)
            chunks = rag.search(doc.id, query_emb, top_k=5)
            retrieved_pages = [c["page"] for c in chunks]
            
            # 2. Get Answer
            chat_result = gemini.answer_question(q, chunks)
            elapsed = time.time() - start_time
            latencies.append(elapsed)
            
            answer = chat_result.get("answer", "")
            source_pages = chat_result.get("source_pages", [])

            print(f"[{i}/{len(GROUND_TRUTH_TESTS)}] {t['type'].upper()}: {q[:55]}...")
            print(f"   ⏱ Latency: {elapsed:.2f}s | Retrieved Pages: {retrieved_pages} | Cited: {source_pages}")

            if t["type"] == "supported":
                supported_count += 1
                exp_page = t["expected_page"]
                # Check retrieval
                hit_retrieval = exp_page in retrieved_pages
                if hit_retrieval:
                    retrieval_hits += 1
                
                # Check citation
                hit_citation = exp_page in source_pages
                if hit_citation:
                    citation_hits += 1

                # Check relevance
                hit_relevance = any(k.lower() in answer.lower() for k in t["expected_keywords"])
                if hit_relevance:
                    relevance_hits += 1

                print(f"   Retrieval: {'PASS' if hit_retrieval else 'FAIL'} | Citation: {'PASS' if hit_citation else 'FAIL'} | Relevance: {'PASS' if hit_relevance else 'FAIL'}")

            else:
                unsupported_count += 1
                # Check refusal accuracy
                hit_refusal = any(k.lower() in answer.lower() for k in t["refusal_keywords"])
                if hit_refusal:
                    refusal_hits += 1
                print(f"   Refusal: {'PASS' if hit_refusal else 'FAIL'}")

            print("-" * 55)

        avg_latency = sum(latencies) / len(latencies) if latencies else 0

        print("\n================== BENCHMARK RESULTS ==================")
        print(f"Retrieval Hit Rate:              {retrieval_hits}/{supported_count} ({retrieval_hits/supported_count*100:.1f}%)")
        print(f"Citation Accuracy:               {citation_hits}/{supported_count} ({citation_hits/supported_count*100:.1f}%)")
        print(f"Answer Relevance / Faithfulness: {relevance_hits}/{supported_count} ({relevance_hits/supported_count*100:.1f}%)")
        print(f"Refusal Accuracy:                {refusal_hits}/{unsupported_count} ({refusal_hits/unsupported_count*100:.1f}%)")
        print(f"Response Latency (Average):      {avg_latency:.2f} seconds")
        print("=======================================================")

if __name__ == "__main__":
    run_benchmark()
