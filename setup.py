from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="cortex-ai",
    version="0.1.0",
    author="Cortex AI",
    author_email="contact@cortex-ai.com",
    description="A dual-model governance system for AI collaboration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cortex-ai/cortex",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "cortex=cortex.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)