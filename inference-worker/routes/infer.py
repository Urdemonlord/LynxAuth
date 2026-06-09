from fastapi import APIRouter, File, Form, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.deepfake_detector import DeepfakeDetector
from services.embedding_store import EmbeddingStore
from services.face_recognizer import FaceRecognizer

router = APIRouter(prefix="/infer", tags=["infer"])
deepfake_detector = DeepfakeDetector()
face_recognizer = FaceRecognizer()
embedding_store = EmbeddingStore()


class RegisterResponse(BaseModel):
    success: bool
    user_id: str
    message: str


class VerifyResponse(BaseModel):
    authenticated: bool
    user_id: str | None = None
    confidence: float | None = None
    deepfake_detected: bool
    latency_ms: int


@router.post("/register", response_model=RegisterResponse)
async def register_face(user_id: str = Form(...), image: UploadFile = File(...)) -> RegisterResponse:
    image_bytes = await image.read()
    embedding = face_recognizer.extract_embedding(image_bytes)
    await embedding_store.store(user_id=user_id, embedding=embedding)
    return RegisterResponse(success=True, user_id=user_id, message="Face enrolled successfully.")


@router.post("/verify", response_model=VerifyResponse)
async def verify_face(image: UploadFile = File(...)) -> VerifyResponse:
    image_bytes = await image.read()

    if deepfake_detector.is_fake(image_bytes):
        payload = VerifyResponse(
            authenticated=False,
            user_id=None,
            confidence=None,
            deepfake_detected=True,
            latency_ms=100,
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=payload.model_dump(),
        )

    embedding = face_recognizer.extract_embedding(image_bytes)
    user_id, confidence = await embedding_store.match(embedding)
    return VerifyResponse(
        authenticated=user_id is not None,
        user_id=user_id,
        confidence=confidence,
        deepfake_detected=False,
        latency_ms=250,
    )
