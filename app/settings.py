from pydantic import BaseModel, EmailStr, Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # === SMTP (por defecto: Postfix local) ===
    SMTP_HOST: str = "127.0.0.1"
    SMTP_PORT: int = 25
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_STARTTLS: bool = False
    TIMEOUT: float = 60.0

    # === Remitente por defecto (fallback) ===
    FROM_NAME: str = "Renewal"
    FROM_EMAIL: EmailStr = "renewal@e-filemycorporation.com"

    # === FROM dinámico ===
    # local-part fijo para construir renewal@<dominio>
    FROM_LOCALPART: str = "renewal"
    # dominio por defecto
    DEFAULT_DOMAIN: str = "e-filemycorporation.com"
    # display-name que mostraremos por dominio
    DISPLAY_NAMES: dict[str, str] = {
        "e-filemycorporation.com": "Renewal",
        "e-filemycorp.com": "Renewal",
    }

    # === Operación ===
    MAX_RCPTS: int = 100
    RETRIES: int = 3

    # === CSV (envío masivo) ===
    CSV_PATH: str = "/home/taylerk/Documentos/smtpppp/datosPrueba.csv"
    CSV_EMAIL_COLUMN: str = "gmail"

    class Config:
        env_file = ".env"
        extra = "ignore"

# Instancia global
settings = Settings()


class Email(BaseModel):
    """Payload del endpoint /send"""
    to: list[EmailStr] = Field(..., min_length=1)
    subject: str = Field(..., min_length=1, max_length=200)
    body_text: str | None = None
    body_html: str | None = None
    headers: dict[str, str] | None = None
    # Permite elegir el dominio del From por petición (ej: e-filemycorporation.com)
    from_domain: str | None = None
