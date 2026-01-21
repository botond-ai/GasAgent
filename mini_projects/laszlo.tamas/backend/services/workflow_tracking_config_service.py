"""
Workflow Tracking Configuration Service

Runtime-configurable node-level tracking with tenant-level granularity.

Features:
- 3 tracking levels: OFF, METADATA_ONLY, FULL_STATE
- Tenant-level override (all users in tenant)
- Temporary override (auto-revert after N hours)
- Selective node filtering
- In-memory cache with expiration handling

Hierarchy:
- Tenant config > System default

Usage:
```python
from services.workflow_tracking_config_service import workflow_tracking_config_service

# Check if tracking enabled
should_track, level = workflow_tracking_config_service.should_track_node(
    tenant_id=1,
    node_name="agent_decide"
)

if should_track and level == "FULL_STATE":
    # Store full state snapshot
    pass
```
"""

from typing import Optional, Literal
from datetime import datetime, timedelta
from database.pg_connection import get_db_connection
import logging

TrackingLevel = Literal["OFF", "METADATA_ONLY", "FULL_STATE"]

logger = logging.getLogger(__name__)


class WorkflowTrackingConfigService:
    """
    Manages runtime-configurable node-level tracking.
    
    Cache: In-memory dict (invalidated on config change or expiration)
    Hierarchy: Tenant config > System default
    """
    
    def __init__(self):
        self._cache: dict = {}  # {tenant_id: config_dict}
        self._system_default: Optional[dict] = None
    
    def get_tracking_config(self, tenant_id: int) -> dict:
        """
        Get effective tracking config for tenant.
        
        Returns:
            {
                "enabled": bool,
                "level": "OFF" | "METADATA_ONLY" | "FULL_STATE",
                "tracked_nodes": list[str] | None,
                "is_override": bool,
                "override_expires_at": str | None
            }
        """
        # Check cache
        if tenant_id in self._cache:
            cached = self._cache[tenant_id]
            logger.info(f"[get_tracking_config] CACHE HIT for tenant={tenant_id}: {cached}")
            # Check if override expired
            if cached.get("override_expires_at"):
                try:
                    if datetime.fromisoformat(cached["override_expires_at"]) < datetime.utcnow():
                        # Expired, invalidate cache
                        del self._cache[tenant_id]
                        logger.info(f"🕒 Tracking override expired for tenant_id={tenant_id}")
                    else:
                        return cached
                except (ValueError, TypeError):
                    # Invalid timestamp, invalidate
                    del self._cache[tenant_id]
            else:
                return cached
        
        logger.info(f"[get_tracking_config] CACHE MISS for tenant={tenant_id}, fetching from DB...")
        # Fetch from DB
        config = self._fetch_config_from_db(tenant_id)
        self._cache[tenant_id] = config
        logger.info(f"[get_tracking_config] CACHED new config for tenant={tenant_id}: {config}")
        return config
    
    def _fetch_config_from_db(self, tenant_id: int) -> dict:
        """Fetch from DB with tenant > system hierarchy."""
        try:
            logger.info(f"[CONFIG_FETCH] START for tenant_id={tenant_id}")
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Try tenant-specific config first
                    cur.execute("""
                        SELECT 
                            node_tracking_enabled,
                            node_tracking_level,
                            tracked_nodes,
                            override_until
                        FROM workflow_tracking_config
                        WHERE config_type = 'tenant' AND tenant_id = %s
                        LIMIT 1
                    """, (tenant_id,))
                    
                    tenant_config = cur.fetchone()
                    logger.info(f"[CONFIG_FETCH] tenant_config={tenant_config}")
                    
                    if tenant_config:
                        # Use column names instead of index (RealDictRow doesn't support integer indexing)
                        override_until = tenant_config['override_until']
                        is_override = override_until is not None and override_until > datetime.utcnow()
                        
                        try:
                            result = {
                                "enabled": bool(tenant_config['node_tracking_enabled']),
                                "level": str(tenant_config['node_tracking_level']),
                                "tracked_nodes": tenant_config['tracked_nodes'],
                                "is_override": is_override,
                                "override_expires_at": override_until.isoformat() if override_until else None
                            }
                            logger.info(f"[CONFIG_FETCH] returning tenant config: {result}")
                            return result
                        except Exception as e:
                            logger.error(f"[CONFIG_FETCH] ERROR creating result dict: {e}", exc_info=True)
                            raise
                    
                    # Fallback to system default
                    if not self._system_default:
                        cur.execute("""
                            SELECT 
                                node_tracking_enabled,
                                node_tracking_level,
                                tracked_nodes
                            FROM workflow_tracking_config
                            WHERE config_type = 'system'
                            LIMIT 1
                        """)
                        system_config = cur.fetchone()
                        
                        if system_config:
                            self._system_default = {
                                "enabled": system_config['node_tracking_enabled'],
                                "level": system_config['node_tracking_level'],
                                "tracked_nodes": system_config['tracked_nodes'],
                                "is_override": False,
                                "override_expires_at": None
                            }
                        else:
                            # Hardcoded fallback
                            logger.warning("⚠️ System default config not found, using hardcoded fallback")
                            self._system_default = {
                                "enabled": True,
                                "level": "METADATA_ONLY",
                                "tracked_nodes": None,
                                "is_override": False,
                                "override_expires_at": None
                            }
                    
                    return self._system_default.copy()
                    
        except Exception as e:
            logger.error(f"❌ Failed to fetch tracking config: {e}", exc_info=True)
            # Safe fallback
            return {
                "enabled": False,
                "level": "OFF",
                "tracked_nodes": None,
                "is_override": False,
                "override_expires_at": None
            }
    
    def set_tenant_tracking_level(
        self,
        tenant_id: int,
        level: TrackingLevel,
        duration_hours: Optional[int] = None,
        tracked_nodes: Optional[list[str]] = None
    ) -> bool:
        """
        Set tenant-specific tracking level.
        
        Args:
            tenant_id: Tenant identifier
            level: OFF | METADATA_ONLY | FULL_STATE
            duration_hours: If set, revert after N hours (temporary override)
            tracked_nodes: Optional filter (e.g. ["agent_decide", "search"])
        
        Returns:
            bool: Success status
        """
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                override_until = None
                if duration_hours:
                    override_until = datetime.utcnow() + timedelta(hours=duration_hours)
                
                enabled = level != "OFF"
                
                # Convert list to JSONB format
                tracked_nodes_json = tracked_nodes if tracked_nodes else None
                
                cur.execute("""
                    INSERT INTO workflow_tracking_config (
                        config_type, tenant_id, 
                        node_tracking_enabled, node_tracking_level,
                        tracked_nodes, override_until, updated_at
                    ) VALUES (
                        'tenant', %s,
                        %s, %s,
                        %s, %s, NOW()
                    )
                    ON CONFLICT (config_type, tenant_id)
                    DO UPDATE SET
                        node_tracking_enabled = EXCLUDED.node_tracking_enabled,
                        node_tracking_level = EXCLUDED.node_tracking_level,
                        tracked_nodes = EXCLUDED.tracked_nodes,
                        override_until = EXCLUDED.override_until,
                        updated_at = NOW()
                """, (
                    tenant_id, 
                    enabled, 
                    level, 
                    tracked_nodes_json, 
                    override_until
                ))
                
                conn.commit()
                
                # Invalidate cache
                if tenant_id in self._cache:
                    del self._cache[tenant_id]
                
                duration_msg = f"{duration_hours}h" if duration_hours else "permanent"
                nodes_msg = f"nodes={tracked_nodes}" if tracked_nodes else "all nodes"
                logger.info(
                    f"✅ Updated tracking config: tenant={tenant_id}, level={level}, "
                    f"duration={duration_msg}, {nodes_msg}"
                )
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to set tracking config: {e}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    def should_track_node(self, tenant_id: int, node_name: str) -> tuple[bool, TrackingLevel]:
        """
        Check if node should be tracked.
        
        Returns:
            (should_track: bool, level: TrackingLevel)
        """
        config = self.get_tracking_config(tenant_id)
        logger.info(f"[should_track_node] tenant={tenant_id}, node={node_name}, config={config}")
        
        if not config["enabled"]:
            logger.info(f"[should_track_node] DISABLED for {node_name}")
            return False, "OFF"
        
        # Check node filter
        tracked_nodes = config.get("tracked_nodes")
        if tracked_nodes and node_name not in tracked_nodes:
            logger.info(f"[should_track_node] FILTERED OUT: {node_name} not in {tracked_nodes}")
            return False, config["level"]
        
        logger.info(f"[should_track_node] ENABLED for {node_name}, level={config['level']}")
        return True, config["level"]
    
    def reset_tenant_config(self, tenant_id: int) -> bool:
        """
        Reset tenant to system default (remove tenant override).
        
        Args:
            tenant_id: Tenant identifier
        
        Returns:
            bool: Success status
        """
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM workflow_tracking_config
                    WHERE config_type = 'tenant' AND tenant_id = %s
                """, (tenant_id,))
                conn.commit()
            
            # Invalidate cache
            if tenant_id in self._cache:
                del self._cache[tenant_id]
            
            logger.info(f"✅ Reset tracking config for tenant_id={tenant_id} to system default")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to reset tracking config: {e}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    def get_system_default(self) -> dict:
        """Get system default config."""
        if not self._system_default:
            # Trigger fetch
            self.get_tracking_config(tenant_id=1)
        return self._system_default.copy() if self._system_default else {}
    
    def invalidate_cache(self, tenant_id: Optional[int] = None):
        """
        Invalidate cache (after config change).
        
        Args:
            tenant_id: If None, clear all cache
        """
        if tenant_id:
            if tenant_id in self._cache:
                del self._cache[tenant_id]
                logger.debug(f"🔄 Cache invalidated for tenant_id={tenant_id}")
        else:
            self._cache.clear()
            self._system_default = None
            logger.debug("🔄 Full cache invalidated")


# Singleton instance
workflow_tracking_config_service = WorkflowTrackingConfigService()
