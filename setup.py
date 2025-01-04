from setuptools import setup, find_packages

__project__ = "logme"
__version__ = "0.1.0"
__description__ = "Collector and analyser of my digital footprint"
__author__ = "Ricardo Jose Olvera Flores"
__author_email__ = "olveraricardo72@gmail.com"

__classifiers__ = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Education",
    "Programming Language :: Python :: 3",
]

setup(
    packages=find_packages(),
    name=__project__,
    version=__version__,
    description=__description__,
    author=__author__,
    author_email=__author_email__,
    classifiers=__classifiers__,
)
