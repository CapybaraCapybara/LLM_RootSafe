import json
import logging
from typing import Dict, Any, List
from app.models import RootHazardArgs, TreeFilterArgs, TreeKnowledgeArgs
from app.rag import load_trees_catalog, retrieve_tree_docs

logger = logging.getLogger("rootsafe.tools")

ALLOWED_TOOLS = {
    "evaluate_root_hazard",
    "search_trees_by_criteria",
    "search_tree_knowledge"
}

ROOT_TYPE_THAI = {
    "aggressive_surface": "รากลอยผิวดินที่แผ่ขยายรุนแรง (Aggressive Surface Roots)",
    "deep_taproot": "รากแก้วแนวดิ่ง (Deep Taproot)",
    "fibrous": "รากฝอยไม่ทำลายโครงสร้าง (Fibrous Roots)",
    "moderate_lateral": "รากแขนงแผ่ปานกลาง (Moderate Lateral Roots)",
}

def find_tree_in_catalog(tree_name: str) -> Dict[str, Any] | None:
    trees = load_trees_catalog()
    query = tree_name.strip().lower()
    
    # Exact or substring match in Thai / English / Scientific name
    for tree in trees:
        if (
            query == tree["name_th"].lower()
            or query == tree["name_en"].lower()
            or query in tree["name_th"].lower()
            or query in tree["name_en"].lower()
        ):
            return tree
            
    # Substring in Thai name (e.g. 'หูกระจง' in 'ต้นหูกระจง')
    for tree in trees:
        if tree["name_th"].lower() in query:
            return tree
            
    return None

def evaluate_root_hazard(args: RootHazardArgs) -> Dict[str, Any]:
    """Calculate structural hazard index and setback clearance."""
    tree = find_tree_in_catalog(args.tree_name)
    
    if not tree:
        # Default safety conservative estimation for unknown tree
        return {
            "status": "warning",
            "verdict": "WARNING",
            "tree_name": args.tree_name,
            "hazard_score": 6,
            "safe_setback_meters": 4.0,
            "explanation": f"ไม่พบข้อมูลเฉพาะของ '{args.tree_name}' ในคลังรุกขกรรม แนะนำเว้นระยะห่างมาตรฐานความปลอดภัย 4.0 เมตรจากโครงสร้าง",
            "recommended_substitutes": ["โมก", "แก้ว", "ลีลาวดี"],
            "citation": "[Doc: General Arboriculture Standard]"
        }
    
    # Determine critical safe distance based on structure type
    if args.structure_type in ["house_foundation", "pipe"]:
        safe_dist = tree["min_foundation_distance_m"]
        structure_label = "ฐานรากบ้าน/ท่อประปา"
    else:  # fence, sidewalk
        safe_dist = tree["min_fence_distance_m"]
        structure_label = "แนวกำแพงรั้ว/ทางเท้า"
        
    actual_dist = args.distance_meters
    root_score = tree["root_aggressiveness_score"]
    
    # Clearance ratio
    clearance_ratio = actual_dist / safe_dist
    
    # Decision Matrix
    root_type_label = ROOT_TYPE_THAI.get(tree.get("root_type", ""), tree.get("root_type", ""))
    if clearance_ratio < 0.8:
        if root_score >= 6:
            verdict = "PROHIBITED"
            hazard_score = min(10, root_score + 2)
            action = f"ห้ามปลูกเด็ดขาด! {tree['name_th']} มีระบบรากแบบ{root_type_label} มีแรงดันรากสูงมาก (คะแนน {root_score}/10) เสี่ยงทำลาย {structure_label} แตกร้าวอย่างถาวร"
        else:
            verdict = "WARNING"
            hazard_score = 6
            action = f"ระยะค่อนข้างประชิดเกินไป ({actual_dist} ม. เทียบกับเกณฑ์ปลอดภัย {safe_dist} ม.) อาจทำให้โครงสร้างขยับหรือแตกร้าวได้"
    elif clearance_ratio < 1.0:
        verdict = "WARNING"
        hazard_score = 5
        action = f"ระยะห่างปานกลาง ({actual_dist} ม. ใกล้เคียงเกณฑ์ขั้นต่ำ {safe_dist} ม.) หากต้องการปลูกควรติดตั้งแผ่นกั้นราก (Root Barrier) ลึก 80-120 ซม."
    else:
        verdict = "SAFE"
        hazard_score = max(1, root_score - 3)
        action = f"ระยะปลอดภัยผ่านเกณฑ์ ({actual_dist} ม. มากกว่าระยะปลอดภัยขั้นต่ำ {safe_dist} ม.) ปลูกได้อย่างปลอดภัย"
        
    return {
        "verdict": verdict,
        "tree_name": tree["name_th"],
        "scientific_name": tree["scientific_name"],
        "hazard_score": hazard_score,
        "actual_distance_m": actual_dist,
        "safe_setback_meters": safe_dist,
        "structure_evaluated": structure_label,
        "root_type": tree["root_type"],
        "explanation": action,
        "root_behavior": tree["root_risk_description"],
        "neighbor_impact": tree.get("legal_neighbor_risk", "ระวังกิ่งก้านและระบบรากแผ่ขยาย"),
        "legal_neighbor_risk": tree.get("legal_neighbor_risk", "ระวังกิ่งก้านและระบบรากแผ่ขยาย"),
        "citations": [f"[Doc: {tree['name_th']}]"]
    }

