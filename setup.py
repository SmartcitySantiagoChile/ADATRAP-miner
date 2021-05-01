from setuptools import setup

setup(
    name='miner',
    version='0.1',
    py_modules=['miner'],
    install_requires=[
        'Click',
    ],
    entry_points='''
        [console_scripts]
        miner=miner:cli
    ''',
)