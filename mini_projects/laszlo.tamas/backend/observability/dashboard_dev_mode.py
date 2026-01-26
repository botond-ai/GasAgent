"""
Dashboard Dev Mode - Instant Queries for Development

Automatically switches Grafana dashboards between dev and prod query modes
based on system.ini GRAFANA_DASHBOARD_MODE setting.

MODES:
- dev:  Instant queries (llm_requests_total) - immediate feedback
- prod: Rate queries (rate(llm_requests_total[1m])) - requires scrape history

CÉLJA: Frissen scrape-elt metrikák esetén a rate() query üres,
mert nincs elég történeti adat. Ezt átalakítja instant query-kre.
"""
import json
import re
import sys
from pathlib import Path

# Add parent directory to path for config imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config_service import get_config_value


DASHBOARD_PATH = Path(__file__).parent.parent.parent / "monitoring" / "grafana" / "provisioning" / "dashboards" / "prometheus-ai-metrics.json"

# Mapping: rate() -> instant query (DEV MODE)
DEV_QUERY_REPLACEMENTS = {
    # LLM Requests
    'rate(llm_requests_total[1m])': 'llm_requests_total',
    
    # Token Usage (rate-ről instant összegre)
    'rate(llm_tokens_total{direction="prompt"}[1m])': 'llm_tokens_total{direction="prompt"}',
    'rate(llm_tokens_total{direction="completion"}[1m])': 'llm_tokens_total{direction="completion"}',
    
    # Cost (hourly rate helyett total)
    'sum(rate(llm_cost_usd_total[1m])) * 3600': 'llm_cost_usd_total',
    
    # Tool Invocations
    'rate(tool_invocations_total[1m])': 'tool_invocations_total',
    
    # Error Rate (százalék helyett nyers counter)
    '(rate(errors_total[1m]) / rate(llm_requests_total[1m])) * 100': 'errors_total',
    
    # Cost increase
    'sum(increase(llm_cost_usd_total[30m])) by (model)': 'sum(llm_cost_usd_total) by (model)',
}

# Mapping: instant query -> rate() (PROD MODE - reversal)
PROD_QUERY_REPLACEMENTS = {v: k for k, v in DEV_QUERY_REPLACEMENTS.items()}


def get_dashboard_mode() -> str:
    """Get dashboard mode from system.ini."""
    mode = get_config_value("observability", "GRAFANA_DASHBOARD_MODE", "dev")
    if isinstance(mode, str):
        return mode.lower()
    return "dev"


def convert_dashboard_queries(target_mode: str = None):
    """
    Konvertálja a dashboard-ot dev vagy prod mode-ra.
    
    Args:
        target_mode: 'dev' vagy 'prod'. Ha None, akkor system.ini-ből olvassa.
    """
def convert_dashboard_queries(target_mode: str = None):
    """
    Konvertálja a dashboard-ot dev vagy prod mode-ra.
    
    Args:
        target_mode: 'dev' vagy 'prod'. Ha None, akkor system.ini-ből olvassa.
    """
    
    # Read target mode from system.ini if not specified
    if target_mode is None:
        target_mode = get_dashboard_mode()
    
    if target_mode not in ("dev", "prod"):
        print(f"❌ Invalid mode: {target_mode}. Must be 'dev' or 'prod'")
        return False
    
    # Select appropriate replacements
    if target_mode == "dev":
        replacements = DEV_QUERY_REPLACEMENTS
        mode_name = "DEV MODE (instant queries)"
    else:
        replacements = PROD_QUERY_REPLACEMENTS
        mode_name = "PROD MODE (rate queries)"
    
    if not DASHBOARD_PATH.exists():
        print(f"❌ Dashboard not found: {DASHBOARD_PATH}")
        return False
    
    with open(DASHBOARD_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    replacements_made = 0
    
    for old_query, new_query in replacements.items():
        escaped_old = re.escape(old_query)
        count = len(re.findall(escaped_old, content))
        if count > 0:
            content = content.replace(old_query, new_query)
            replacements_made += count
            print(f"✅ '{old_query}' → '{new_query}' ({count}x)")
    
    if replacements_made == 0:
        print(f"ℹ️  Dashboard already in {mode_name} (no replacements needed)")
        return True
    
    # Backup
    backup_path = DASHBOARD_PATH.with_suffix('.json.backup')
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(original_content)
    print(f"💾 Backup: {backup_path}")
    
    # Write new version
    with open(DASHBOARD_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n✅ Dashboard converted to {mode_name} ({replacements_made} queries updated)")
    print(f"ℹ️  system.ini: GRAFANA_DASHBOARD_MODE={target_mode}")
    print("ℹ️  Restart Grafana: docker-compose restart grafana")
    
    return True


if __name__ == "__main__":
    # Support command-line override: python -m observability.dashboard_dev_mode prod
    import sys
    target_mode = sys.argv[1] if len(sys.argv) > 1 else None
    convert_dashboard_queries(target_mode)
