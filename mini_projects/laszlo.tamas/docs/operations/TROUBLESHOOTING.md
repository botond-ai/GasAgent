# Troubleshooting Guide - Knowledge Router

## Mit csinál (felhasználói nézőpont)

Komprehenzív hibaelhárítási útmutató a leggyakoribb problémákhoz. Systematic debugging approach, log analysis és performance optimization technikákkal.

## Használat

### Gyors diagnosztika
```bash
# System health check
curl http://localhost:8000/health/

# Service status
docker-compose ps

# Log analysis
docker-compose logs --tail=100 backend | grep ERROR

# Database connection test
docker exec -it knowledge-router-postgres psql -U user -d k_r_
```

### Performance debugging
```bash
# Memory usage
docker stats knowledge-router-backend

# API response times
curl -w "@curl-format.txt" -s http://localhost:8000/api/chat/

# Database query analysis
docker exec -it knowledge-router-postgres psql -U user -d k_r_ -c "SELECT * FROM pg_stat_activity;"
```

### Common fixes
```bash
# Reset containers
docker-compose down -v && docker-compose up --build

# Clear vector store
docker volume rm knowledge-router_qdrant-storage

# Database migration fix
docker-compose exec backend python database/migrate.py
```

## Technikai implementáció

### Health Check System
```python
# health/health_checker.py
import asyncio
import time
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client import QdrantClient
import redis
import openai

class HealthChecker:
    """Comprehensive system health monitoring."""
    
    def __init__(self, db_session: AsyncSession, qdrant_client: QdrantClient, redis_client: redis.Redis):
        self.db_session = db_session
        self.qdrant_client = qdrant_client
        self.redis_client = redis_client
    
    async def check_all_services(self) -> Dict[str, Any]:
        """Check all service health statuses."""
        
        health_status = {
            "overall": "unknown",
            "timestamp": time.time(),
            "services": {}
        }
        
        # Run all checks concurrently
        checks = await asyncio.gather(
            self._check_database(),
            self._check_vector_store(),
            self._check_cache(),
            self._check_llm_api(),
            return_exceptions=True
        )
        
        service_names = ["database", "vector_store", "cache", "llm_api"]
        
        for service_name, result in zip(service_names, checks):
            if isinstance(result, Exception):
                health_status["services"][service_name] = {
                    "status": "unhealthy",
                    "error": str(result),
                    "response_time_ms": None
                }
            else:
                health_status["services"][service_name] = result
        
        # Determine overall health
        unhealthy_services = [
            name for name, status in health_status["services"].items()
            if status["status"] != "healthy"
        ]
        
        if not unhealthy_services:
            health_status["overall"] = "healthy"
        elif len(unhealthy_services) <= 1:
            health_status["overall"] = "degraded"
        else:
            health_status["overall"] = "unhealthy"
            
        health_status["unhealthy_services"] = unhealthy_services
        
        return health_status
    
    async def _check_database(self) -> Dict[str, Any]:
        """Check PostgreSQL database health."""
        start_time = time.time()
        
        try:
            # Test basic connectivity
            result = await self.db_session.execute("SELECT 1")
            await result.fetchone()
            
            # Test table access
            await self.db_session.execute("SELECT COUNT(*) FROM tenants")
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "details": "Database connectivity verified"
            }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "unhealthy",
                "response_time_ms": round(response_time, 2),
                "error": f"Database error: {str(e)}"
            }
    
    async def _check_vector_store(self) -> Dict[str, Any]:
        """Check Qdrant vector store health."""
        start_time = time.time()
        
        try:
            # Test Qdrant connectivity
            collections = await self.qdrant_client.get_collections()
            
            # Test collection access if exists
            if collections.collections:
                collection_name = collections.collections[0].name
                await self.qdrant_client.get_collection(collection_name)
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "details": f"Vector store accessible, {len(collections.collections)} collections"
            }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "unhealthy",
                "response_time_ms": round(response_time, 2),
                "error": f"Vector store error: {str(e)}"
            }
    
    async def _check_cache(self) -> Dict[str, Any]:
        """Check Redis cache health."""
        start_time = time.time()
        
        try:
            # Test Redis connectivity
            await asyncio.get_event_loop().run_in_executor(
                None, self.redis_client.ping
            )
            
            # Test read/write
            test_key = "health_check_test"
            await asyncio.get_event_loop().run_in_executor(
                None, self.redis_client.set, test_key, "test_value", 10
            )
            
            value = await asyncio.get_event_loop().run_in_executor(
                None, self.redis_client.get, test_key
            )
            
            if value != b"test_value":
                raise Exception("Redis read/write test failed")
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "details": "Cache read/write operations successful"
            }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "unhealthy", 
                "response_time_ms": round(response_time, 2),
                "error": f"Cache error: {str(e)}"
            }
    
    async def _check_llm_api(self) -> Dict[str, Any]:
        """Check OpenAI LLM API health."""
        start_time = time.time()
        
        try:
            # Test OpenAI API with minimal request
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
                timeout=5
            )
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "details": f"LLM API responsive, model: {response.model}"
            }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "unhealthy",
                "response_time_ms": round(response_time, 2),
                "error": f"LLM API error: {str(e)}"
            }
```

