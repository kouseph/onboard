from fastapi import FastAPI, Request, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import os
import re

app = FastAPI(title="Backend API")

# Get allowed origins from environment or use defaults
allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",") if os.getenv("ALLOWED_ORIGINS") else []
# Remove empty strings from split
allowed_origins = [origin.strip() for origin in allowed_origins if origin.strip()]

# Default origins if not set via env
default_origins = [
    "https://onboard-dun.vercel.app",
    "https://afterquery-test.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Combine env origins with defaults (avoid duplicates)
origins = list(set(allowed_origins + default_origins))

# Regex pattern for Vercel apps
vercel_regex = re.compile(r"https://.*\.vercel\.app$")

def is_origin_allowed(origin: str) -> bool:
    """Check if an origin is allowed."""
    if not origin:
        return False
    return origin in origins or bool(vercel_regex.match(origin))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Exception handlers to ensure CORS headers are included in error responses
@app.exception_handler(HTTPException)
async def fastapi_http_exception_handler(request: Request, exc: HTTPException):
    """Ensure CORS headers are included in FastAPI HTTP exception responses."""
    origin = request.headers.get("origin")
    headers = {}
    
    # Check if origin is allowed
    if is_origin_allowed(origin):
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Access-Control-Allow-Methods"] = "*"
        headers["Access-Control-Allow-Headers"] = "*"
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Ensure CORS headers are included in Starlette HTTP exception responses."""
    origin = request.headers.get("origin")
    headers = {}
    
    # Check if origin is allowed
    if is_origin_allowed(origin):
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Access-Control-Allow-Methods"] = "*"
        headers["Access-Control-Allow-Headers"] = "*"
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Ensure CORS headers are included in validation error responses."""
    origin = request.headers.get("origin")
    headers = {}
    
    # Check if origin is allowed
    if is_origin_allowed(origin):
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Access-Control-Allow-Methods"] = "*"
        headers["Access-Control-Allow-Headers"] = "*"
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
        headers=headers,
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Ensure CORS headers are included in all exception responses."""
    origin = request.headers.get("origin")
    headers = {}
    
    # Check if origin is allowed
    if is_origin_allowed(origin):
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Access-Control-Allow-Methods"] = "*"
        headers["Access-Control-Allow-Headers"] = "*"
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
        headers=headers,
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
