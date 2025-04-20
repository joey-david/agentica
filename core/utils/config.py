
import yaml

def load_agent_config(agent_name: str) -> dict:
    config_path = f"agents/{agent_name}/config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)