from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from scraper import verify_license, verify_batch

app = FastAPI(title="Contractor License Verification API", version="3.0")

class LicenseRequest(BaseModel):
    state: str
    license_number: Optional[str] = None
    business_name: Optional[str] = None

class BatchRequest(BaseModel):
    requests: List[LicenseRequest]

@app.get("/")
async def root():
    return {"message": "Contractor License Verification API v3.0", "status": "active"}

@app.post("/verify")
async def verify(request: LicenseRequest):
    try:
        result = await verify_license(request.state, request.license_number, request.business_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/verify_batch")
async def verify_multiple(batch: BatchRequest):
    try:
        queries = [r.dict() for r in batch.requests]
        results = await verify_batch(queries)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
