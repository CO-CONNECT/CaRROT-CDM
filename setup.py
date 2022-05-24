import setuptools
import os
import sys

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open('requirements.txt') as f:
    required = f.read().splitlines()


sys.path.append("coconnect/")
from _version import __version__ as version

    
setuptools.setup(
    name="co-connect-tools", 
    author="CO-CONNECT",
    version=version,
    author_email="CO-CONNECT@dundee.ac.uk",
    description="Python package for performing mapping of ETL to CDM ",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/CO-CONNECT/co-connect-tools",
    entry_points = {
        'console_scripts':[
            'carrot=coconnect.cli.cli:coconnect',
            'etltool=coconnect.cli.subcommands.run:map',
            'etl-gui=coconnect.cli.subcommands.run:gui',
        ],
    },
    packages=setuptools.find_packages(),
    extras_require = {
        'airflow':['apache-airflow'],
        'performance':['snakeviz'],
    },
    install_requires=required,
    package_data={'coconnect': ['data/cdm/*','data/example/*/*','data/test/*/*','data/test/*/*/*']},
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
