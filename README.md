# 🌳 RootSafe Arborist

> **Capstone Project — End-to-End LLM Application**  
> An Agentic LLM System for Residential Landscape Tree Selection, Root Hazard Prevention & Setback Calculation.  
> Powered by `gemma-4-E4B-it` via Class Proxy, ChromaDB RAG, and Deterministic Arboricultural Tools.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com)
[![Model](https://img.shields.io/badge/Model-gemma--4--E4B--it-orange.svg)](https://openai.com)
[![Evaluation](https://img.shields.io/badge/Eval-30%20Gold%20Cases-emerald.svg)](eval/test_set.json)

---

## 📌 Problem & Motivation

เจ้าของบ้าน สถาปนิก และนักจัดสวนในประเทศไทย มักประสบปัญหา **"ปลูกต้นไม้ผิด ชีวิตเปลี่ยน"** เช่น:
1. ปลูกต้นไม้ที่มี **ระบบรากชอนไชก้าวร้าว (Aggressive surface roots)** เช่น *หูกระจง, ไทร, พญาสัตบรรณ (ตีนเป็ด), แคนา* ชิดตัวบ้านหรือกำแพงรั้ว ทำให้คานคอดิน ฐานราก ท่อระบายน้ำ และรั้วแตกร้าวทรุดตัว
2. ข้อพิพาททางกฎหมายกับเพื่อนบ้านตาม **ป.พ.พ. มาตรา 1347** เรื่องรากไม้และกิ่งไม้รุกล้ำ หรือผลัดใบร่วงอุดตันท่อระบายน้ำ

เมื่อถาม LLM ทั่วไป (Naive LLM) โมเดลมักจะตอบเอาใจผู้ใช้ เช่น แนะนำให้ปลูกหูกระจงเพราะ "ให้ร่มเงาสวยงาม" โดยละเลยสูตรคำนวณระยะร่นและความปลอดภัยของโครงสร้าง

**RootSafe Arborist** แก้ปัญหานี้ด้วย **Agentic Tool Calling** ผสาน **Vector RAG** เพื่อคำนวณระยะปลอดภัยทางคณิตศาสตร์และอ้างอิงเอกสารรุกขกรรมอย่างเคร่งครัด

---

## 🎯 Course Capability Families Coverage

โครงการนี้ครอบคลุม **5 Capability Families** จากเนื้อหาการเรียน (เกินเกณฑ์ขั้นต่ำ 3 ด้าน):

| Capability Family | Implementation in RootSafe Arborist |
| :--- | :--- |
| **1. Structured Output & Validation** | Pydantic Schema สำหรับตรวจสอบผลประเมิน `ConsultationReport`, `RootHazardArgs`, `TreeFilterArgs` |
| **2. Retrieval / RAG (Grounded Knowledge)** | คลังพรรณไม้เมืองร้อน 42 ชนิด, Embed & Search ด้วย ChromaDB พร้อมระบุ `[Doc: ชื่อต้นไม้]` |
| **3. Agent Loop with Tools *(Agentic, บังคับ)*** | วงรอบ Agent (Max 5 iterations) ตัดสินใจเรียก Tool พร้อม Stop Condition เมื่อได้คำตอบ |
| **4. Rigorous Evaluation *(บังคับ)*** | ชุดทดสอบ 30 สถานการณ์จริง (10 Dangerous, 8 Warning, 7 Safe, 5 Knowledge) เทียบกับ Baseline |
| **5. Served Interface** | REST Backend (FastAPI) + SSE Streaming Event UI แสดงผล Tool Traces แบบสด |

---

## 🏗️ Architecture & Execution Flow

```
[User Browser (SSE Web UI)]
         │
         │  1. POST /api/chat (SSE Stream)
         ▼
[FastAPI Backend (main.py)]
         │
         │  2. Start Agent Loop (max 5 iterations)
         ▼
[RootSafe Agent (gemma-4-E4B-it)]
   ├─── Requires Hazard Calculation? ──► Tool 1: evaluate_root_hazard(args)
   ├─── Requires Species Filtering?   ──► Tool 2: search_trees_by_criteria(args)
   └─── Requires Botanical Grounding? ──► Tool 3: search_tree_knowledge(query)
                                                      │
                                                      ▼
                                            [ChromaDB Collection]
                                            (min_score floor: 0.35)
         │
         │  3. Stream tokens & tool pills via SSE
         ▼
[Pydantic Structured Output Validation]
         │
         │  4. Emit Verdict (SAFE / WARNING / PROHIBITED) + Citations
         ▼
[User Interface (Live Graphical Gauge)]
```

---

## 📊 Evaluation & Measured Improvement

ผลการทดสอบบนชุดทดสอบมาตรฐาน **30 Gold Test Cases** ([`eval/test_set.json`](eval/test_set.json)):

### 1. เปรียบเทียบกับ Baseline (Naive LLM)

| Metric | Baseline (Naive LLM) | RootSafe Agent (Ours) | Measured Improvement |
| :--- | :---: | :---: | :---: |
| **Hazard Avoidance Rate** (บล็อกต้นไม้อันตราย 10 เคส) | **30.0%** (3/10) | **100.0%** (10/10) | **+70.0%** 🚀 |
| **Overall Verdict Accuracy** (ความแม่นยำทุกเคส) | **36.67%** | **93.33%** | **+56.66%** 🚀 |
| **Citation Grounding Rate** (มีการอ้างอิงเอกสาร) | **0.0%** | **96.67%** | **+96.67%** 🚀 |

> **คำอธิบาย**: Naive LLM ล้มเหลวในการปฏิเสธต้นไม้รากอันตราย (ตอบยอมให้ปลูกหูกระจงชิดรั้ว 1.2 ม.) ในขณะที่ RootSafe Agent เรียก `evaluate_root_hazard` คำนวณอัตราส่วนระยะจริงต่อระยะปลอดภัย และสั่งห้ามปลูก (**PROHIBITED**) ได้ถูกต้อง 100%

### 2. Ablation Study: การปรับจูน `min_score` Threshold ใน RAG

| `min_score` Threshold | Relevance Score | บทวิเคราะห์ทางวิศวกรรม |
| :---: | :---: | :--- |
| `0.0` (ไม่กรอง) | 50.0% | ดึงข้อมูลต้นไม้ที่ไม่เกี่ยวข้องมาปน ทำให้โมเดลสับสน |
| **`0.35` (Tuned)** | **100.0%** | **จุดสมดุลที่ดีที่สุด** กรองเอกสารรบกวนทิ้งได้อย่างแม่นยำ |
| `0.70` (เข้มงวดเกินไป) | 60.0% | กรองทิ้งมากเกินไปจนเอกสารที่เกี่ยวข้องหลุดหาย |

---

## 🚀 Quick Start (วิธีติดตั้งและรัน)

### 1. Clone & ติดตั้ง Dependencies
```bash
git clone https://github.com/your-username/rootsafe-arborist.git
cd rootsafe-arborist

# สร้าง Virtual Environment
python -m venv .venv

# Activate บน Windows:
.venv\Scripts\activate
# บน macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
```

### 2. ตั้งค่า Environment Variables
คัดลอกไฟล์ `.env.example` เป็น `.env` และใส่ API Key:
```bash
cp .env.example .env
```
ตรวจสอบเนื้อหาในไฟล์ `.env`:
```ini
OPENAI_API_KEY="sk-your-class-proxy-key"
OPENAI_BASE_URL="BASE_URL"
MODEL="gemma-4-E4B-it"
RAG_MIN_SCORE=0.35
```

### 3. รัน Server
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
เปิดเบราว์เซอร์ไปที่: **`http://127.0.0.1:8000`** เพื่อใช้งาน Web Interface

### 4. รันชุดทดสอบ Evaluation
```bash
python eval/run_eval.py
```
สคริปต์จะทำการทดสอบทั้ง 30 ข้อ และสร้างรายงานสรุปใน `eval/results/eval_report.md`

---


## ⚖️ Honest Failure Case (บทวิเคราะห์ข้อจำกัด)

- **Success Case**: คำถาม *"มีพื้นที่ข้างบ้าน 1.2 เมตร ปลูกหูกระจงดีไหม"* — ระบบเรียกเครื่องมือตรวจพบแรงดันราก 10/10 ระยะปลอดภัยต้องไม่ต่ำกว่า 4.5 ม. จึงประเมินเป็น `PROHIBITED` พร้อมแนะพันธุ์ไม้รากฝอยทดแทน เช่น *โมก, แก้ว* ทันที
- **Honest Failure Case**: เมื่อผู้ใช้ถามถึงพันธุ์ไม้ลูกผสม (Hybrid) หรือชื่อท้องถิ่นที่ไม่ปรากฏในคลังพรรณไม้ 42 ชนิด ระบบจะยังไม่สามารถระบุระยะรากที่แท้จริงได้ และจะถอยไปใช้ค่า Conservative Setback (4.0 เมตร) เป็นค่าตั้งต้นเพื่อความปลอดภัย

---

## 📁 Repository Structure

```
rootsafe-arborist/
├── README.md               # รายละเอียดโครงการ วิธีรัน และผลการประเมิน
├── .env.example            # ตัวอย่างการตั้งค่า Environment Variables
├── .gitignore              # กำหนดไฟล์ที่ไม่ commit (.env, .chroma/, .venv/)
├── requirements.txt        # รายการ Dependencies
│
├── data/
│   └── trees.json          # คลังข้อมูลพรรณไม้ 42 ชนิด (Raw Corpus)
│
├── app/
│   ├── main.py             # FastAPI App และ Route endpoints
│   ├── config.py           # ตัวอ่านค่า Config และ OpenAI Client
│   ├── models.py           # Pydantic Schemas สำหรับ Input/Output/Tools
│   ├── prompts.py          # System Prompt และ OpenAI Tool Specs
│   ├── tools.py            # เครื่องมือคำนวณรุกขกรรมและ Dispatcher
│   ├── rag.py              # ChromaDB Vector Search พร้อม min_score
│   └── agent.py            # Agent Loop, Function Calling และ SSE Generator
│
├── static/
│   ├── index.html          # หน้าจอ Web UI
│   ├── style.css           # สไตล์ Glassmorphism Dark Emerald
│   └── app.js              # SSE Client และ Dynamic Card Renderer
│
└── eval/
    ├── test_set.json       # ชุดทดสอบมาตรฐาน 30 สถานการณ์พร้อม Ground Truth
    ├── run_eval.py         # สคริปต์รัน Benchmark และ Ablation Study
    └── results/
        ├── summary.json    # ผลลัพธ์ตัวเลขเชิงปริมาณ
        └── eval_report.md  # รายงานผลการประเมินแบบ Markdown
```
