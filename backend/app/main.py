"""InvoiceFlow FastAPI application."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import approvals, audit, dashboard, invoices, maintenance, seed, vendors
from app.config import settings
from app.database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="InvoiceFlow", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(invoices.router, prefix="/api/invoices", tags=["invoices"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["approvals"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(seed.router, prefix="/api/seed", tags=["seed"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(vendors.router, prefix="/api/vendors", tags=["vendors"])
app.include_router(maintenance.router, prefix="/api/maintenance", tags=["maintenance"])


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "invoiceflow"}
