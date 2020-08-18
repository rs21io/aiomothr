import setuptools

setuptools.setup(
    name='aiomothr',
    version='1.2.4',
    author='James Arnold',
    author_email='james@rs21.io',
    description='Asynchronous client library for interacting with MOTHR',
    packages=setuptools.find_packages(),
    include_package_data=True,
    install_requires=[
        'aioredis',
        'gql==3.0.0a1',
        'mothrpy>=1.3.0',
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
        'Operating System :: OS Independent'
    ]
)
