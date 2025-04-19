from setuptools import setup, find_packages
from pathlib import Path

# Read dependencies from requirements.txt
requirements_path = Path(__file__).parent / "requirements.txt"
with requirements_path.open() as f:
    requirements = f.read().splitlines()

setup(
    name="agentica",
    version="0.1.0",
    description="A collection of LLM agents for various tasks",
    author="Joey David",
    packages=find_packages(),
    install_requires=requirements,
)
