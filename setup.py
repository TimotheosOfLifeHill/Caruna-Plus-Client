#!/usr/bin/env python

"""The setup script."""

import pathlib

from setuptools import find_packages, setup

here = pathlib.Path(__file__).parent.resolve()
long_description = (here / "README.md").read_text(encoding="utf-8")

requirements = [
    "beautifulsoup4==4.12.3",
    "python-dateutil==2.9.0.post0",
    "requests>=2.28.1",
    "soupsieve==2.5",
    "urllib3==1.26.5",
    "cachetools>=5.3.3",
    "keyring>=23.0.1",
]

setup(
    author="TimotheosOfLifeHill",
    author_email="timo.elovaara@gmail.com",
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    description="Caruna Plus API library and CLI",
    entry_points={
        "console_scripts": [
            "caruna-plus-cli=carunaplusservice.cli:main",
        ],
    },
    name="caruna-plus-cli",
    install_requires=requirements,
    license="MIT license",
    long_description=long_description,
    long_description_content_type="text/markdown",
    include_package_data=True,
    packages=find_packages(include=["carunaplusservice", "carunaplusservice.*"]),
    url="https://github.com/TimotheosOfLifeHill/Caruna-Plus-Client",
    version="0.0.6-alpha",
    zip_safe=False,
)
