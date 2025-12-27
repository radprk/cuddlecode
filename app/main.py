from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="CuddleCode MVP")

class AnalyzeReq(BaseModel):
    repo_url: str

@app.post("/analyze")
def analyze(req: AnalyzeReq):
    try:
        from .pipeline import run_analysis

        run_id, out = run_analysis(req.repo_url)
        return {"run_id": run_id, "result": out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


