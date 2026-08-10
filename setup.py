from setuptools import setup, find_packages

setup(
    name="facturx-api",
    version="1.0.1",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0",
        "python-multipart>=0.0.5",
        "lxml>=4.6.3",
        "pikepdf>=2.0.0",
    ],
    description="API for Factur-X PDF generation, XML extraction and validation",
    author="Factur-X Team",
    python_requires=">=3.10",
)
