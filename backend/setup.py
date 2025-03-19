from setuptools import setup, find_packages

setup(
    name="quickscript",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        line.strip() for line in open("requirements.txt")
        if not line.startswith("#")
    ],
)

