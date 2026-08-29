from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """환경변수를 로드하는 설정 클래스"""

    gemini_api_key: str
    kakao_map_api_key: str = ""
    database_url: str = "sqlite:///./skinscope.db"
        # 기본 모델: 정확도 우선. 쿼터 초과 시 fallback 모델로 자동 전환
    gemini_primary_model: str = "gemini-3.6-flash"
    gemini_fallback_model: str = "gemini-3.5-flash-lite"
    share_link_expiry_days: int = 7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()