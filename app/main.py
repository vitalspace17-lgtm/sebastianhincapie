from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse

from .settings import settings, Email
from .sender import build_message, send_with_retries

app = FastAPI(title="SMTP independiente", version="1.0.0")


@app.get("/")
async def health():
    return {"status": "ok", "smtp_host": settings.SMTP_HOST}


@app.post("/send")
async def send_email(payload: Email, authorization: str | None = Header(None)):
    # (Opcional) Bearer si lo usas
    if settings.API_BEARER_TOKEN.get_secret_value():
        token = (authorization or "").replace("Bearer ", "")
        if token != settings.API_BEARER_TOKEN.get_secret_value():
            raise HTTPException(status_code=401, detail="Unauthorized")

    if len(payload.to) > settings.MAX_RCPTS:
        raise HTTPException(
            status_code=400,
            detail=f"Demasiados destinatarios (>{settings.MAX_RCPTS})"
        )

    try:
        # ⚠️ Aquí el fix: usar 'to=' (o posicional) en vez de 'recipients='
        msg = build_message(
            to=payload.to,
            subject=payload.subject,
            body_text=payload.body_text,
            body_html=payload.body_html,
            headers=payload.headers,
            from_domain=payload.from_domain,
        )
        resp = await send_with_retries(msg)
        return JSONResponse({"status": "sent", "result": resp})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error SMTP: {e}")
