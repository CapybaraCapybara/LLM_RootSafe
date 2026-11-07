from pydantic import BaseModel, Field, model_validator
from typing import Literal, Optional, List, Dict, Any

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000, description="User question or garden scenario")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Previous chat conversation history")
    temperature: float = Field(0.0, ge=0.0, le=1.5, description="Sampling temperature (0 for reproducible eval)")
    min_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Optional RAG similarity score floor override")

class RootHazardArgs(BaseModel):
    tree_name: str = Field(..., description="ชื่อภาษาไทยหรือภาษาอังกฤษของต้นไม้ เช่น 'หูกระจง', 'โมก', 'มะม่วง'")
    distance_meters: float = Field(..., gt=0.0, le=100.0, description="ระยะห่างระหว่างตำแหน่งปลูกถึงสิ่งปลูกสร้าง (เมตร)")
    structure_type: Literal["house_foundation", "fence", "pipe", "sidewalk"] = Field(
        ..., description="ประเภทโครงสร้าง: house_foundation (ฐานรากบ้าน/ตัวบ้าน), fence (กำแพงรั้ว), pipe (ท่อประปา/ท่อระบายน้ำ), sidewalk (ทางเท้า/ลานคอนกรีต)"
    )

class TreeFilterArgs(BaseModel):
    sunlight: Optional[Literal["full_sun", "partial_shade", "full_shade"]] = Field(
        default=None, description="ระดับแสงแดด: full_sun (แดดทั้งวัน), partial_shade (แดดครึ่งวัน/รำไร), full_shade (ร่มตลอดวัน)"
    )
    max_space_meters: Optional[float] = Field(
        default=None, gt=0.0, description="ความกว้างของพื้นที่หรือระยะห่างสิ่งปลูกสร้างที่มี (เมตร)"
    )
    pet_safe_only: Optional[bool] = Field(
        default=False, description="ต้องการเฉพาะต้นไม้ที่ไม่เป็นพิษต่อสัตว์เลี้ยง (สุนัข/แมว)"
    )
    maintenance_level: Optional[Literal["low", "medium", "high"]] = Field(
        default=None, description="ระดับการดูแลรักษาและการกวาดใบไม้"
    )

class TreeKnowledgeArgs(BaseModel):
    query: str = Field(..., min_length=2, description="คำค้นหาเกี่ยวกับลักษณะพรรณไม้ ระบบราก โรค หรือการดูแล")
    top_k: int = Field(default=3, ge=1, le=5, description="จำนวนเอกสารที่ต้องการดึง")

class TreeData(BaseModel):
    id: str
    name_th: str
    name_en: str
    scientific_name: str
    root_type: str
    root_aggressiveness_score: int
    min_foundation_distance_m: float
    min_fence_distance_m: float
    max_height_m: float
    canopy_spread_m: float
    sunlight: str
    leaf_shedding: str
    pet_toxic: bool
    maintenance_level: str
    architectural_use: str
    root_risk_description: str
    legal_neighbor_risk: str
    care_and_soil: str

class ConsultationReport(BaseModel):
    verdict: Literal["SAFE", "WARNING", "PROHIBITED"] = Field(
        ..., description="ผลการประเมินความปลอดภัย: SAFE (ปลอดภัย), WARNING (เสี่ยงปานกลาง/ต้องมีเงื่อนไข), PROHIBITED (ห้ามปลูกเด็ดขาด)"
    )
    hazard_score: int = Field(..., ge=1, le=10, description="คะแนนความเสี่ยงเชิงโครงสร้าง 1 (ปลอดภัยมาก) ถึง 10 (อันตรายสูงสุด)")
    summary: str = Field(..., description="สรุปคำแนะนำทางรุกขกรรมสำหรับเจ้าของบ้าน")
    recommended_trees: List[str] = Field(default_factory=list, description="รายชื่อพันธุ์ไม้ที่แนะนำให้ปลูกแทนหรืออนุญาตให้ปลูกได้")
    safe_setback_meters: float = Field(..., description="ระยะร่นขั้นต่ำที่ปลอดภัยตามหลักวิชาการ (เมตร)")
    neighbor_impact_notes: str = Field(
        default="ระวังกิ่งก้านและระบบรากแผ่ขยายล้ำแนวเขต",
        description="ข้อควรระวังเกี่ยวกับผลกระทบต่อพื้นที่ข้างเคียง (เช่น กิ่งก้าน ทรงพุ่ม ใบร่วง)"
    )
    legal_neighbor_risk_notes: Optional[str] = Field(
        default=None,
        description="Deprecated alias for backward compatibility"
    )
    citations: List[str] = Field(default_factory=list, description="แหล่งอ้างอิงข้อมูลพรรณไม้ที่ใช้ประกอบการวินิจฉัย")

    @model_validator(mode="before")
    @classmethod
    def sync_neighbor_notes(cls, data: Any):
        if isinstance(data, dict):
            if "neighbor_impact_notes" not in data and "legal_neighbor_risk_notes" in data:
                data["neighbor_impact_notes"] = data["legal_neighbor_risk_notes"]
            elif "neighbor_impact_notes" in data and "legal_neighbor_risk_notes" not in data:
                data["legal_neighbor_risk_notes"] = data["neighbor_impact_notes"]
        return data
