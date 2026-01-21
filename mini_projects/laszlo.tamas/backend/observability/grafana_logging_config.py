"""
Grafana Logging Configuration Manager

Automatically updates docker-compose.yml with Grafana log level
based on system.ini GRAFANA_CONTINUOUS_LOGGING setting.

Usage:
    python -m observability.grafana_logging_config
    
Environment updates:
    - GRAFANA_CONTINUOUS_LOGGING=true  → GF_LOG_LEVEL=debug (verbose)
    - GRAFANA_CONTINUOUS_LOGGING=false → GF_LOG_LEVEL=error (minimal)
"""
import re
from pathlib import Path
import sys

# Add parent directory to path for config imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config_service import get_config_value


def update_grafana_log_level():
    """Update docker-compose.yml with Grafana log level from system.ini."""
    
    # Read configuration
    config_value = get_config_value(
        "observability", 
        "GRAFANA_CONTINUOUS_LOGGING", 
        "false"
    )
    
    # Handle both bool and string values
    if isinstance(config_value, bool):
        continuous_logging = config_value
    else:
        continuous_logging = str(config_value).lower() == "true"
    
    # Determine log level
    log_level = "debug" if continuous_logging else "error"
    
    # Find docker-compose.yml
    project_root = Path(__file__).parent.parent.parent
    docker_compose_path = project_root / "docker-compose.yml"
    
    if not docker_compose_path.exists():
        print(f"❌ docker-compose.yml not found at {docker_compose_path}")
        return False
    
    # Read file
    with open(docker_compose_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Update GF_LOG_LEVEL
    pattern = r'(- GF_LOG_LEVEL=)(debug|error|info|warn)'
    replacement = rf'\g<1>{log_level}'
    
    new_content, count = re.subn(pattern, replacement, content)
    
    if count == 0:
        print("❌ GF_LOG_LEVEL not found in docker-compose.yml")
        return False
    
    # Write back
    with open(docker_compose_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    mode = "ON (verbose)" if continuous_logging else "OFF (minimal)"
    print(f"✅ Grafana logging updated: {log_level.upper()} ({mode})")
    print(f"ℹ️  system.ini: GRAFANA_CONTINUOUS_LOGGING={str(continuous_logging).lower()}")
    print(f"ℹ️  Restart Grafana: docker-compose restart grafana")
    
    return True


if __name__ == "__main__":
    update_grafana_log_level()
