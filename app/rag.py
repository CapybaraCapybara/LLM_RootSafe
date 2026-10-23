import json
import logging
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

def fallback_keyword_search(query: str, top_k: int = 3, min_score: float = 0.35) -> List[Dict[str, Any]]:
    """Deterministic token-overlap search fallback if ChromaDB is unavailable."""
    trees = load_trees_catalog()
    query_tokens = set(query.lower().split())
    scored_results = []
    
    for tree in trees:
        doc_text = build_tree_document(tree).lower()
        # Direct name match gets high score
        score = 0.0
        if tree["name_th"].lower() in query.lower() or tree["name_en"].lower() in query.lower():
            score += 0.8
        
        matches = sum(1 for token in query_tokens if token in doc_text)
        score += min(0.6, matches * 0.15)
        
        normalized_score = min(1.0, round(score, 3))
        if normalized_score >= min_score:
            scored_results.append({
                "id": tree["id"],
                "content": build_tree_document(tree),
                "score": normalized_score,
                "citation": f"[Doc: {tree['name_th']}]",
                "metadata": tree
            })
            
    scored_results.sort(key=lambda x: x["score"], reverse=True)
    return scored_results[:top_k]

def retrieve_tree_docs(query: str, min_score: Optional[float] = None, top_k: int = 3) -> List[Dict[str, Any]]:
    """Retrieve grounded arboriculture documents filtered by min_score threshold."""
    threshold = min_score if min_score is not None else DEFAULT_MIN_SCORE
    collection = init_chroma_db()
    
    if collection is None:
        return fallback_keyword_search(query, top_k=top_k, min_score=threshold)
        
    try:
        results = collection.query(
            query_texts=[query],
            n_results=top_k * 2
        )
        
        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        
        scored_docs = []
        for doc, meta, dist in zip(docs, metadatas, distances):
            # For cosine distance: similarity = 1.0 - (dist / 2.0) or 1.0 - dist
            # When distance is cosine, dist is typically between 0.0 and 2.0
            similarity = max(0.0, min(1.0, 1.0 - (dist / 2.0)))
            if similarity >= threshold:
                scored_docs.append({
                    "content": doc,
                    "score": round(similarity, 3),
                    "citation": f"[Doc: {meta.get('name_th', 'Tree')}]",
                    "metadata": meta
                })
                
        # Sort and take top_k
        scored_docs.sort(key=lambda x: x["score"], reverse=True)
        return scored_docs[:top_k]
    except Exception as e:
        logger.error(f"Error querying ChromaDB: {e}. Falling back to in-memory search.")
        return fallback_keyword_search(query, top_k=top_k, min_score=threshold)
