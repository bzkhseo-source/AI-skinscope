from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """환경변수를 로드하는 설정 클래스"""

    gemini_api_key: str
    kakao_map_api_key: str = ""
    database_url: str = "sqlite:///./skinscope.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()