from setuptools import setup
from os import path

here = path.abspath(path.dirname(__file__))

setup(
    name="mlagents_envs",
    version="0.9.3",
    description="Unity Machine Learning Agents Interface",
    url="https://github.com/Unity-Technologies/ml-agents",
    author="Unity Technologies",
    author_email="ML-Agents@unity3d.com",
    classifiers=[
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.6",
    ],
    packages=["mlagents.envs", "mlagents.envs.communicator_objects"],  # Required
    zip_safe=False,
    install_requires=[
        "Pillow>=5.4.1",
        "numpy>=1.16.1",
        "pytest>=3.2.2",
        "protobuf>=3.6",
        "grpcio>=1.11.0",
        "cloudpickle",
    ],
    python_requires="==3.6",
)
