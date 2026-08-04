from setuptools import find_packages, setup

setup(
    name="distributed-model-server",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi==0.115.12",
        "uvicorn==0.34.3",
        "grpcio==1.71.0",
        "protobuf==5.29.5",
        "onnxruntime==1.22.0",
        "tokenizers==0.21.1",
        "numpy==2.2.6",
        "prometheus-client==0.22.1",
    ],
    extras_require={
        "dev": [
            "httpx==0.28.1",
            "pytest==8.4.0",
            "pytest-asyncio==1.0.0",
            "ruff==0.11.13",
            "mypy==1.16.0",
            "grpcio-tools==1.71.0",
        ]
    },
)
