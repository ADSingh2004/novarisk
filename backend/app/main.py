from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import endpoints

import logging
import warnings

# Suppress non-critical GDAL warnings on Windows
warnings.filterwarnings('ignore', message='.*CPLE_NotSupported.*')
warnings.filterwarnings('ignore', category=RuntimeWarning)

logger = logging.getLogger(__name__)
logger.info("GDAL CPLE_NotSupported warnings suppressed")

app = FastAPI(
    title="NovaRisk ESG API",
    description="Satellite ESG Intelligence Dashboard API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(endpoints.router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to NovaRisk ESG API"}
