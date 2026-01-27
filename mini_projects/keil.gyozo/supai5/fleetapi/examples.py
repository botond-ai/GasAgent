"""
Example usage script for Fleet API Client.
Demonstrates various operations and best practices.
"""

import asyncio
from typing import List
from fleet_client import create_fleet_client
from models import LabelCreate, PolicyCreate, TeamCreate
from exceptions import (
    AuthenticationError,
    ResourceNotFoundError,
    ValidationError
)


async def example_authentication():
    """Example: Authentication operations."""
    print("\n" + "="*60)
    print("AUTHENTICATION EXAMPLES")
    print("="*60)
    
    client = create_fleet_client()
    
    try:
        # Login
        print("\n1. Logging in...")
        response = await client.login(
            email="admin@example.com",
            password="your-password"
        )
        print(f"✓ Login successful!")
        print(f"  User: {response.user.name}")
        print(f"  Role: {response.user.global_role}")
        print(f"  Token: {response.token[:20]}...")
        
        # Get current user
        print("\n2. Getting current user info...")
        user = await client.get_me()
        print(f"✓ Current user: {user.name} ({user.email})")
        
        # Logout
        print("\n3. Logging out...")
        await client.logout()
        print("✓ Logged out successfully")
        
    except AuthenticationError as e:
        print(f"✗ Authentication failed: {e.message}")
    except Exception as e:
        print(f"✗ Error: {str(e)}")


async def example_host_management():
    """Example: Host management operations."""
    print("\n" + "="*60)
    print("HOST MANAGEMENT EXAMPLES")
    print("="*60)
    
    client = create_fleet_client()
    
    try:
        # List hosts
        print("\n1. Listing hosts...")
        hosts = await client.list_hosts(page=0, per_page=5)
        print(f"✓ Found {len(hosts)} hosts:")
        for host in hosts[:3]:  # Show first 3
            print(f"  - {host.hostname} ({host.platform}) - {host.status}")
        
        if hosts:
            # Get specific host details
            host_id = hosts[0].id
            print(f"\n2. Getting details for host {host_id}...")
            host = await client.get_host(host_id)
            print(f"✓ Host details:")
            print(f"  Hostname: {host.hostname}")
            print(f"  Platform: {host.platform}")
            print(f"  OS Version: {host.os_version}")
            print(f"  Primary IP: {host.primary_ip}")
            print(f"  Status: {host.status}")
        
    except ResourceNotFoundError as e:
        print(f"✗ Resource not found: {e.message}")
    except Exception as e:
        print(f"✗ Error: {str(e)}")


async def example_query_execution():
    """Example: Query execution."""
    print("\n" + "="*60)
    print("QUERY EXECUTION EXAMPLES")
    print("="*60)
    
    client = create_fleet_client()
    
    try:
        # Run a simple query
        print("\n1. Running query on all hosts...")
        result = await client.run_query(
            query="SELECT * FROM system_info"
        )
        print(f"✓ Query initiated:")
        print(f"  Campaign ID: {result.campaign_id}")
        print(f"  Query ID: {result.query_id}")
        
        # Run query on specific hosts
        print("\n2. Running query on specific hosts...")
        result = await client.run_query(
            query="SELECT * FROM processes LIMIT 10",
            host_ids=[1, 2, 3]
        )
        print(f"✓ Query initiated on hosts [1, 2, 3]")
        print(f"  Campaign ID: {result.campaign_id}")
        
    except ValidationError as e:
        print(f"✗ Validation error: {e.message}")
    except Exception as e:
        print(f"✗ Error: {str(e)}")


async def example_label_management():
    """Example: Label management."""
    print("\n" + "="*60)
    print("LABEL MANAGEMENT EXAMPLES")
    print("="*60)
    
    client = create_fleet_client()
    
    try:
        # List existing labels
        print("\n1. Listing existing labels...")
        labels = await client.list_labels()
        print(f"✓ Found {len(labels)} labels:")
        for label in labels[:3]:  # Show first 3
            print(f"  - {label.name} ({label.host_count} hosts)")
        
        # Create a new label
        print("\n2. Creating a new label...")
        new_label = LabelCreate(
            name="Example Ubuntu Hosts",
            description="Hosts running Ubuntu",
            query="SELECT 1 FROM os_version WHERE platform = 'ubuntu'",
            platform="linux"
        )
        created = await client.create_label(new_label)
        print(f"✓ Label created:")
        print(f"  ID: {created.id}")
        print(f"  Name: {created.name}")
        print(f"  Type: {created.type}")
        
        # Clean up - delete the label we created
        print(f"\n3. Deleting label {created.id}...")
        await client.delete_label(created.id)
        print(f"✓ Label deleted")
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")


