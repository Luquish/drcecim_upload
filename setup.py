# setup.py
from setuptools import setup, find_packages

setup(
    name="drcecim_shared",
    version="0.1.0",
    packages=find_packages(include=['services', 'config', 'models', 'utils']),
    description="Módulos compartidos para el sistema DrCecim.",
    author="DrCecim Team",
    install_requires=[
        # Dependencias compartidas por ambos servicios
        "google-cloud-storage>=2.10.0",
        "google-cloud-secret-manager>=2.16.0", # Para secrets_service
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0", # Para settings.py
        "tqdm>=4.65.0",
        "openai>=1.3.0",
        "faiss-cpu>=1.7.4",
        "python-magic>=0.4.27", # Para file_validator
        "tenacity>=8.2.0"
    ],
    python_requires=">=3.8",
)