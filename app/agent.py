import json
import logging
import re
from typing import List, Dict, Any, AsyncGenerator, Optional
from app.config import client, MODEL
from app.prompts import SYSTEM_PROMPT, TOOLS_SPEC
from app.tools import dispatch_tool
from app.models import ConsultationReport

logger = logging.getLogger("rootsafe.agent")
MAX_AGENT_ITERATIONS = 5

def extract_structured_json(text: str) -> Optional[ConsultationReport]:
    """Extract and validate ConsultationReport from assistant response."""
    # Look for ```json ... ``` code blocks first
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate_json = None
    if json_match:
        candidate_json = json_match.group(1)
    else:
        # Fallback: look for outermost curly braces
        brace_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if brace_match:
            candidate_json = brace_match.group(1)
            
    if candidate_json:
        try:
            data = json.loads(candidate_json)
            # Ensure required fields have sensible defaults if omitted by LLM
            if "verdict" not in data:
                data["verdict"] = "WARNING"
            if "hazard_score" not in data:
                data["hazard_score"] = 5
            if "summary" not in data:
                data["summary"] = text[:150]
            if "safe_setback_meters" not in data:
                data["safe_setback_meters"] = 3.0
            if "legal_neighbor_risk_notes" not in data:
                data["legal_neighbor_risk_notes"] = "ควรเว้นระยะร่นตาม ป.พ.พ. 1347"
            if "citations" not in data:
                data["citations"] = []
            return ConsultationReport(**data)
        except Exception as e:
            logger.debug(f"JSON parsing error: {e}")
            
    # Heuristic fallback if model didn't format strict JSON
    verdict = "WARNING"
    text_lower = text.lower()
    if "ห้ามปลูก" in text or "prohibited" in text_lower or "อันตราย" in text:
        verdict = "PROHIBITED"
    elif "ปลอดภัย" in text or "safe" in text_lower:
        verdict = "SAFE"
        
    citations = re.findall(r"\[Doc:\s*[^\]]+\]", text)
    return ConsultationReport(
        verdict=verdict,
        hazard_score=8 if verdict == "PROHIBITED" else (3 if verdict == "SAFE" else 6),
        summary=text[:200].replace("\n", " ") + "...",
        recommended_trees=["โมก", "แก้ว", "ลีลาวดี"] if verdict == "PROHIBITED" else [],
        safe_setback_meters=4.0 if verdict == "PROHIBITED" else 1.5,
        legal_neighbor_risk_notes="ระวังกิ่งก้านและระบบรากล้ำแนวรั้วตาม ป.พ.พ. 1347",
        citations=citations if citations else ["[Doc: General Arboriculture]"]
    )

def run_agent(
    user_message: str,
    history: Optional[List[Dict[str, Any]]] = None,
    temperature: float = 0.0,
    min_score: Optional[float] = None
) -> Dict[str, Any]:
    """Synchronous execution of agent loop for eval and testing."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Append history
    if history:
        for msg in history[-6:]:  # Keep recent context
            role = msg.get("role")
            content = msg.get("content", "")
            if role in ["user", "assistant"]:
                messages.append({"role": role, "content": content})
                
    messages.append({"role": "user", "content": user_message})
    
    tool_trace = []
    
    for iteration in range(MAX_AGENT_ITERATIONS):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS_SPEC,
                temperature=temperature
            )
        except Exception as e:
            logger.error(f"LLM proxy call error: {e}")
            return {
                "reply": f"เกิดข้อผิดพลาดในการเชื่อมต่อโมเดล: {str(e)}",
                "tool_trace": tool_trace,
                "structured": None
            }
            
        choice = response.choices[0]
        message = choice.message
        
        # Check if the model wants to call tools
        if message.tool_calls:
            # Append assistant message with tool calls to history
            messages.append(message)
            
            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                try:
                    fn_args = json.loads(tool_call.function.arguments)
                except Exception:
                    fn_args = {}
                    
                tool_trace.append({"tool": fn_name, "args": fn_args})
                logger.info(f"[Iteration {iteration+1}] Calling tool: {fn_name} with {fn_args}")
                
                # Execute tool
                tool_result = dispatch_tool(fn_name, fn_args)
                
                # Append tool result to context
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result, ensure_ascii=False)
                })
        else:
            # Assistant provided a final answer
            final_text = message.content or ""
            structured_data = extract_structured_json(final_text)
            return {
                "reply": final_text,
                "tool_trace": tool_trace,
                "structured": structured_data.model_dump() if structured_data else None,
                "iterations": iteration + 1
            }
            
    # Max iterations exceeded fallback
    fallback_text = "การประเมินใช้จำนวนรอบเกินกำหนด สรุปเบื้องต้น: ควรเว้นระยะร่นอย่างน้อย 4 เมตรจากโครงสร้างเพื่อความปลอดภัย"
    return {
        "reply": fallback_text,
        "tool_trace": tool_trace,
        "structured": extract_structured_json(fallback_text).model_dump(),
        "iterations": MAX_AGENT_ITERATIONS
    }

async def stream_agent(
    user_message: str,
    history: Optional[List[Dict[str, Any]]] = None,
    temperature: float = 0.0,
    min_score: Optional[float] = None
) -> AsyncGenerator[str, None]:
    """SSE streaming generator yielding live events, tool execution traces, and tokens."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if history:
        for msg in history[-6:]:
            role = msg.get("role")
            content = msg.get("content", "")
            if role in ["user", "assistant"]:
                messages.append({"role": role, "content": content})
                
    messages.append({"role": "user", "content": user_message})
    
    yield f"data: {json.dumps({'type': 'status', 'content': 'กำลังวิเคราะห์ข้อกำหนดพื้นที่และความปลอดภัย...'}, ensure_ascii=False)}\n\n"
    
    for iteration in range(MAX_AGENT_ITERATIONS):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS_SPEC,
                temperature=temperature
            )
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'Upstream error: {str(e)}'}, ensure_ascii=False)}\n\n"
            return
            
        choice = response.choices[0]
        message = choice.message
        
        if message.tool_calls:
            messages.append(message)
            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                try:
                    fn_args = json.loads(tool_call.function.arguments)
                except Exception:
                    fn_args = {}
                    
                tool_label = {
                    "evaluate_root_hazard": "กำลังคำนวณระยะร่นและแรงดันระบบราก",
                    "search_trees_by_criteria": "กำลังค้นหาพันธุ์ไม้ตามขนาดพื้นที่และแดด",
                    "search_tree_knowledge": "กำลังค้นคว้าเอกสารรุกขกรรมพรรณไม้ (RAG)"
                }.get(fn_name, fn_name)
                
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': fn_name, 'label': tool_label, 'args': fn_args}, ensure_ascii=False)}\n\n"
                
                tool_result = dispatch_tool(fn_name, fn_args)
                
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': fn_name, 'result': tool_result}, ensure_ascii=False)}\n\n"
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result, ensure_ascii=False)
                })
        else:
            final_text = message.content or ""
            # Stream final tokens or text chunks
            chunk_size = 20
            for i in range(0, len(final_text), chunk_size):
                chunk = final_text[i:i+chunk_size]
                yield f"data: {json.dumps({'type': 'token', 'token': chunk}, ensure_ascii=False)}\n\n"
                
            structured_data = extract_structured_json(final_text)
            yield f"data: {json.dumps({'type': 'done', 'structured': structured_data.model_dump() if structured_data else None}, ensure_ascii=False)}\n\n"
            return
            
    yield f"data: {json.dumps({'type': 'done', 'structured': None}, ensure_ascii=False)}\n\n"
