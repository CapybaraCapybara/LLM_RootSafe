import json
import logging
import re
from typing import List, Dict, Any, Optional
from app.config import DATA_PATH, CHROMA_PERSIST_DIR, DEFAULT_MIN_SCORE

logger = logging.getLogger("rootsafe.rag")

# In-memory tree catalog cache
_TREES_CATALOG: List[Dict[str, Any]] = []
_CHROMA_COLLECTION = None

def load_trees_catalog() -> List[Dict[str, Any]]:
    global _TREES_CATALOG
    if not _TREES_CATALOG:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            _TREES_CATALOG = json.load(f)
    return _TREES_CATALOG

def build_tree_document(tree: Dict[str, Any]) -> str:
    pet_status = "เป็นพิษต่อสัตว์เลี้ยง (ห้ามสุนัข/แมวกัดแทะ)" if tree.get("pet_toxic") else "ปลอดภัยต่อสัตว์เลี้ยง"
    return (
        f"ชื่อพรรณไม้: {tree['name_th']} ({tree['name_en']}) ชื่อวิทยาศาสตร์: {tree['scientific_name']}\n"
        f"ระบบราก: {tree['root_type']} | คะแนนความเสี่ยงระบบราก: {tree['root_aggressiveness_score']}/10\n"
        f"ระยะปลอดภัยขั้นต่ำ: ฐานราก/ตัวบ้าน {tree['min_foundation_distance_m']} เมตร | กำแพงรั้ว {tree['min_fence_distance_m']} เมตร\n"
        f"ขนาดลำต้น: สูงสูงสุด {tree['max_height_m']} เมตร | รัศมีทรงพุ่ม {tree['canopy_spread_m']} เมตร\n"
        f"แสงแดด: {tree['sunlight']} | การผลัดใบ: {tree['leaf_shedding']} | ความเป็นพิษ: {pet_status}\n"
        f"การดูแลรักษา: {tree['maintenance_level']} | การใช้งาน: {tree['architectural_use']}\n"
        f"พฤติกรรมและความเสี่ยงของระบบราก: {tree['root_risk_description']}\n"
        f"ข้อควรระวังต่อพื้นที่ข้างเคียง (กิ่ง/ใบ/ราก): {tree['legal_neighbor_risk']}\n"
        f"การปลูกและสภาพดิน: {tree['care_and_soil']}"
    )

def init_chroma_db():
    global _CHROMA_COLLECTION
    if _CHROMA_COLLECTION is not None:
        return _CHROMA_COLLECTION
    
    trees = load_trees_catalog()
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        collection = client.get_or_create_collection(
            name="rootsafe_trees",
            metadata={"hnsw:space": "cosine"}
        )
        
        # Check if already populated
        if collection.count() < len(trees):
            ids = [t["id"] for t in trees]
            documents = [build_tree_document(t) for t in trees]
            metadatas = [
                {
                    "name_th": t["name_th"],
                    "name_en": t["name_en"],
                    "root_type": t["root_type"],
                    "root_score": t["root_aggressiveness_score"],
                    "safe_foundation_m": t["min_foundation_distance_m"],
                    "safe_fence_m": t["min_fence_distance_m"],
                    "pet_toxic": t["pet_toxic"],
                }
                for t in trees
            ]
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        _CHROMA_COLLECTION = collection
        logger.info(f"ChromaDB initialized with {collection.count()} tree documents.")
        return _CHROMA_COLLECTION
    except Exception as e:
        logger.warning(f"Could not initialize ChromaDB ({e}). Will use fallback in-memory search.")
        return None

def clean_tree_aliases(name_th: str, name_en: str) -> List[str]:
    cleaned = re.sub(r"\((?:ลงดิน|ในกระบะคอนกรีต|ปลูกในกระถาง[^\)]*|ไม้เลื้อยซุ้ม)\)", "", name_th)
    clean_parts = cleaned.replace("(", "/").replace(")", "/").replace("（", "/").replace("）", "/")
    aliases = [p.strip() for p in clean_parts.split("/") if len(p.strip()) > 1]
    if name_en:
        aliases.append(name_en.strip())
    return aliases

def score_tree_match(tree: Dict[str, Any], query: str, vec_dist: Optional[float] = None) -> float:
    query_lower = query.lower()
    query_tokens = set(query_lower.split())
    doc_text = build_tree_document(tree).lower()
    
    name_th = tree["name_th"].lower()
    name_en = tree["name_en"].lower()
    primary_name = name_th.split("/")[0].split("(")[0].strip()
    aliases = clean_tree_aliases(name_th, name_en)
    
    vec_sim = max(0.0, min(1.0, 1.0 - (vec_dist / 2.0))) if vec_dist is not None else 0.5
    
    if primary_name in query_lower:
        score = 0.70 + 0.15 * vec_sim
    elif any(alias in query_lower for alias in aliases if len(alias) > 2):
        score = 0.50 + 0.10 * vec_sim
    else:
        matches = sum(1 for tok in query_tokens if tok in doc_text and len(tok) > 2)
        score = min(0.30, 0.10 * vec_sim + matches * 0.05)
        
    return min(1.0, round(score, 3))

def fallback_keyword_search(query: str, top_k: int = 3, min_score: float = 0.35) -> List[Dict[str, Any]]:
    """Deterministic token-overlap search fallback if ChromaDB is unavailable."""
    trees = load_trees_catalog()
    scored_results = []
    
    for tree in trees:
        score = score_tree_match(tree, query, vec_dist=None)
        if score >= min_score:
            scored_results.append({
                "id": tree["id"],
                "content": build_tree_document(tree),
                "score": score,
                "citation": f"[Doc: {tree['name_th']}]",
                "metadata": tree
            })
            
    scored_results.sort(key=lambda x: x["score"], reverse=True)
    return scored_results[:top_k]

def retrieve_tree_docs(query: str, min_score: Optional[float] = None, top_k: int = 3) -> List[Dict[str, Any]]:
    """Retrieve grounded arboriculture documents filtered by min_score threshold."""
    threshold = min_score if min_score is not None else DEFAULT_MIN_SCORE
    trees = load_trees_catalog()
    collection = init_chroma_db()
    
    vec_dists = {}
    if collection is not None:
        try:
            results = collection.query(
                query_texts=[query],
                n_results=len(trees)
            )
            if results and results.get("ids") and results.get("distances"):
                for tid, dist in zip(results["ids"][0], results["distances"][0]):
                    vec_dists[tid] = dist
        except Exception as e:
            logger.error(f"Error querying ChromaDB: {e}. Falling back to keyword search.")
            return fallback_keyword_search(query, top_k=top_k, min_score=threshold)
            
    scored_docs = []
    for tree in trees:
        dist = vec_dists.get(tree["id"])
        similarity = score_tree_match(tree, query, vec_dist=dist)
        if similarity >= threshold:
            scored_docs.append({
                "id": tree["id"],
                "content": build_tree_document(tree),
                "score": similarity,
                "citation": f"[Doc: {tree['name_th']}]",
                "metadata": tree
            })
            
    scored_docs.sort(key=lambda x: x["score"], reverse=True)
    return scored_docs[:top_k]
