import setuptools

with open("README.md") as f:
    long_description = f.read()

setuptools.setup(
    name="aiomothr",
    version="0.2.1",
    author="James Arnold",
    author_email="james@rs21.io",
    description="Asynchronous client library for interacting with MOTHR",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    include_package_data=True,
    install_requires=[
        "gql[aiohttp,websockets]==3.0.0a4",
    ],
    extras_require={
        "dev": [
            "asynctest",
            "pytest",
            "pytest-asyncio",
            "pytest-cov",
            "pytest-mypy",
            "pytest-pylint",
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
