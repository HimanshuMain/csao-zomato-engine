import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, ORJSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import uvicorn
from ml_engine import CSAORecommender

app = FastAPI(default_response_class=ORJSONResponse)

app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


base_dir = os.path.dirname(os.path.abspath(__file__))
template_path = os.path.join(base_dir, "templates")
templates = Jinja2Templates(directory=template_path)

engine = CSAORecommender()

class CartRequest(BaseModel):
    cart_item_ids: List[str]
    res_id: str
    user_id: str = None
    current_hour: int = 14 
    current_month: int = 3

@app.get("/", response_class=HTMLResponse)
async def serve_ui(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/users")
def get_users():
    return {"users": engine.get_users()}

@app.post("/api/feed")
def get_feed(req: dict):
   
    u_id = req.get('user_id', 'user_1')
    hr = req.get('current_hour', 14)
    mo = req.get('current_month', 3)
    return {"items": engine.get_feed(u_id, hr, mo, limit=1000)}

@app.post("/api/recommend")
def get_recommendations(req: CartRequest):
    recs = engine.get_recommendations(req.cart_item_ids, req.res_id, req.user_id, req.current_hour, req.current_month)
    return {"recommendations": recs}

@app.post("/api/upsell")
def get_upsell(req: CartRequest):
    return {"upsells": engine.get_upsell(req.cart_item_ids, req.res_id)}

@app.post("/api/checkout")
def process_checkout(req: CartRequest):
    engine.save_order(req.user_id, req.res_id, req.cart_item_ids, 0)
    return {"status": "success"}

@app.exception_handler(404)
async def custom_404_handler(request, __):
    return RedirectResponse("/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)