"""Check existing PostgreSQL database structure."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database.pg_connection import get_db_connection

def check_tables():
    """List all tables and their structures."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        print("=" * 80)
        print("EXISTING TABLES IN DATABASE")
        print("=" * 80)
        
        if not tables:
            print("No tables found in database.")
            return
        
        for table in tables:
            table_name = table['table_name']
            print(f"\n📋 TABLE: {table_name}")
            print("-" * 80)
            
            # Get columns for this table
            cursor.execute("""
                SELECT 
                    column_name,
                    data_type,
                    character_maximum_length,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' 
                AND table_name = %s
                ORDER BY ordinal_position;
            """, (table_name,))
            
            columns = cursor.fetchall()
            
            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                data_type = col['data_type']
                if col['character_maximum_length']:
                    data_type += f"({col['character_maximum_length']})"
                
                default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                
                print(f"  - {col['column_name']:<30} {data_type:<20} {nullable:<10}{default}")
            
            # Get foreign keys
            cursor.execute("""
                SELECT
                    tc.constraint_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = %s;
            """, (table_name,))
            
            fkeys = cursor.fetchall()
            if fkeys:
                print("\n  FOREIGN KEYS:")
                for fk in fkeys:
                    print(f"    - {fk['column_name']} → {fk['foreign_table_name']}.{fk['foreign_column_name']}")
            
            # Get indexes
            cursor.execute("""
                SELECT
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE tablename = %s
                AND schemaname = 'public';
            """, (table_name,))
            
            indexes = cursor.fetchall()
            if indexes:
                print("\n  INDEXES:")
                for idx in indexes:
                    print(f"    - {idx['indexname']}")
        
        print("\n" + "=" * 80)
        print("END OF DATABASE STRUCTURE")
        print("=" * 80)

if __name__ == "__main__":
    try:
        check_tables()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
