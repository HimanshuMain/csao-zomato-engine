from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from ml_engine import CSAORecommender
import uvicorn

app = FastAPI()

# compress large payloads to fix port-forwarding latency
app.add_middleware(GZipMiddleware, minimum_size=500)

# prevent pre-flight request lag
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")
engine = CSAORecommender()

class CartRequest(BaseModel):
    cart_item_ids: List[str]
    res_id: str
    user_id: str = None
    current_hour: int = 14 
    current_month: int = 3

class FeedRequest(BaseModel):
    user_id: str = None
    current_hour: int = 14
    current_month: int = 3

class CheckoutRequest(BaseModel):
    cart_item_ids: List[str]
    res_id: str
    user_id: str
    total_amount: float

@app.get("/", response_class=HTMLResponse)
async def serve_ui(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/users")
def get_users():
    return {"users": engine.get_users()}

@app.post("/api/feed")
def get_feed(req: FeedRequest):
    return {"items": engine.get_feed(req.user_id, req.current_hour, req.current_month, limit=2000)} 

@app.post("/api/recommend")
def get_recommendations(req: CartRequest):
    recs = engine.get_recommendations(req.cart_item_ids, req.res_id, req.user_id, req.current_hour, req.current_month)
    return {"recommendations": recs}

@app.post("/api/upsell")
def get_upsell(req: CartRequest):
    upsells = engine.get_upsell(req.cart_item_ids, req.res_id)
    return {"upsells": upsells}

@app.post("/api/checkout")
def process_checkout(req: CheckoutRequest):
    engine.save_order(req.user_id, req.res_id, req.cart_item_ids, req.total_amount)
    return {"status": "success"}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=9000, reload=True)