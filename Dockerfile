# Two-stage build for CUDA llama-cpp-python with Git support
FROM nvidia/cuda:12.5.1-devel-ubuntu22.04 AS builder

# Install build dependencies including git
RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y git build-essential \
    python3 \
    python3-pip \
    gcc \
    wget \
    ocl-icd-opencl-dev \
    opencl-headers \
    clinfo \
    libclblast-dev \
    libopenblas-dev \
    && mkdir -p /etc/OpenCL/vendors \
    && echo "libnvidia-opencl.so.1" > /etc/OpenCL/vendors/nvidia.icd

# Set CUDA build environment
ENV CUDA_DOCKER_ARCH=all
ENV LLAMA_CUBLAS=1
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/local/cuda/compat:$LD_LIBRARY_PATH

# Install Python dependencies
RUN python3 -m pip install --user --upgrade pip cmake scikit-build setuptools

# Install llama-cpp-python with CUDA support
RUN CMAKE_ARGS="-DGGML_CUDA=on" pip install --user llama-cpp-python \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu125 \
    --verbose

# Runtime stage
FROM nvidia/cuda:12.5.1-runtime-ubuntu22.04

ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH

# Install runtime dependencies including git and pytest for testing
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install pytest and coverage tools for git-based testing
RUN pip install pytest pytest-cov

# Copy CUDA-enabled llama-cpp from builder
COPY --from=builder /root/.local/lib/python3.10/site-packages/ /usr/local/lib/python3.10/dist-packages/

# Copy project files
COPY . .

EXPOSE 8000

CMD ["python3", "local_llm_mcp_server.py"]
