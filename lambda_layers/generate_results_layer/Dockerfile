# Lambda-compatible Python 3.11 image for ARM64
FROM public.ecr.aws/lambda/python:3.11-arm64

WORKDIR /lambda

COPY requirements.txt .

# Install directly into the layer root
RUN yum update -y && \
    yum install -y zip gcc make python3-devel && \
    pip install --upgrade pip && \
    mkdir -p python && \
    pip install -r requirements.txt -t python && \
    zip -r layer.zip python && \
    yum clean all