# Cosmos-Embed1 PyTorch server for GB200 (aarch64 + Blackwell).
# Uses NVIDIA's arm64 PyTorch base (ships torch/torchvision built for aarch64 CUDA),
# which is why this runs where the amd64-only NIM cannot.
FROM nvcr.io/nvidia/pytorch:25.01-py3

ENV DEBIAN_FRONTEND=noninteractive \
    HF_HOME=/models/hf \
    COSMOS_MODEL_ID=nvidia/Cosmos-Embed1-224p \
    COSMOS_NUM_FRAMES=8 \
    COSMOS_EMBED_DIM=256

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
