"""
Database migration runner for knowledge_router.

Automatically applies all SQL migrations from database/migrations/ folder.
Migrations are executed in alphabetical order (use numbered prefixes: 001_, 002_, etc.)

Usage:
    python -m database.run_migrations
"""
import os
import logging
from pathlib import Path
from database.pg_connection import get_db_connection

logger = logging.getLogger(__name__)


def get_migrations_folder() -> Path:
    """Get path to migrations folder."""
    current_file = Path(__file__)
    migrations_folder = current_file.parent / "migrations"
    return migrations_folder


def get_migration_files() -> list[Path]:
    """Get all SQL migration files sorted by name."""
    migrations_folder = get_migrations_folder()
    
    if not migrations_folder.exists():
        logger.warning(f"Migrations folder not found: {migrations_folder}")
        return []
    
    sql_files = sorted(migrations_folder.glob("*.sql"))
    return sql_files


def has_migration_been_applied(cursor, filename: str) -> bool:
    """Check if a migration has already been applied."""
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM applied_migrations 
            WHERE filename = %s
        ) as exists
    """, (filename,))
    result = cursor.fetchone()
    return result['exists'] if result else False


def record_migration(cursor, filename: str):
    """Record that a migration has been applied."""
    cursor.execute("""
        INSERT INTO applied_migrations (filename, applied_at)
        VALUES (%s, NOW())
    """, (filename,))


def init_migrations_table():
    """Create applied_migrations tracking table if it doesn't exist."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS applied_migrations (
                    id SERIAL PRIMARY KEY,
                    filename TEXT NOT NULL UNIQUE,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            conn.commit()
            logger.info("✅ Migrations tracking table ready")


def run_migrations():
    """
    Run all pending SQL migrations.
    
    Migrations are applied in alphabetical order.
    Already-applied migrations are skipped automatically.
    """
    # Ensure tracking table exists
    init_migrations_table()
    
    # Get all migration files
    migration_files = get_migration_files()
    
    if not migration_files:
        logger.info("📭 No migration files found")
        return
    
    logger.info(f"📦 Found {len(migration_files)} migration file(s)")
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            applied_count = 0
            skipped_count = 0
            
            for migration_file in migration_files:
                filename = migration_file.name
                
                # Check if already applied
                if has_migration_been_applied(cursor, filename):
                    logger.info(f"⏭️  Skipping {filename} (already applied)")
                    skipped_count += 1
                    continue
                
                # Read and execute migration
                logger.info(f"🔄 Applying migration: {filename}")
                
                try:
                    sql_content = migration_file.read_text(encoding='utf-8')
                    cursor.execute(sql_content)
                    
                    # Record success
                    record_migration(cursor, filename)
                    conn.commit()
                    
                    logger.info(f"✅ Successfully applied: {filename}")
                    applied_count += 1
                    
                except Exception as e:
                    conn.rollback()
                    logger.error(f"❌ Failed to apply {filename}: {e}", exc_info=True)
                    raise RuntimeError(f"Migration failed: {filename}") from e
            
            # Summary
            logger.info(f"\n📊 Migration Summary:")
            logger.info(f"   ✅ Applied: {applied_count}")
            logger.info(f"   ⏭️  Skipped: {skipped_count}")
            logger.info(f"   📦 Total: {len(migration_files)}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        run_migrations()
        print("\n🎉 All migrations completed successfully!")
    except Exception as e:
        print(f"\n💥 Migration failed: {e}")
        exit(1)
