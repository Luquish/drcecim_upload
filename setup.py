# setup.py
from setuptools import setup, find_packages

setup(
    name="drcecim_shared",
    version="0.1.0",
    packages=find_packages(include=['services', 'config', 'models', 'utils']),
    description="Módulos compartidos para el sistema DrCecim.",
    author="DrCecim Team",
    install_requires=[
        # Dependencias básicas para los módulos compartidos
        "google-cloud-storage>=2.10.0",
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "python-dotenv>=1.0.0",
        "tqdm>=4.65.0",
        "openai>=1.3.0",
        "faiss-cpu>=1.7.4",
    ],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
) 