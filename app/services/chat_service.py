import json
import logging
import math
from pathlib import Path
from typing import List, Optional

from google import genai
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.record import SkinRecord
from app.services import memory_service

logger = logging.getLogger(__name__)

KNOWLEDGE_BASE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "knowledge_base_embeddings.json"
)
EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIM = 768
RAG_TOP_K = 3

FALLBACK_MESSAGE = "지금은 답변이 어려워요, 잠시 후 다시 시도해주세요."

SYSTEM_PROMPT_TEMPLATE = """당신은 스킨케어 지식을 참고용으로 안내하는 AI 어시스턴트다. 아래 [사용자 분석
결과]와 [참고 자료]에 근거해서만 답변하라. 근거에 없는 내용은 추측하지 말고
"정확한 답변을 위해서는 추가 정보가 필요합니다"라고 답하라.

의료 진단·처방에 해당하는 질문(예: "이거 무슨 병이에요?", "약 뭐 발라야 해요?")
에는 절대 단정적으로 답하지 말고, "이 부분은 전문의 상담이 필요해요"로 안내하라.

답변은 3~4문장 이내로 간결하게, 참고용임을 자연스럽게 포함하라.

[사용자 분석 결과]
{user_context}

[참고 자료]
{rag_context}

[질문]
{question}
"""


def _load_knowledge_base() -> List[dict]:
    if not KNOWLEDGE_BASE_PATH.exists():
        logger.warning("지식베이스 파일이 없습니다 (%s).", KNOWLEDGE_BASE_PATH)
        return []
    return json.loads(KNOWLEDGE_BASE_PATH.read_text(encoding="utf-8"))


_knowledge_base_cache: Optional[List[dict]] = None


def _get_knowledge_base() -> List[dict]:
    global _knowledge_base_cache
    if _knowledge_base_cache is None:
        _knowledge_base_cache = _load_knowledge_base()
    return _knowledge_base_cache


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _retrieve_top_k(client: genai.Client, question: str) -> List[dict]:
    knowledge_base = _get_knowledge_base()
    if not knowledge_base:
        return []

    from google.genai import types  # 지연 import: 임베딩 실패해도 앱 시작에는 영향 없게

    try:
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=[question],
            config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
        )
        question_embedding = list(result.embeddings[0].values)
    except Exception as exc:  # noqa: BLE001
        logger.warning("질문 임베딩 실패: %s", exc)
        return []

    scored = [
        (doc, _cosine_similarity(question_embedding, doc["embedding"])) for doc in knowledge_base
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in scored[:RAG_TOP_K]]


def _build_rag_context(docs: List[dict]) -> str:
    if not docs:
        return "(참고 자료 없음)"
    return "\n\n".join(f"- {doc['text']}" for doc in docs)


def _build_user_context(record: Optional[SkinRecord]) -> str:
    if record is None:
        return "(분석 기록 없음)"

    agent_result = memory_service.load_agent_result(record)
    vision = agent_result.vision

    parts = [f"종합 점수: {vision.overall_score}/100"]
    if vision.feature_scores:
        scores = vision.feature_scores.model_dump()
        scores_text = ", ".join(f"{k}={v}" for k, v in scores.items())
        parts.append(f"세부 점수: {scores_text}")
    if vision.suspected_patterns:
        patterns_text = ", ".join(p.name for p in vision.suspected_patterns)
        parts.append(f"의심 패턴: {patterns_text}")
    if agent_result.product_recommendations:
        concerns_text = ", ".join(
            g.concern_label_ko for g in agent_result.product_recommendations
        )
        parts.append(f"추천 성분 관련 고민: {concerns_text}")

    return "\n".join(parts)


def answer_question(db: Session, user_id: str, record_id: int, question: str) -> str:
    """RAG(지식베이스) + 사용자 분석 결과를 근거로 질문에 답한다.

    Gemini 호출이 실패하면(쿼터 초과 등) 고정 안내 메시지로 대체해, 다른
    서비스 전체에 영향을 주지 않도록 격리한다.
    """
    client = genai.Client(api_key=settings.gemini_api_key)

    record = memory_service.get_record(db, user_id, record_id)
    user_context = _build_user_context(record)

    retrieved_docs = _retrieve_top_k(client, question)
    rag_context = _build_rag_context(retrieved_docs)

    prompt = SYSTEM_PROMPT_TEMPLATE.format(
        user_context=user_context, rag_context=rag_context, question=question
    )

    try:
        response = client.models.generate_content(
            model=settings.gemini_primary_model, contents=[prompt]
        )
        answer = (response.text or "").strip()
        return answer or FALLBACK_MESSAGE
    except Exception as exc:  # noqa: BLE001
        logger.warning("챗봇 답변 생성 실패: %s", exc)
        return FALLBACK_MESSAGE
