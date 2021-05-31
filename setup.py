from setuptools import setup, find_packages

setup(
    name='adatrap_miner',
    version='1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Click',
    ],
    entry_points={
        'console_scripts': [
            "adatrap_miner = adatrap_miner.adatrap_miner:cli "]}
)
