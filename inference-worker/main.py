from contextlib import asynccontextmanager

from fastapi import FastAPI

from routes.infer import embedding_store, router as infer_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    await embedding_store.initialize()
    yield


app = FastAPI(title="LynxAuth Inference Worker", version="0.1.0", lifespan=lifespan)
app.include_router(infer_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "inference-worker"}
