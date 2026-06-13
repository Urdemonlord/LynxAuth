from fastapi import APIRouter, File, Form, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.deepfake_detector import DeepfakeDetector
from services.embedding_store import EmbeddingStore
from services.face_recognizer import FaceRecognizer
from services.synthetic_face_detector import SyntheticFaceDetector

router = APIRouter(prefix="/infer", tags=["infer"])
deepfake_detector = DeepfakeDetector()
face_recognizer = FaceRecognizer()
synthetic_detector = SyntheticFaceDetector()
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
    synthetic_detected: bool = False
    vit_prob: float = 0.0
    synth_prob: float = 0.0
    det_score: float = 0.0
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

    # --- Stage 1: ViT deepfake detection (faceswap artifacts) ---
    scores = deepfake_detector.get_scores(image_bytes)
    vit_prob = scores["vit_prob"]
    deepfake_flag = deepfake_detector.is_fake(image_bytes)

    # --- Stage 2: ArcFace face quality check ---
    face_quality = face_recognizer.detect_face_quality(image_bytes)
    arcface_anomaly = False
    det_score = 0.0
    if face_quality is not None:
        det_score = face_quality["det_score"]
        # Low det_score can be caused by occlusion (hand, mask, angle),
        # not necessarily synthetic. Only flag as anomaly if no face at all,
        # or low det_score with ViT corroboration.
        if face_quality["face_count"] == 0:
            arcface_anomaly = True
        elif face_quality["det_score"] < 0.3 and vit_prob >= 0.5:
            arcface_anomaly = True

    # --- Stage 3: Dedicated synthetic/AI-generated face detection ---
    synth_prob = synthetic_detector.get_score(image_bytes)
    synth_flag = synthetic_detector.is_synthetic(image_bytes)

    # --- Combined decision ---
    if deepfake_flag:
        is_deepfake = True
    elif synth_flag:
        is_deepfake = True
    elif arcface_anomaly:
        is_deepfake = True
    else:
        is_deepfake = False

    if is_deepfake:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=VerifyResponse(
                authenticated=False,
                user_id=None,
                confidence=None,
                deepfake_detected=deepfake_flag,
                synthetic_detected=synth_flag,
                vit_prob=vit_prob,
                synth_prob=synth_prob,
                det_score=det_score,
                latency_ms=100,
            ).model_dump(),
        )

    # --- Stage 4: Face matching ---
    try:
        embedding = face_recognizer.extract_embedding(image_bytes)
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=VerifyResponse(
                authenticated=False,
                user_id=None,
                confidence=None,
                deepfake_detected=False,
                synthetic_detected=False,
                vit_prob=vit_prob,
                synth_prob=synth_prob,
                det_score=det_score,
                latency_ms=50,
            ).model_dump(),
        )

    user_id, confidence = await embedding_store.match(embedding)
    return JSONResponse(
        content=VerifyResponse(
            authenticated=user_id is not None,
            user_id=user_id,
            confidence=confidence,
            deepfake_detected=False,
            synthetic_detected=False,
            vit_prob=vit_prob,
            synth_prob=synth_prob,
            det_score=det_score,
            latency_ms=250,
        ).model_dump(),
    )
