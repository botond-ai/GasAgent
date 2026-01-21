"""
Grafana Dashboard Dynamic Configuration

Updates dashboard JSON files with configurable time windows from system.ini.

Usage:
    from observability.dashboard_config import update_dashboard_time_windows
    
    update_dashboard_time_windows()  # Updates all dashboards
"""

import json
import re
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


def get_time_windows() -> Dict[str, str]:
    """
    Get time window configuration from system.ini.
    
    Returns:
        Dict with 'rate_window' and 'cost_window' keys
    """
    try:
        from config.config_service import get_config_value
        
        return {
            "rate_window": get_config_value("observability", "GRAFANA_RATE_WINDOW", "1m"),
            "cost_window": get_config_value("observability", "GRAFANA_COST_WINDOW", "30m"),
        }
    except Exception as e:
        logger.warning(f"Failed to load time windows from config: {e}, using defaults")
        return {
            "rate_window": "1m",
            "cost_window": "30m",
        }


def update_dashboard_queries(dashboard: Dict[str, Any], time_windows: Dict[str, str]) -> Dict[str, Any]:
    """
    Update PromQL queries in dashboard with configured time windows.
    
    Args:
        dashboard: Dashboard JSON dict
        time_windows: Time window configuration
    
    Returns:
        Updated dashboard dict
    """
    rate_window = time_windows["rate_window"].strip()
    cost_window = time_windows["cost_window"].strip()
    
    # Convert dashboard to JSON string for regex replacement
    dashboard_str = json.dumps(dashboard, indent=2)
    
    # Replace rate() and histogram_quantile() time windows
    # Pattern: rate(...[5m]) or rate(...[1h]) → rate(...[1m])
    # Match only the time window part inside brackets
    dashboard_str = re.sub(
        r'(rate\([^[]+\[)[\dwmh]+(\])',
        rf'\g<1>{rate_window}\g<2>',
        dashboard_str
    )
    
    # Also update histogram_quantile patterns
    dashboard_str = re.sub(
        r'(histogram_quantile\([^[]+\[)[\dwmh]+(\])',
        rf'\g<1>{rate_window}\g<2>',
        dashboard_str
    )
    
    # Replace increase() time windows for cost queries
    # Pattern: increase(...[1h]) → increase(...[30m])
    dashboard_str = re.sub(
        r'(increase\(llm_cost_usd_total\[)[\dwmh]+(\])',
        rf'\g<1>{cost_window}\g<2>',
        dashboard_str
    )
    
    # Parse back to dict
    return json.loads(dashboard_str)


def update_dashboard_time_windows(dashboard_dir: str = None) -> int:
    """
    Update all Grafana dashboards with configured time windows.
    
    Args:
        dashboard_dir: Path to dashboard directory (default: auto-detect)
    
    Returns:
        Number of dashboards updated
    """
    if dashboard_dir is None:
        # Auto-detect dashboard directory (works in both container and host)
        project_root = Path(__file__).parent.parent.parent
        
        # Try multiple possible paths
        possible_paths = [
            project_root / "monitoring" / "grafana" / "provisioning" / "dashboards",  # Host
            Path("/app") / ".." / "monitoring" / "grafana" / "provisioning" / "dashboards",  # Container
            Path("/monitoring") / "grafana" / "provisioning" / "dashboards",  # Alternative
        ]
        
        for path in possible_paths:
            if path.exists():
                dashboard_dir = path
                break
        else:
            logger.error(f"Dashboard directory not found. Tried: {[str(p) for p in possible_paths]}")
            return 0
    else:
        dashboard_dir = Path(dashboard_dir)
    
    if not dashboard_dir.exists():
        logger.error(f"Dashboard directory not found: {dashboard_dir}")
        return 0
    
    time_windows = get_time_windows()
    logger.info(f"Updating dashboards with time windows: {time_windows}")
    
    updated_count = 0
    
    for dashboard_file in dashboard_dir.glob("*.json"):
        if dashboard_file.name == "dashboards.yml":
            continue
        
        try:
            # Load dashboard
            with open(dashboard_file, 'r', encoding='utf-8') as f:
                dashboard = json.load(f)
            
            # Update queries
            updated_dashboard = update_dashboard_queries(dashboard, time_windows)
            
            # Save updated dashboard
            with open(dashboard_file, 'w', encoding='utf-8') as f:
                json.dump(updated_dashboard, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Updated dashboard: {dashboard_file.name}")
            updated_count += 1
            
        except Exception as e:
            logger.error(f"❌ Failed to update {dashboard_file.name}: {e}")
    
    logger.info(f"✅ Updated {updated_count} dashboard(s)")
    return updated_count


def get_instant_query_for_counter(metric_name: str, filters: str = "") -> str:
    """
    Generate instant query for counter metrics (no rate()).
    
    For counter metrics, we can show the current value directly
    instead of rate of change.
    
    Args:
        metric_name: Metric name (e.g., "llm_requests_total")
        filters: Optional label filters (e.g., 'model="gpt-4o"')
    
    Returns:
        PromQL query string
    
    Examples:
        >>> get_instant_query_for_counter("llm_requests_total")
        'llm_requests_total'
        
        >>> get_instant_query_for_counter("llm_requests_total", 'model="gpt-4o"')
        'llm_requests_total{model="gpt-4o"}'
        
        >>> get_instant_query_for_counter("llm_cost_usd_total", filters='model=~".*"')
        'sum(llm_cost_usd_total{model=~".*"}) by (model)'
    """
    if filters:
        return f"{metric_name}{{{filters}}}"
    else:
        return metric_name


if __name__ == "__main__":
    # CLI usage: python -m observability.dashboard_config
    logging.basicConfig(level=logging.INFO)
    count = update_dashboard_time_windows()
    print(f"✅ Updated {count} dashboard(s)")
