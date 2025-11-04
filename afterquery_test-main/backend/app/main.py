from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Backend API")

origins = [
    "https://onboard-dun.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
#https://afterquery-test.vercel.app

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://onboard-dun.vercel.app",
        "https://afterquery-test.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
def root():
    return {"message": "Backend is running 🚀"}

# ⬇️ Import routers *after* CORS is set up
from app.routes import example, assessments, invites, candidate, review, email

app.include_router(example.router, prefix="/api")
app.include_router(assessments.router, prefix="/api")
app.include_router(invites.router, prefix="/api")
app.include_router(candidate.router, prefix="/api")
app.include_router(review.router, prefix="/api")
app.include_router(email.router, prefix="/api")

if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
