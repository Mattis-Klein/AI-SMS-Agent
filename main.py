from fastapi import FastAPI, Request
from fastapi.responses import Response

app = FastAPI()

@app.get("/")
def home():
    return {"status": "running"}

@app.post("/sms")
async def receive_sms(request: Request):
    form = await request.form()
    sender = form.get("From")
    message = form.get("Body")

    print("NEW SMS:")
    print("FROM:", sender)
    print("MESSAGE:", message)

    return Response(
        content="<?xml version='1.0' encoding='UTF-8'?><Response></Response>",
        media_type="application/xml",
    )