from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from .settings import settings, Email
from .sender import build_message, send_with_retries

app = FastAPI(title="SMTP independiente", version="1.0.0")

@app.get("/")
async def health():
    return {"status": "ok", "smtp_host": settings.SMTP_HOST}

@app.post("/send")
async def send_email(payload: Email):
    if len(payload.to) > settings.MAX_RCPTS:
        raise HTTPException(400, f"Demasiados destinatarios (>{settings.MAX_RCPTS})")
    try:
        msg = build_message(
            payload.to,
            payload.subject,
            payload.body_text,
            payload.body_html,
            payload.headers,
            payload.from_domain,  # ← aquí
        )
        resp = await send_with_retries(msg)
        return JSONResponse({"status": "sent", "result": resp})
    except Exception as e:
        raise HTTPException(502, f"Error SMTP: {e!s}")
