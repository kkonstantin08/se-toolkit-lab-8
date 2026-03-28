"""Stdio MCP server exposing observability tools for VictoriaLogs and VictoriaTraces."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field

server = Server("observability")

# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class _LogsSearchQuery(BaseModel):
    query: str = Field(
        default="",
        description="LogsQL query string. Use filters like `_stream:{service.name=\"backend\"}` and `severity:ERROR`.",
    )
    limit: int = Field(default=30, ge=1, le=1000, description="Max log entries to return (default 30).")
    start: str = Field(
        default="-1h",
        description="Start time for the query. Use relative time like '-1h', '-30m', or absolute RFC3339.",
    )


class _LogsErrorCountQuery(BaseModel):
    service: str = Field(default="", description="Filter by service name. Leave empty for all services.")
    window: str = Field(default="-1h", description="Time window for counting errors (e.g., '-1h', '-24h').")


class _TracesListQuery(BaseModel):
    service: str = Field(default="", description="Filter by service name. Leave empty for all services.")
    limit: int = Field(default=10, ge=1, le=100, description="Max traces to return (default 10).")


class _TracesGetQuery(BaseModel):
    trace_id: str = Field(description="The trace ID to fetch.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _victorialogs_url() -> str:
    """Get VictoriaLogs base URL from environment."""
    url = os.environ.get("VICTORIALOGS_URL", "").strip()
    if url:
        return url.rstrip("/")
    # Default to Docker service name when running inside Docker
    return "http://victorialogs:9428"


def _victoriatraces_url() -> str:
    """Get VictoriaTraces base URL from environment."""
    url = os.environ.get("VICTORIATRACES_URL", "").strip()
    if url:
        return url.rstrip("/")
    # Default to Docker service name when running inside Docker
    return "http://victoriatraces:10428"


def _text(data: BaseModel | Sequence[BaseModel] | dict | list) -> list[TextContent]:
    """Serialize data to a JSON text block."""
    if isinstance(data, BaseModel):
        payload = data.model_dump()
    elif isinstance(data, (dict, list)):
        payload = data
    else:
        payload = [item.model_dump() if isinstance(item, BaseModel) else item for item in data]
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


def _text_summary(summary: str, data: BaseModel | Sequence[BaseModel] | dict | list) -> list[TextContent]:
    """Return a text summary followed by JSON data."""
    if isinstance(data, BaseModel):
        payload = data.model_dump()
    elif isinstance(data, (dict, list)):
        payload = data
    else:
        payload = [item.model_dump() if isinstance(item, BaseModel) else item for item in data]
    return [
        TextContent(type="text", text=summary),
        TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2)),
    ]


# ---------------------------------------------------------------------------
# VictoriaLogs tool handlers
# ---------------------------------------------------------------------------


async def _logs_search(args: _LogsSearchQuery) -> list[TextContent]:
    """Search logs using VictoriaLogs LogsQL query."""
    base_url = _victorialogs_url()
    url = f"{base_url}/select/logsql/query"
    
    # Build query - if no query provided, search for everything in the time range
    query = args.query if args.query else f"_time:{args.start}"
    
    params = {
        "query": query,
        "limit": str(args.limit),
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            # VictoriaLogs returns newline-delimited JSON (streaming format)
            content = response.text.strip()
            if not content:
                return _text_summary("No logs found matching your query.", [])
            
            # Parse newline-delimited JSON
            logs = []
            for line in content.split('\n'):
                if line.strip():
                    try:
                        logs.append(json.loads(line))
                    except json.JSONDecodeError:
                        logs.append({"raw": line})
            
            if not logs:
                return _text_summary("No logs found matching your query.", [])
            
            return _text_summary(f"Found {len(logs)} log entries:", logs)
            
        except httpx.ConnectError as e:
            return _text_summary(f"Error: Cannot connect to VictoriaLogs at {base_url}", {"error": str(e)})
        except httpx.HTTPStatusError as e:
            return _text_summary(f"Error: HTTP {e.response.status_code}", {"error": e.response.text})
        except Exception as e:
            return _text_summary(f"Error: {type(e).__name__}", {"error": str(e)})


async def _logs_error_count(args: _LogsErrorCountQuery) -> list[TextContent]:
    """Count errors per service over a time window."""
    base_url = _victorialogs_url()
    url = f"{base_url}/select/logsql/query"

    # Build LogsQL query for errors
    # VictoriaLogs uses 'severity' field, not 'level'
    if args.service:
        query = f"_stream:{{service.name=\"{args.service}\"}} AND severity:ERROR _time:{args.window}"
    else:
        query = f"severity:ERROR _time:{args.window}"

    params = {
        "query": query,
        "limit": "1000",  # Get up to 1000 entries to count
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            # VictoriaLogs returns newline-delimited JSON
            content = response.text.strip()
            
            logs = []
            if content:
                for line in content.split('\n'):
                    if line.strip():
                        try:
                            logs.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass

            # Count errors by service
            error_count = len(logs)
            by_service: dict[str, int] = {}
            for log in logs:
                if isinstance(log, dict):
                    service = log.get("service.name", log.get("_stream", {}).get("service.name", "unknown"))
                    by_service[service] = by_service.get(service, 0) + 1

            result = {
                "total_errors": error_count,
                "time_window": args.window,
                "by_service": by_service,
            }

            if error_count == 0:
                return _text_summary(f"No errors found in the last time window ({args.window}).", result)

            return _text_summary(f"Found {error_count} error(s) in {args.window}:", result)

        except httpx.ConnectError as e:
            return _text_summary(f"Error: Cannot connect to VictoriaLogs at {base_url}", {"error": str(e)})
        except httpx.HTTPStatusError as e:
            return _text_summary(f"Error: HTTP {e.response.status_code}", {"error": e.response.text})
        except Exception as e:
            return _text_summary(f"Error: {type(e).__name__}", {"error": str(e)})


# ---------------------------------------------------------------------------
# VictoriaTraces tool handlers
# ---------------------------------------------------------------------------


async def _traces_list(args: _TracesListQuery) -> list[TextContent]:
    """List recent traces for a service."""
    base_url = _victoriatraces_url()
    # VictoriaTraces Jaeger-compatible API
    url = f"{base_url}/select/jaeger/api/traces"
    
    params = {
        "limit": str(args.limit),
    }
    if args.service:
        params["service"] = args.service
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Jaeger API returns {"data": [...]}
            traces = data.get("data", [])
            
            if not traces:
                return _text_summary("No traces found.", [])
            
            # Simplify trace info for display
            trace_summaries = []
            for trace in traces[:args.limit]:
                summary = {
                    "trace_id": trace.get("traceID", "unknown"),
                    "spans": len(trace.get("spans", [])),
                    "start_time": trace.get("startTime", "unknown"),
                    "duration_ms": trace.get("duration", 0),
                }
                # Find service name from spans
                for span in trace.get("spans", []):
                    for tag in span.get("tags", []):
                        if tag.get("key") == "service.name":
                            summary["service"] = tag.get("value", "unknown")
                            break
                    if "service" in summary:
                        break
                trace_summaries.append(summary)
            
            return _text_summary(f"Found {len(trace_summaries)} recent trace(s):", trace_summaries)
            
        except httpx.ConnectError as e:
            return _text_summary(f"Error: Cannot connect to VictoriaTraces at {base_url}", {"error": str(e)})
        except httpx.HTTPStatusError as e:
            return _text_summary(f"Error: HTTP {e.response.status_code}", {"error": e.response.text})
        except Exception as e:
            return _text_summary(f"Error: {type(e).__name__}", {"error": str(e)})


async def _traces_get(args: _TracesGetQuery) -> list[TextContent]:
    """Fetch a specific trace by ID."""
    base_url = _victoriatraces_url()
    url = f"{base_url}/select/jaeger/api/traces/{args.trace_id}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Jaeger API returns {"data": [...]}
            traces = data.get("data", [])
            
            if not traces:
                return _text_summary(f"Trace {args.trace_id} not found.", [])
            
            trace = traces[0]
            
            # Build span hierarchy summary
            spans_info = []
            for span in trace.get("spans", []):
                span_info = {
                    "span_id": span.get("spanID", "unknown"),
                    "operation_name": span.get("operationName", "unknown"),
                    "service": None,
                    "duration_ms": span.get("duration", 0),
                    "tags": {},
                }
                # Extract service name and error info from tags
                for tag in span.get("tags", []):
                    key = tag.get("key", "")
                    value = tag.get("value", "")
                    if key == "service.name":
                        span_info["service"] = value
                    elif key in ("error", "error.message", "error.object"):
                        span_info["tags"][key] = value
                
                spans_info.append(span_info)
            
            result = {
                "trace_id": trace.get("traceID", args.trace_id),
                "duration_ms": trace.get("duration", 0),
                "start_time": trace.get("startTime", "unknown"),
                "spans": spans_info,
            }
            
            return _text_summary(f"Trace {args.trace_id}:", result)
            
        except httpx.ConnectError as e:
            return _text_summary(f"Error: Cannot connect to VictoriaTraces at {base_url}", {"error": str(e)})
        except httpx.HTTPStatusError as e:
            return _text_summary(f"Error: HTTP {e.response.status_code}", {"error": e.response.text})
        except Exception as e:
            return _text_summary(f"Error: {type(e).__name__}", {"error": str(e)})


# ---------------------------------------------------------------------------
# Registry: tool name -> (input model, handler, Tool definition)
# ---------------------------------------------------------------------------

_Registry = tuple[type[BaseModel], Callable[..., Awaitable[list[TextContent]]], Tool]

_TOOLS: dict[str, _Registry] = {}


def _register(
    name: str,
    description: str,
    model: type[BaseModel],
    handler: Callable[..., Awaitable[list[TextContent]]],
) -> None:
    schema = model.model_json_schema()
    schema.pop("$defs", None)
    schema.pop("title", None)
    _TOOLS[name] = (
        model,
        handler,
        Tool(name=name, description=description, inputSchema=schema),
    )


_register(
    "logs_search",
    "Search logs in VictoriaLogs using LogsQL. Use for finding errors, debugging issues, or auditing events. "
    "Example query: '_stream:{service=\"backend\"} AND level:error' to find backend errors.",
    _LogsSearchQuery,
    _logs_search,
)

_register(
    "logs_error_count",
    "Count errors per service over a time window. Use for quick health checks or finding which service has errors.",
    _LogsErrorCountQuery,
    _logs_error_count,
)

_register(
    "traces_list",
    "List recent traces. Use to see request flow through services or find traces for a specific service.",
    _TracesListQuery,
    _traces_list,
)

_register(
    "traces_get",
    "Fetch a specific trace by ID. Use to inspect the full span hierarchy and find where errors occurred.",
    _TracesGetQuery,
    _traces_get,
)


# ---------------------------------------------------------------------------
# MCP handlers
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [entry[2] for entry in _TOOLS.values()]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    entry = _TOOLS.get(name)
    if entry is None:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    model_cls, handler, _ = entry
    try:
        args = model_cls.model_validate(arguments or {})
        return await handler(args)
    except Exception as exc:
        return [TextContent(type="text", text=f"Error: {type(exc).__name__}: {exc}")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        init_options = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    asyncio.run(main())
