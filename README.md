# Vedro Dev

[![PyPI](https://img.shields.io/pypi/v/vedro-dev.svg?style=flat-square)](https://pypi.python.org/pypi/vedro-dev/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/vedro-dev?style=flat-square)](https://pypi.python.org/pypi/vedro-dev/)
[![Python Version](https://img.shields.io/pypi/pyversions/vedro-dev.svg?style=flat-square)](https://pypi.python.org/pypi/vedro-dev/)

## Installation

### 1. Install package

```shell
$ pip3 install vedro-dev
```

### 2. Enable plugin

```python
# ./vedro.cfg.py
import vedro
import vedro_dev

class Config(vedro.Config):

    class Plugins(vedro.Config.Plugins):

        class VedroDev(vedro_dev.VedroDev):
            enabled = True

```

# Usage

```shell
$ vedro run --dev -r silent
```