### Common Issue Diagnostics
```python
# troubleshooting/diagnostics.py
import psutil
import docker
import requests
import asyncio
from typing import Dict, List, Any

class SystemDiagnostics:
    """System diagnostics and troubleshooting utilities."""
    
    def __init__(self):
        self.docker_client = docker.from_env()
    
    def diagnose_performance_issues(self) -> Dict[str, Any]:
        """Diagnose common performance bottlenecks."""
        
        diagnostics = {
            "system_resources": self._check_system_resources(),
            "container_status": self._check_container_status(),
            "database_performance": self._check_database_performance(),
            "api_response_times": self._check_api_response_times()
        }
        
        # Analyze and provide recommendations
        diagnostics["recommendations"] = self._generate_recommendations(diagnostics)
        
        return diagnostics
    
    def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage."""
        
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
            "network_io": psutil.net_io_counters()._asdict()
        }
    
    def _check_container_status(self) -> List[Dict[str, Any]]:
        """Check Docker container statuses."""
        
        containers = []
        
        for container in self.docker_client.containers.list(all=True):
            containers.append({
                "name": container.name,
                "status": container.status,
                "image": container.image.tags[0] if container.image.tags else "unknown",
                "created": container.attrs["Created"],
                "ports": container.ports,
                "resource_usage": self._get_container_stats(container)
            })
        
        return containers
    
    def _get_container_stats(self, container) -> Dict[str, Any]:
        """Get container resource usage stats."""
        
        try:
            stats = container.stats(stream=False)
            
            # Calculate CPU percentage
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                       stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                          stats['precpu_stats']['system_cpu_usage']
            
            cpu_percent = 0.0
            if system_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * 100.0
            
            # Memory usage
            memory_usage = stats['memory_stats']['usage']
            memory_limit = stats['memory_stats']['limit']
            memory_percent = (memory_usage / memory_limit) * 100.0
            
            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_usage_mb": round(memory_usage / 1024 / 1024, 2),
                "memory_percent": round(memory_percent, 2)
            }
            
        except Exception as e:
            return {"error": f"Failed to get stats: {str(e)}"}
    
    def _check_database_performance(self) -> Dict[str, Any]:
        """Check database performance metrics."""
        
        try:
            # Connect to database and run diagnostics
            # This would need actual database connection
            return {
                "active_connections": "check_needed",
                "slow_queries": "check_needed", 
                "index_usage": "check_needed",
                "table_sizes": "check_needed"
            }
            
        except Exception as e:
            return {"error": f"Database diagnostics failed: {str(e)}"}
    
    def _check_api_response_times(self) -> Dict[str, Any]:
        """Check API endpoint response times."""
        
        endpoints = [
            "/health/",
            "/api/chat/",
            "/docs"
        ]
        
        response_times = {}
        
        for endpoint in endpoints:
            try:
                import time
                start_time = time.time()
                response = requests.get(f"http://localhost:8000{endpoint}", timeout=10)
                end_time = time.time()
                
                response_times[endpoint] = {
                    "response_time_ms": round((end_time - start_time) * 1000, 2),
                    "status_code": response.status_code,
                    "status": "healthy" if response.status_code < 400 else "unhealthy"
                }
                
            except Exception as e:
                response_times[endpoint] = {
                    "error": str(e),
                    "status": "unhealthy"
                }
        
        return response_times
    
    def _generate_recommendations(self, diagnostics: Dict[str, Any]) -> List[str]:
        """Generate troubleshooting recommendations."""
        
        recommendations = []
        
        # Check system resources
        resources = diagnostics["system_resources"]
        
        if resources["cpu_percent"] > 80:
            recommendations.append("High CPU usage detected. Consider scaling up or optimizing workflow performance.")
        
        if resources["memory_percent"] > 85:
            recommendations.append("High memory usage detected. Check for memory leaks or increase container memory limits.")
        
        if resources["disk_usage"] > 90:
            recommendations.append("Disk space running low. Clean up logs or increase storage capacity.")
        
        # Check container status
        unhealthy_containers = [
            c for c in diagnostics["container_status"] 
            if c["status"] not in ["running", "restarting"]
        ]
        
        if unhealthy_containers:
            container_names = [c["name"] for c in unhealthy_containers]
            recommendations.append(f"Unhealthy containers detected: {', '.join(container_names)}. Restart containers.")
        
        # Check API response times
        slow_endpoints = [
            endpoint for endpoint, data in diagnostics["api_response_times"].items()
            if data.get("response_time_ms", 0) > 5000
        ]
        
        if slow_endpoints:
            recommendations.append(f"Slow API endpoints detected: {', '.join(slow_endpoints)}. Check database or LLM API performance.")
        
        return recommendations
```

