from setuptools import setup, find_packages
import os, sys

with open("README.md", "r", encoding="utf-8") as fh:
  long_description = fh.read()
  print (long_description)
cwd = os.getcwd()
os.system(f'ls {cwd}')

sys.path.append("carrotlite/")
from _version import __version__ as version

setup(
  name='carrot-cdm-lite',
  version=version,
  author_email="pdappleby@gmail.com",
  description="Python package for mapping data partner data to the OMOP CDM",
  long_description=long_description,
  long_description_content_type="text/markdown",
  url="https://github.com/HDRUK/CaRROT-CDM-Lite",
  entry_points = {
    'console_scripts':[
    'carrotlite=carrotlite.clilite.clilite:carrotlite'
    ],
  },
  packages=find_packages(),
  install_requires=[
    "click"
  ],
  classifiers=[
    "Programming Language :: Python :: 3",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
  ],
  python_requires='>=3.6',
)

