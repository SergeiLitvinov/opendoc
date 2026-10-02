"""Rebuild generated inventories in the disposable source tree during preview."""

from tools.docs import prepare


def on_pre_build(config):
    prepare()