### Error Analysis Tools
```python
# troubleshooting/error_analyzer.py
import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from collections import Counter, defaultdict

class ErrorAnalyzer:
    """Analyze application logs for error patterns."""
    
    def __init__(self, log_file_path: str):
        self.log_file_path = log_file_path
        
    def analyze_recent_errors(self, hours: int = 24) -> Dict[str, Any]:
        """Analyze errors from the last N hours."""
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        errors = self._extract_errors(cutoff_time)
        
        return {
            "total_errors": len(errors),
            "error_types": self._categorize_errors(errors),
            "error_patterns": self._find_error_patterns(errors),
            "affected_tenants": self._get_affected_tenants(errors),
            "time_distribution": self._get_time_distribution(errors),
            "recommendations": self._get_error_recommendations(errors)
        }
    
    def _extract_errors(self, cutoff_time: datetime) -> List[Dict[str, Any]]:
        """Extract error entries from log file."""
        
        errors = []
        
        try:
            with open(self.log_file_path, 'r') as f:
                for line in f:
                    try:
                        log_entry = json.loads(line)
                        
                        # Check if error level
                        if log_entry.get('severity') not in ['ERROR', 'CRITICAL']:
                            continue
                        
                        # Check timestamp
                        timestamp_str = log_entry.get('timestamp')
                        if timestamp_str:
                            log_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            if log_time < cutoff_time:
                                continue
                        
                        errors.append(log_entry)
                        
                    except json.JSONDecodeError:
                        # Handle non-JSON log lines
                        if 'ERROR' in line or 'CRITICAL' in line:
                            errors.append({'raw_message': line.strip()})
                            
        except FileNotFoundError:
            return []
        
        return errors
    
    def _categorize_errors(self, errors: List[Dict[str, Any]]) -> Dict[str, int]:
        """Categorize errors by type."""
        
        categories = defaultdict(int)
        
        for error in errors:
            message = error.get('message', error.get('raw_message', ''))
            
            # Database errors
            if any(db_keyword in message.lower() for db_keyword in ['database', 'postgresql', 'connection']):
                categories['database'] += 1
            
            # LLM API errors  
            elif any(llm_keyword in message.lower() for llm_keyword in ['openai', 'api', 'rate limit']):
                categories['llm_api'] += 1
            
            # Vector store errors
            elif any(vs_keyword in message.lower() for vs_keyword in ['qdrant', 'vector', 'embedding']):
                categories['vector_store'] += 1
            
            # Workflow errors
            elif any(wf_keyword in message.lower() for wf_keyword in ['workflow', 'node', 'langgraph']):
                categories['workflow'] += 1
            
            # Authentication/Authorization
            elif any(auth_keyword in message.lower() for auth_keyword in ['auth', 'permission', 'unauthorized']):
                categories['authentication'] += 1
            
            else:
                categories['other'] += 1
        
        return dict(categories)
    
    def _find_error_patterns(self, errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find recurring error patterns."""
        
        message_patterns = Counter()
        
        for error in errors:
            message = error.get('message', error.get('raw_message', ''))
            
            # Extract error pattern (remove specific values)
            pattern = re.sub(r'\d+', '[NUMBER]', message)
            pattern = re.sub(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', '[UUID]', pattern)
            pattern = re.sub(r'\b\w+@\w+\.\w+\b', '[EMAIL]', pattern)
            
            message_patterns[pattern] += 1
        
        # Return top 10 patterns
        return [
            {"pattern": pattern, "count": count}
            for pattern, count in message_patterns.most_common(10)
        ]
    
    def _get_affected_tenants(self, errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get tenants affected by errors."""
        
        tenant_errors = Counter()
        
        for error in errors:
            tenant_id = error.get('tenant_id')
            if tenant_id:
                tenant_errors[str(tenant_id)] += 1
        
        return [
            {"tenant_id": tenant_id, "error_count": count}
            for tenant_id, count in tenant_errors.most_common(10)
        ]
    
    def _get_time_distribution(self, errors: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get error distribution by hour."""
        
        hourly_errors = defaultdict(int)
        
        for error in errors:
            timestamp_str = error.get('timestamp')
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    hour_key = timestamp.strftime('%Y-%m-%d %H:00')
                    hourly_errors[hour_key] += 1
                except:
                    continue
        
        return dict(hourly_errors)
    
    def _get_error_recommendations(self, errors: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on error analysis."""
        
        recommendations = []
        
        # Analyze error patterns for recommendations
        error_types = self._categorize_errors(errors)
        
        if error_types.get('database', 0) > 10:
            recommendations.append("High number of database errors. Check connection pool settings and database performance.")
        
        if error_types.get('llm_api', 0) > 5:
            recommendations.append("LLM API errors detected. Check rate limits and API key validity.")
        
        if error_types.get('vector_store', 0) > 5:
            recommendations.append("Vector store issues detected. Verify Qdrant connectivity and collection configuration.")
        
        if error_types.get('authentication', 0) > 0:
            recommendations.append("Authentication errors present. Check API keys and tenant configurations.")
        
        return recommendations
```

