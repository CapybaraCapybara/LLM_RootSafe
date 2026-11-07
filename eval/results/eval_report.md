# RootSafe Arborist — Evaluation Report

Generated: 2026-11-07 15:32:10
Model: `gemma-4-E4B-it` | Test Set: `30` hand-labelled examples

## 1. Executive Summary Table

| Metric | Baseline (Naive LLM) | RootSafe Agent (Ours) | Measured Improvement |
| :--- | :---: | :---: | :---: |
| **Hazard Avoidance Rate** (Dangerous Cases) | **0.0%** | **100.0%** | **+100.0%** |
| **Overall Verdict Accuracy** | **36.67%** | **76.67%** | **+40.0%** |
| **Citation Grounding Rate** | **0.0%** | **100.0%** | **+100.0%** |

## 2. RAG Ablation Study (`min_score` Threshold)

Demonstrating the effect of tuning the similarity score floor on Precision@3, Recall@3, and F1@3:

| `min_score` Threshold | Precision@3 | Recall@3 | F1@3 Score | Characteristic & Analysis |
| :---: | :---: | :---: | :---: | :--- |
| `0.0` (No threshold) | 33.3% | 100.0% | **50.0%** | Too noisy (retrieves irrelevant trees without filtering, low precision) |
| **`0.35` (Tuned)** | **100.0%** | **100.0%** | **100.0%** | **Optimal balance (clear signal, filters noise, 100% precision & recall)** |
| `0.70` (Too aggressive) | 100.0% | 60.0% | **75.0%** | Too strict (over-filters alias queries, recall drops to 60.0%) |

## 3. Analysis & Honest Failure Cases
- **Success Case**: When asked to plant *หูกระจง* 1.2m from a wall, the Naive LLM approved it because of shade benefits, whereas RootSafe Agent called `evaluate_root_hazard`, identified root aggressiveness (10/10), and issued a strict `PROHIBITED` verdict.
- **Honest Failure Case**: For ambiguous tree varieties or hybrid species not explicitly covered in the catalog, the agent defaulted to a generic conservative setback (4.0m) rather than an exact botanical setback.
