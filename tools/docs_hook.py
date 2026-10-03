"""Rebuild generated inventories in the disposable source tree during preview."""

import os

from tools.docs import prepare


def on_config(config):
    repository = os.environ.get("GITHUB_REPOSITORY")
    if repository:
        owner, name = repository.split("/")
        config.repo_url = "https://github.com/" + repository
        config.site_url = f"https://{owner}.github.io/{name}/"
    return config


def on_pre_build(config):
    prepare()