## Funkció-specifikus konfiguráció

```ini
# Troubleshooting settings
ENABLE_DETAILED_LOGGING=true
LOG_RETENTION_HOURS=168  # 7 days
ERROR_ANALYSIS_ENABLED=true

# Health check intervals
HEALTH_CHECK_INTERVAL_SECONDS=30
DEEP_HEALTH_CHECK_INTERVAL_MINUTES=5

# Performance monitoring
PERFORMANCE_MONITORING_ENABLED=true
SLOW_QUERY_THRESHOLD_MS=1000
HIGH_MEMORY_THRESHOLD_PERCENT=85

# Alerting thresholds
ERROR_RATE_ALERT_THRESHOLD=5  # errors per minute
RESPONSE_TIME_ALERT_THRESHOLD_MS=5000
```

### Quick Fix Scripts
```bash
#!/bin/bash
# troubleshooting/quick-fixes.sh

case "$1" in
  "reset-containers")
    echo "Resetting all containers..."
    docker-compose down -v
    docker-compose up -d --build
    ;;
    
  "clear-cache")
    echo "Clearing Redis cache..."
    docker exec knowledge-router-redis redis-cli FLUSHALL
    ;;
    
  "restart-backend")
    echo "Restarting backend service..."
    docker-compose restart backend
    ;;
    
  "check-logs")
    echo "Recent error logs:"
    docker-compose logs --tail=50 backend | grep -E "(ERROR|CRITICAL)"
    ;;
    
  "database-status")
    echo "Database connection status:"
    docker exec knowledge-router-postgres pg_isready -U user -d k_r_
    ;;
    
  *)
    echo "Usage: $0 {reset-containers|clear-cache|restart-backend|check-logs|database-status}"
    ;;
esac
```