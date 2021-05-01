from setuptools import setup

setup(
    name='adatrap_miner',
    version='0.1',
    py_modules=['adatrap_miner'],
    install_requires=[
        'Click',
    ],
    entry_points='''
        [console_scripts]
        adatrap_miner=adatrap_miner:cli
    ''',
)