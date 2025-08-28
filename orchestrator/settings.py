from __future__ import annotations

import os

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables immediately when settings module is imported
# This ensures .env is loaded before any load_settings() calls
load_dotenv()


class ProviderCfg(BaseModel):
    mode: str  # "cli", "api", or "interactive"
    provider_type: str | None = (
        None  # "cli" or "api" - distinguishes between CLI tools and API providers
    )
    binary: str | None = None
    args: list[str] | None = None
    model: str | None = None
    available_models: list[str] | None = None  # List of available models for this provider
    max_tokens: int | None = None
    description: str | None = None


class Settings(BaseModel):
    repo_path: str
    dev_branch: str
    default_remote: str
    provider_order: list[str]
    full_access_order: list[str] | None = None
    providers: dict[str, ProviderCfg]
    checkpoint_minutes: int
    pr_minutes: int
    worktrees_base_dir: str
    roles: dict
    roles_dir: str
    full_access: dict | None = None


def load_settings() -> Settings:
    with open("config/config.yaml", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    repo = raw["repo"]
    providers = raw["providers"]
    hygiene = raw["hygiene"]
    worktrees = raw["worktrees"]

    prov_cfg = {
        name: ProviderCfg(**cfg)
        for name, cfg in providers.items()
        if name not in ["order", "full_access_order"]
    }

    return Settings(
        repo_path=os.path.expandvars(repo["path"]),
        dev_branch=os.path.expandvars(repo["dev_branch"]),
        default_remote=repo.get("default_remote", "origin"),
        provider_order=providers["order"],
        full_access_order=providers.get("full_access_order"),
        providers=prov_cfg,
        checkpoint_minutes=int(hygiene["checkpoint_minutes"]),
        pr_minutes=int(hygiene["pr_minutes"]),
        worktrees_base_dir=worktrees["base_dir"],
        roles=raw.get("roles", {}),
        roles_dir=raw.get("roles_dir", "roles"),
        full_access=raw.get("full_access", {}),
    )
