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

RUN git config --global user.name "MCP Agent System" && \
    git config --global user.email "mcp@localhost" && \
    git config --global init.defaultBranch main && \
    git config --global --add safe.directory /workspace

# Copy requirements and install
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install pytest, coverage tools, and pre-commit for git-based testing
RUN pip install pytest pytest-cov pre-commit

# Copy CUDA-enabled llama-cpp from builder
COPY --from=builder /root/.local/lib/python3.10/site-packages/ /usr/local/lib/python3.10/dist-packages/

# Copy project files
COPY . .

EXPOSE 8000

# Copy pre-commit template
COPY templates/.pre-commit-config.yaml /app/precommit-template.yaml

# Setup workspace on container start
RUN echo '#!/bin/bash\n\
if [ -d "/workspace" ]; then\n\
    cd /workspace\n\
    if [ -d ".git" ] && [ ! -f ".pre-commit-config.yaml" ]; then\n\
        cp /app/precommit-template.yaml .pre-commit-config.yaml\n\
        pre-commit install 2>/dev/null || true\n\
    fi\n\
fi\n\
cd /app\n\
exec python3 local_llm_mcp_server.py' > /app/startup.sh && chmod +x /app/startup.sh

CMD ["/app/startup.sh"]
