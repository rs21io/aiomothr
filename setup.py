import setuptools

setuptools.setup(
    name='aiomothr',
    version='0.1.2',
    author='James Arnold',
    author_email='james@rs21.io',
    description='Asynchronous client library for interacting with MOTHR',
    packages=setuptools.find_packages(),
    include_package_data=True,
    install_requires=[
        'aioredis',
        'gql==3.0.0a1',
        'mothrpy>=0.1.0',
    ],
    extras_require={
        'dev': [
            'asynctest',
            'pytest', 
            'pytest-asyncio',
            'pytest-cov',
            'pytest-mypy'
        ]
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent'
    ],
    python_requires='>=3.6'
)
