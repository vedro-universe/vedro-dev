from vedro.core import Plugin

from vedro_dev import VedroDev, VedroDevPlugin


def test_dev():
    plugin = VedroDevPlugin(VedroDev)
    assert isinstance(plugin, Plugin)
