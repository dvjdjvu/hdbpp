#!/usr/bin/env python3
#encoding: UTF-8

from setuptools import setup, find_packages

PACKAGE = "hdbpp"
NAME = "hdbpp"
DESCRIPTION = "TANGO HDB++ python"
AUTHOR = "dvjdvju"
AUTHOR_EMAIL = "djvu@inbox.ru"
URL = ""
VERSION = __import__(PACKAGE).__version__

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    license="BSD",
    url=URL,
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
    ],
    zip_safe=False,
    include_package_data=True,
    python_requires='>=3.6',
    install_request=["mysql-connector>=2.2.9", "pytango>=9.3.2"]
)
