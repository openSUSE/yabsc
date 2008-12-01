#!/usr/bin/env python
from distutils.core import setup

long_description = "An openSUSE Build Service client that focuses on package build results"

setup(name             = "yabsc",
      version	       = "0.9.1",
      description      = "Yet Another Build Service Client",
      long_description = long_description,
      author           = "James Oakley",
      author_email     = "jfunk@opensuse.org",
      url              = "http://www.funktronics.ca/yabsc",
      license	       = "GPL",
      scripts          = ['yabsc'],
      packages         = ['yabsclib'],
     )
