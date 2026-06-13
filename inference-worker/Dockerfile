FROM python:3.11-slim

# System deps for InsightFace/OpenCV (ArcFace needs libxcb, libGL, libSM, libXext)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxcb-shm0 libxcb-xfixes0 libxcb-shape0 \
    libxcb-xinerama0 libxcb-randr0 libxcb-render0 \
    libxcb-keysyms1 libxcb-image0 libxcb-icccm4 \
    libxcb-sync1 libxcb-xkb1 libxkbcommon0 \
    libxkbcommon-x11-0 libgl1 libglib2.0-0 \
    libsm6 libxext6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Download large ONNX models not stored in git (synthetic face detector)
RUN python3 -c "
import os, urllib.request
models = {
    'efficientnet_b0_fp32.onnx': 'https://huggingface.co/MeowLabs/lynxauth-models/resolve/main/efficientnet_b0_fp32.onnx',
    'synthetic_vit_int8.onnx': 'https://huggingface.co/MeowLabs/lynxauth-models/resolve/main/synthetic_vit_int8.onnx',
}
os.makedirs('/app/models', exist_ok=True)
for name, url in models.items():
    path = f'/app/models/{name}'
    if not os.path.exists(path):
        print(f'Downloading {name}...')
        urllib.request.urlretrieve(url, path)
        print(f'Downloaded {name}')
" 2>&1 || echo "[WARN] Model download failed, may need manual download"

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