def search_trees_by_criteria(args: TreeFilterArgs) -> Dict[str, Any]:
    """Filter safe and fitting landscape trees from catalog."""
    trees = load_trees_catalog()
    matched = []
    
    for tree in trees:
        # Filter sunlight
        if args.sunlight and tree["sunlight"] != args.sunlight and tree["sunlight"] != "full_sun":
            continue
            
        # Filter max space
        if args.max_space_meters is not None:
            # If space is narrow, reject high aggressiveness trees
            if args.max_space_meters < 3.0 and tree["root_aggressiveness_score"] >= 6:
                continue
            if tree["min_fence_distance_m"] > args.max_space_meters:
                continue
                
        # Filter pet toxicity
        if args.pet_safe_only and tree["pet_toxic"]:
            continue
            
        # Filter maintenance
        if args.maintenance_level and tree["maintenance_level"] != args.maintenance_level:
            continue
            
        matched.append({
            "name_th": tree["name_th"],
            "name_en": tree["name_en"],
            "root_type": tree["root_type"],
            "safe_fence_m": tree["min_fence_distance_m"],
            "safe_foundation_m": tree["min_foundation_distance_m"],
            "pet_toxic": tree["pet_toxic"],
            "leaf_shedding": tree["leaf_shedding"],
            "architectural_use": tree["architectural_use"]
        })
        
    # Sort matched trees by safety (lowest aggressiveness first)
    return {
        "total_matched": len(matched),
        "trees": matched[:8],
        "citations": [f"[Doc: {t['name_th']}]" for t in matched[:4]]
    }

def search_tree_knowledge(args: TreeKnowledgeArgs) -> Dict[str, Any]:
    """Retrieve grounded knowledge snippets with citations."""
    docs = retrieve_tree_docs(query=args.query, top_k=args.top_k)
    return {
        "results_count": len(docs),
        "documents": [
            {
                "citation": d["citation"],
                "score": d["score"],
                "snippet": d["content"]
            }
            for d in docs
        ]
    }

def dispatch_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Safe tool dispatcher with strict allow-listing and Pydantic validation."""
    if tool_name not in ALLOWED_TOOLS:
        return {"error": f"Tool '{tool_name}' is not in the allowed tools list."}
        
    try:
        if tool_name == "evaluate_root_hazard":
            parsed_args = RootHazardArgs(**arguments)
            return evaluate_root_hazard(parsed_args)
        elif tool_name == "search_trees_by_criteria":
            parsed_args = TreeFilterArgs(**arguments)
            return search_trees_by_criteria(parsed_args)
        elif tool_name == "search_tree_knowledge":
            parsed_args = TreeKnowledgeArgs(**arguments)
            return search_tree_knowledge(parsed_args)
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}")
        return {"error": f"Invalid arguments for tool '{tool_name}': {str(e)}"}
        
    return {"error": "Unhandled tool execution"}
