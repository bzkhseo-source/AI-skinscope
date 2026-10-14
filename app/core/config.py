from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """환경변수를 로드하는 설정 클래스"""

    gemini_api_key: str
    kakao_map_api_key: str = ""
    uv_api_key: str = ""
    # 성분 추천 시 실제 화장품 완제품 링크를 찾기 위한 네이버쇼핑 검색 API 키.
    # 둘 중 하나라도 비어있으면 naver_service가 호출을 건너뛰고 기존 범용
    # 검색 링크로 degrade한다(docs/개선 과정 작업지시서/INGREDIENT_PRODUCT_LINK_SPEC.md 참고).
    naver_client_id: str = ""
    naver_client_secret: str = ""
    database_url: str = "sqlite:///./skinscope.db"
        # 기본 모델: 정확도 우선. 쿼터 초과 시 fallback 모델로 자동 전환
    gemini_primary_model: str = "gemini-3.6-flash"
    gemini_fallback_model: str = "gemini-3.5-flash-lite"
    share_link_expiry_days: int = 7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()