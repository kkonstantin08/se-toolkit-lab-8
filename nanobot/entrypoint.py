import json
import os
from pathlib import Path


##import some constants
PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_DIR / "config.json"
RESOLVED_CONFIG_PATH = PROJECT_DIR / "config.resolved.json"
WORKSPACE_PATH = PROJECT_DIR / "workspace"


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


def resolve_config() -> Path:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    provider_name = config["agents"]["defaults"]["provider"]
    provider = config["providers"][provider_name]
    provider["apiKey"] = require_env("LLM_API_KEY")
    provider["apiBase"] = require_env("LLM_API_BASE_URL")
    config["agents"]["defaults"]["model"] = require_env("LLM_API_MODEL")

    gateway = config.setdefault("gateway", {})
    gateway["host"] = require_env("NANOBOT_GATEWAY_CONTAINER_ADDRESS")
    gateway["port"] = int(require_env("NANOBOT_GATEWAY_CONTAINER_PORT"))

    channels = config.setdefault("channels", {})
    webchat = channels.setdefault("webchat", {})
    webchat["enabled"] = True
    webchat["allow_from"] = webchat.get("allow_from", ["*"])
    webchat["host"] = require_env("NANOBOT_WEBCHAT_CONTAINER_ADDRESS")
    webchat["port"] = int(require_env("NANOBOT_WEBCHAT_CONTAINER_PORT"))
    require_env("NANOBOT_ACCESS_KEY")

    mcp_servers = config.setdefault("tools", {}).setdefault("mcpServers", {})
    lms_server = mcp_servers.setdefault("lms", {})
    backend_url = require_env("NANOBOT_LMS_BACKEND_URL")
    backend_api_key = require_env("NANOBOT_LMS_API_KEY")
    lms_server["args"] = ["-m", "mcp_lms", backend_url]
    lms_server.setdefault("env", {})
    lms_server["env"]["NANOBOT_LMS_BACKEND_URL"] = backend_url
    lms_server["env"]["NANOBOT_LMS_API_KEY"] = backend_api_key

    RESOLVED_CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return RESOLVED_CONFIG_PATH


def main() -> None:
    resolved_config = resolve_config()
    os.execvp(
        "nanobot",
        [
            "nanobot",
            "gateway",
            "--config",
            str(resolved_config),
            "--workspace",
            str(WORKSPACE_PATH),
        ],
    )


if __name__ == "__main__":
    main()
