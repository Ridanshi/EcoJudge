"""Exposes the read-side of the control loop (metrics, errors, carbon signal) as MCP
tools. This satisfies the hackathon's 'MCP Server or custom agentic tools' requirement
literally; the actual debate loop (Tasks 5-7) uses direct function calls for speed and
determinism -- see the architecture doc for why."""
from mcp.server.fastmcp import FastMCP

from src.carbon_signal import carbon_level
from src.ep_bridge import get_block_metrics, get_errors

app = FastMCP(name="eco-loop-building-agents")


@app.tool()
def get_zone_metrics(out_dir: str, zone_name: str = "SPACE1-1") -> dict:
    """Return per-time-block avg zone temp/RH/PMV and kWh from a completed EnergyPlus run directory."""
    return get_block_metrics(out_dir, zone_name)


@app.tool()
def get_simulation_errors(out_dir: str) -> list:
    """Return any severe/fatal error lines from a completed EnergyPlus run's .err file."""
    return get_errors(out_dir)


@app.tool()
def get_carbon_signal(hour_of_day: int) -> str:
    """Return the mocked grid carbon-intensity level ('low'/'medium'/'high') for an hour 0-23."""
    return carbon_level(hour_of_day)


if __name__ == "__main__":
    app.run(transport="stdio")
