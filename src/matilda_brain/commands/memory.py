"""Memory management commands."""

import click
from rich.console import Console
from rich.table import Table

from ..memory_client import get_memory, MemoryClient

console = Console()


@click.group(name="memory")
def memory_group():
    """Manage agent memory and knowledge."""
    pass


@memory_group.command(name="status")
def status_command():
    """Check memory service status."""
    client = get_memory()
    if isinstance(client, MemoryClient) and client.is_available():
        console.print("[green]✅ Memory Service is ONLINE[/green]")
        console.print(f"URL: {client.base_url}")
    else:
        console.print("[red]❌ Memory Service is OFFLINE[/red]")
        console.print("Run 'cargo run -p matilda-memory' to start it.")


@memory_group.command(name="search")
@click.argument("query")
@click.option("--agent", default="assistant", help="Agent name to search")
def search_command(query: str, agent: str):
    """Search knowledge base."""
    client = get_memory(agent_name=agent)

    # We need to manually access query since the protocol doesn't expose it fully if we used get_memory factory which returns abstract protocol
    # But get_memory returns MemoryClient if available.

    if not hasattr(client, "query"):
        console.print("[red]Memory service unavailable[/red]")
        return

    results = client.query(agent, query)

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    table = Table(title=f"Search Results: '{query}'")
    table.add_column("Score", style="cyan", width=8)
    table.add_column("Type", style="magenta", width=12)
    table.add_column("Path", style="blue")
    table.add_column("Snippet")

    for res in results:
        table.add_row(f"{res.relevance:.2f}", res.type, res.path, res.content[:100].replace("\n", " ") + "...")

    console.print(table)


@memory_group.command(name="add")
@click.argument("path")
@click.argument("content")
@click.option("--agent", default="assistant", help="Agent name")
def add_command(path: str, content: str, agent: str):
    """Add knowledge manually."""
    client = get_memory(agent_name=agent)
    if client.add_knowledge(agent, path, content, commit_message="Manual addition via CLI"):
        console.print(f"[green]✅ Added {path} to {agent}'s vault[/green]")
    else:
        console.print("[red]❌ Failed to add knowledge[/red]")
