FROM python:3.9

# Install Rust and Cargo
RUN set -e && \
    apt-get update && \
    apt-get install -y curl && \
    curl https://sh.rustup.rs -sSf | sh -s -- -y && \
    . $HOME/.cargo/env

WORKDIR /usr/app

# Add Rust and Cargo to the PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        gcc \
        libssl-dev \
        libffi-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt requirements.txt
RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt --use-feature=fast-deps

# Copy the app and models folders
COPY app/. .

ENV PYTHONPATH="/usr/"

CMD ["python", "indexers/main.py"]

