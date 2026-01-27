"""
LangGraph integration for Fleet API.
Demonstrates how to use Fleet API as LangGraph tool nodes.
"""

from typing import TypedDict, Annotated, Sequence, Literal, Optional, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool
import asyncio

from fleet_client import create_fleet_client
from models import LabelCreate, PolicyCreate


# Define the agent state
class AgentState(TypedDict):
    """State for the Fleet management agent."""
    messages: Sequence[BaseMessage]
    current_action: Optional[str]
    result: Optional[str]


# Create Fleet API tools for LangGraph
@tool
async def list_fleet_hosts(
    page: int = 0,
    per_page: int = 10
) -> str:
    """
    List hosts in Fleet.
    
    Args:
        page: Page number (default: 0)
        per_page: Results per page (default: 10)
    
    Returns:
        JSON string with host information
    """
    client = create_fleet_client()
    try:
        hosts = await client.list_hosts(page=page, per_page=per_page)
        result = {
            "total": len(hosts),
            "hosts": [
                {
                    "id": host.id,
                    "hostname": host.hostname,
                    "platform": host.platform,
                    "status": host.status
                }
                for host in hosts
            ]
        }
        return str(result)
    except Exception as e:
        return f"Error listing hosts: {str(e)}"


@tool
async def get_fleet_host_details(host_id: int) -> str:
    """
    Get detailed information about a specific host.
    
    Args:
        host_id: The ID of the host to retrieve
    
    Returns:
        JSON string with detailed host information
    """
    client = create_fleet_client()
    try:
        host = await client.get_host(host_id)
        result = {
            "id": host.id,
            "hostname": host.hostname,
            "display_name": host.display_name,
            "platform": host.platform,
            "os_version": host.os_version,
            "status": host.status,
            "primary_ip": host.primary_ip,
            "primary_mac": host.primary_mac,
            "uptime": host.uptime,
            "memory": host.memory
        }
        return str(result)
    except Exception as e:
        return f"Error getting host details: {str(e)}"


@tool
async def run_fleet_query(
    query: str,
    host_ids: Optional[List[int]] = None
) -> str:
    """
    Execute a live query on Fleet hosts.
    
    Args:
        query: SQL query to execute (e.g., "SELECT * FROM processes")
        host_ids: Optional list of host IDs to target
    
    Returns:
        JSON string with query campaign information
    """
    client = create_fleet_client()
    try:
        result = await client.run_query(query=query, host_ids=host_ids)
        return str({
            "campaign_id": result.campaign_id,
            "query_id": result.query_id,
            "status": "Query initiated successfully"
        })
    except Exception as e:
        return f"Error running query: {str(e)}"


@tool
async def create_fleet_label(
    name: str,
    query: str,
    description: str = "",
    platform: Optional[str] = None
) -> str:
    """
    Create a new label in Fleet.
    
    Args:
        name: Label name
        query: SQL query to define the label
        description: Optional description
        platform: Optional platform filter (darwin, windows, linux)
    
    Returns:
        JSON string with created label information
    """
    client = create_fleet_client()
    try:
        label = LabelCreate(
            name=name,
            description=description,
            query=query,
            platform=platform
        )
        result = await client.create_label(label)
        return str({
            "id": result.id,
            "name": result.name,
            "query": result.query,
            "host_count": result.host_count
        })
    except Exception as e:
        return f"Error creating label: {str(e)}"


@tool
async def create_fleet_policy(
    name: str,
    query: str,
    description: str = "",
    resolution: str = "",
    critical: bool = False
) -> str:
    """
    Create a new policy in Fleet.
    
    Args:
        name: Policy name
        query: SQL query to define the policy
        description: Optional description
        resolution: Optional resolution steps
        critical: Whether the policy is critical
    
    Returns:
        JSON string with created policy information
    """
    client = create_fleet_client()
    try:
        policy = PolicyCreate(
            name=name,
            description=description,
            query=query,
            resolution=resolution,
            critical=critical
        )
        result = await client.create_policy(policy)
        return str({
            "id": result.id,
            "name": result.name,
            "critical": result.critical,
            "passing_host_count": result.passing_host_count,
            "failing_host_count": result.failing_host_count
        })
    except Exception as e:
        return f"Error creating policy: {str(e)}"


@tool
async def list_fleet_teams() -> str:
    """
    List all teams in Fleet.
    
    Returns:
        JSON string with team information
    """
    client = create_fleet_client()
    try:
        teams = await client.list_teams()
        result = {
            "total": len(teams),
            "teams": [
                {
                    "id": team.id,
                    "name": team.name,
                    "description": team.description,
                    "user_count": team.user_count,
                    "host_count": team.host_count
                }
                for team in teams
            ]
        }
        return str(result)
    except Exception as e:
        return f"Error listing teams: {str(e)}"


# Create a list of all Fleet tools
FLEET_TOOLS = [
    list_fleet_hosts,
    get_fleet_host_details,
    run_fleet_query,
    create_fleet_label,
    create_fleet_policy,
    list_fleet_teams
]


def create_fleet_agent_graph():
    """
    Create a LangGraph StateGraph for Fleet management.
    
    Returns:
        Compiled StateGraph ready for execution
    """
    # Create tool node
    tool_node = ToolNode(FLEET_TOOLS)
    
    # Define the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    
    # Add edges
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "tools",
            "end": END
        }
    )
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()


def agent_node(state: AgentState) -> AgentState:
    """
    Agent node that decides what action to take.
    This is a simplified example - in practice, you'd use an LLM here.
    """
    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    # Simple decision logic (replace with LLM in production)
    if isinstance(last_message, HumanMessage):
        if "list hosts" in last_message.content.lower():
            state["current_action"] = "list_hosts"
        elif "get host" in last_message.content.lower():
            state["current_action"] = "get_host"
        elif "run query" in last_message.content.lower():
            state["current_action"] = "run_query"
        else:
            state["current_action"] = "complete"
    
    return state


def should_continue(state: AgentState) -> Literal["continue", "end"]:
    """Determine if the agent should continue or end."""
    current_action = state.get("current_action")
    
    if current_action == "complete" or not current_action:
        return "end"
    return "continue"


# Example usage function
async def example_fleet_agent_usage():
    """
    Example of using Fleet tools in a LangGraph agent.
    """
    print("Fleet LangGraph Agent Example")
    print("=" * 50)
    
    # Example 1: List hosts
    print("\n1. Listing hosts...")
    result = await list_fleet_hosts(page=0, per_page=5)
    print(f"Result: {result}")
    
    # Example 2: Get host details
    print("\n2. Getting host details...")
    result = await get_fleet_host_details(host_id=1)
    print(f"Result: {result}")
    
    # Example 3: Run a query
    print("\n3. Running a query...")
    result = await run_fleet_query(
        query="SELECT * FROM system_info",
        host_ids=[1, 2]
    )
    print(f"Result: {result}")
    
    # Example 4: Create a label
    print("\n4. Creating a label...")
    result = await create_fleet_label(
        name="Ubuntu Hosts",
        query="SELECT 1 FROM os_version WHERE platform = 'ubuntu'",
        description="All Ubuntu hosts"
    )
    print(f"Result: {result}")
    
    # Example 5: List teams
    print("\n5. Listing teams...")
    result = await list_fleet_teams()
    print(f"Result: {result}")
    
    print("\n" + "=" * 50)
    print("All examples completed!")


if __name__ == "__main__":
    # Run the example
    asyncio.run(example_fleet_agent_usage())