async def example_policy_management():
    """Example: Policy management."""
    print("\n" + "="*60)
    print("POLICY MANAGEMENT EXAMPLES")
    print("="*60)
    
    client = create_fleet_client()
    
    try:
        # List policies
        print("\n1. Listing policies...")
        policies = await client.list_policies()
        print(f"✓ Found {len(policies)} policies:")
        for policy in policies[:3]:  # Show first 3
            print(f"  - {policy.name} (Critical: {policy.critical})")
            print(f"    Passing: {policy.passing_host_count}, "
                  f"Failing: {policy.failing_host_count}")
        
        # Create a new policy
        print("\n2. Creating a new policy...")
        new_policy = PolicyCreate(
            name="Example Security Policy",
            description="Ensure firewall is enabled",
            query="SELECT 1 WHERE EXISTS (SELECT 1 FROM iptables WHERE policy = 'DROP')",
            resolution="Enable the firewall on affected systems",
            critical=True
        )
        created = await client.create_policy(new_policy)
        print(f"✓ Policy created:")
        print(f"  ID: {created.id}")
        print(f"  Name: {created.name}")
        print(f"  Critical: {created.critical}")
        
        # Clean up
        print(f"\n3. Deleting policy {created.id}...")
        await client.delete_policy(created.id)
        print(f"✓ Policy deleted")
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")


async def example_team_management():
    """Example: Team management."""
    print("\n" + "="*60)
    print("TEAM MANAGEMENT EXAMPLES")
    print("="*60)
    
    client = create_fleet_client()
    
    try:
        # List teams
        print("\n1. Listing teams...")
        teams = await client.list_teams()
        print(f"✓ Found {len(teams)} teams:")
        for team in teams[:3]:  # Show first 3
            print(f"  - {team.name}: {team.user_count} users, "
                  f"{team.host_count} hosts")
        
        # Create a new team
        print("\n2. Creating a new team...")
        new_team = TeamCreate(
            name="Example Engineering Team",
            description="Example team for demonstration"
        )
        created = await client.create_team(new_team)
        print(f"✓ Team created:")
        print(f"  ID: {created.id}")
        print(f"  Name: {created.name}")
        
        # Clean up
        print(f"\n3. Deleting team {created.id}...")
        await client.delete_team(created.id)
        print(f"✓ Team deleted")
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")


async def example_error_handling():
    """Example: Error handling patterns."""
    print("\n" + "="*60)
    print("ERROR HANDLING EXAMPLES")
    print("="*60)
    
    client = create_fleet_client()
    
    # Example 1: Handle authentication errors
    print("\n1. Handling authentication errors...")
    try:
        await client.login("wrong@email.com", "wrongpassword")
    except AuthenticationError as e:
        print(f"✓ Caught authentication error: {e.message}")
    
    # Example 2: Handle not found errors
    print("\n2. Handling resource not found errors...")
    try:
        await client.get_host(999999)
    except ResourceNotFoundError as e:
        print(f"✓ Caught not found error: {e.message}")
    
    # Example 3: Handle validation errors
    print("\n3. Handling validation errors...")
    try:
        invalid_label = LabelCreate(
            name="",  # Invalid: empty name
            query="SELECT 1",
            description=""
        )
        await client.create_label(invalid_label)
    except ValidationError as e:
        print(f"✓ Caught validation error: {e.message}")
    except Exception as e:
        print(f"✓ Caught error (validation or other): {str(e)}")


async def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("FLEET API CLIENT - USAGE EXAMPLES")
    print("="*60)
    print("\nNote: These examples require a running Fleet server")
    print("and valid credentials in your .env file")
    
    # Uncomment the examples you want to run:
    
    # await example_authentication()
    # await example_host_management()
    # await example_query_execution()
    # await example_label_management()
    # await example_policy_management()
    # await example_team_management()
    # await example_error_handling()
    
    print("\n" + "="*60)
    print("EXAMPLES COMPLETED")
    print("="*60)
    print("\nTip: Uncomment specific examples in main() to run them")


if __name__ == "__main__":
    asyncio.run(main())
