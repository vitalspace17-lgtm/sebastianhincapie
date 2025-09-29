from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # === SMTP (Postfix local por defecto) ===
    SMTP_HOST: str = "127.0.0.1"
    SMTP_PORT: int = 25
    SMTP_USER: str = ""
    SMTP_PASS: SecretStr = SecretStr("")
    SMTP_STARTTLS: bool = False
    SMTP_TIMEOUT: float = 60.0

    # === Retries / límites ===
    MAX_RCPTS: int = 100
    RETRIES: int = 3
    RETRY_BACKOFF_SECS: float = 2.0

    # === From dinámico ===
    FROM_NAME: str = "Renewal"
    FROM_EMAIL: EmailStr = "renewal@e-filemycorporation.com"
    FROM_LOCALPART: str = "renewal"
    DEFAULT_DOMAIN: str = "e-filemycorporation.com"
    DISPLAY_NAMES: Dict[str, str] = {
        "e-filemycorporation.com": "Renewal",
        "e-filemycorp.com": "Renewal",
    }

    # === Cabeceras por defecto ===
    DEFAULT_HEADERS: Dict[str, str] = {
        "List-Unsubscribe": "<mailto:unsubscribe@e-filemycorporation.com>",
    }

    # === CSV legacy (si lo usas) ===
    CSV_PATH: str = "/home/taylerk/Documentos/smtpppp/datosPrueba.csv"
    CSV_EMAIL_COLUMN: str = "gmail"

    # === WordPress magic-link ===
    WP_MAGIC_URL: Optional[HttpUrl] = None  # p.ej. https://renewals.../wp-json/comown/v1/magic-link
    WP_API_KEY: SecretStr = SecretStr("")
    WP_PREFER: str = "business_id"

    # === Seguridad de API /send ===
    API_BEARER_TOKEN: SecretStr = SecretStr("")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @field_validator("WP_PREFER")
    @classmethod
    def _validate_prefer(cls, v: str) -> str:
        v = (v or "").strip().lower()
        return v if v in {"business_id", "email"} else "business_id"

    @field_validator("DISPLAY_NAMES")
    @classmethod
    def _lowercase_domains(cls, v: Dict[str, str]) -> Dict[str, str]:
        return { (k or "").lower(): (val or "") for k, val in (v or {}).items() }


settings = Settings()


class Email(BaseModel):
    """Payload para /send"""
    to: List[EmailStr] = Field(..., min_length=1)
    subject: str = Field(..., min_length=1, max_length=200)
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    from_domain: Optional[str] = None
    reply_to: Optional[EmailStr] = None
    list_unsubscribe: Optional[str] = None
    tracking_id: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None

    @field_validator("from_domain")
    @classmethod
    def _normalize_domain(cls, v: Optional[str]) -> Optional[str]:
        return v.lower().strip() if isinstance(v, str) and v.strip() else v
