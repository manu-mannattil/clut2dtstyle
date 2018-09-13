#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import setup

setup(
    name="clut2dtstyle",
    license="Unlicense",
    version="0.1",
    author="Manu Mannattil",
    author_email="manu.mannattil@gmail.com",
    description="Script to convert Hald CLUTs to darktable styles",
    py_modules=["clut2dtstyle"],
    install_requires=["numpy>=1.11.0"],
    classifiers=[
        "License :: Public Domain",
        "Programming Language :: Python :: 3",
        "Topic :: Multimedia :: Graphics"
    ],
    entry_points="""
        [console_scripts]
        clut2dtstyle=clut2dtstyle:main
    """
)
