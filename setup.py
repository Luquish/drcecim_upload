# setup.py
from setuptools import setup, find_packages

# Dependencias principales (producción)
install_requires = [
    # Google Cloud Services
    "google-cloud-storage>=2.10.0,<2.20.0",
    "google-cloud-secret-manager>=2.16.0,<2.20.0",
    
    # Data Processing
    "pandas>=2.0.0,<2.3.0",
    "numpy>=1.24.0,<1.27.0",
    
    # Configuration and Environment
    "python-dotenv>=1.0.0,<1.1.0",
    "pydantic>=2.0.0,<2.6.0",
    "pydantic-settings>=2.0.0,<2.2.0",
    
    # AI/ML Libraries
    "openai>=1.3.0,<1.15.0",
    "faiss-cpu>=1.7.4,<1.8.0",
    
    # File Processing
    "python-magic>=0.4.27,<0.5.0",
    
    # Utilities
    "tqdm>=4.65.0,<4.67.0",
    "tenacity>=8.2.0,<8.3.0",
    "typing-extensions>=4.0.0,<4.10.0",
    "requests>=2.31.0,<2.32.0",
    "psutil>=5.9.0,<5.10.0",  # Para métricas del sistema
]

# Dependencias de desarrollo y testing
dev_requires = [
    # Testing Framework
    "pytest>=7.4.0,<7.5.0",
    "pytest-cov>=4.1.0,<4.2.0",
    "pytest-mock>=3.11.0,<3.12.0",
    "coverage>=7.3.0,<7.5.0",
    
    # Code Quality
    "black>=23.0.0,<24.0.0",
    "flake8>=6.0.0,<6.2.0",
    "isort>=5.12.0,<5.14.0",
    "mypy>=1.5.0,<1.9.0",
    
    # Development Tools
    "pre-commit>=3.0.0,<3.7.0",
    "bandit>=1.7.0,<1.8.0",  # Security linting
    "safety>=2.3.0,<2.4.0",  # Dependency vulnerability checking
]

# Dependencias para UI (opcional para desarrollo local)
ui_requires = [
    "streamlit>=1.28.0,<1.33.0",
]

# Dependencias para Cloud Functions
cloud_requires = [
    "functions-framework>=3.4.0,<3.6.0",
    "flask>=2.0.0,<3.1.0",
    "werkzeug>=2.0.0,<3.1.0",
]

# Dependencias para procesamiento de PDF
pdf_requires = [
    "marker-pdf>=0.2.0,<0.3.0",
]

setup(
    name="drcecim_shared",
    version="1.0.0",
    description="Módulos compartidos para el sistema DrCecim de procesamiento de documentos PDF.",
    long_description=open("README.md", "r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="DrCecim Team",
    author_email="soporte@medicina.uba.ar",
    url="https://github.com/medicina-uba/drcecim-upload",
    
    # Package discovery
    packages=find_packages(include=[
        'services', 
        'config', 
        'models', 
        'utils', 
        'ui',
        'services.*',
        'config.*',
        'models.*',
        'utils.*',
        'ui.*'
    ]),
    
    # Python version requirement
    python_requires=">=3.9,<3.13",
    
    # Main dependencies (production)
    install_requires=install_requires,
    
    # Optional dependencies
    extras_require={
        "dev": dev_requires,
        "ui": ui_requires,
        "cloud": cloud_requires,
        "pdf": pdf_requires,
        "all": dev_requires + ui_requires + cloud_requires + pdf_requires,
    },
    
    # Entry points
    entry_points={
        "console_scripts": [
            "drcecim-upload=streamlit_app:main",
        ],
    },
    
    # Package data
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.yml", "*.json", "*.txt", "*.md"],
    },
    
    # Classification
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Education",
        "Topic :: Education",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    
    # Keywords
    keywords="pdf processing embeddings ai chatbot education medicina uba",
    
    # Minimum package metadata
    zip_safe=False,
    
    # Project URLs
    project_urls={
        "Bug Reports": "https://github.com/medicina-uba/drcecim-upload/issues",
        "Source": "https://github.com/medicina-uba/drcecim-upload",
        "Documentation": "https://github.com/medicina-uba/drcecim-upload/wiki",
    },
)