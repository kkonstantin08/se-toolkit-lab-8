# Lab 8 — Report

Paste your checkpoint evidence below. Add screenshots as image files in the repo and reference them with `![description](path)`.

## Task 1A — Bare agent

<!-- Paste the agent's response to "What is the agentic loop?" and "What labs are available in our LMS?" -->

## Task 1B — Agent with LMS tools

<!-- Paste the agent's response to "What labs are available?" and "Describe the architecture of the LMS system" -->

## Task 1C — Skill prompt

<!-- Paste the agent's response to "Show me the scores" (without specifying a lab) -->

## Task 2A — Deployed agent

```text
nanobot-1  | Using config: /app/nanobot/config.resolved.json
nanobot-1  | Starting nanobot gateway version 0.1.4.post5 on port 18790...
nanobot-1  | 2026-03-28 08:01:48.327 | INFO     | nanobot.channels.manager:_init_channels:58 - WebChat channel enabled
nanobot-1  | Channels enabled: webchat
nanobot-1  | 2026-03-28 08:01:50.645 | INFO     | nanobot.agent.tools.mcp:connect_mcp_servers:246 - MCP server 'lms': connected, 9 tools registered
nanobot-1  | 2026-03-28 08:01:50.645 | INFO     | nanobot.agent.loop:run:280 - Agent loop started
```

<!-- Paste a short nanobot startup log excerpt showing the gateway started inside Docker -->

## Task 2B — Web client

Automated checks completed:

- `http://localhost:42002/flutter` returns `200 OK` and serves the Flutter app.
- WebSocket check through Caddy succeeded with `ws://localhost:42002/ws/chat?access_key=...`.

```json
{
  "type": "text",
  "content": "- Lab 01 – Products, Architecture & Roles\n- Lab 02 — Run, Fix, and Deploy a Backend Service\n- Lab 03 — Backend API: Explore, Debug, Implement, Deploy\n- Lab 04 — Testing, Front-end, and AI Agents\n- Lab 05 — Data Pipeline and Analytics Dashboard\n- Lab 06 — Build Your Own Agent\n- Lab 07 — Build a Client with an AI Coding Agent\n- lab-08",
  "format": "markdown"
}
```

Manual step still needed: add a screenshot of the Flutter chat after logging in with `NANOBOT_ACCESS_KEY`.

<!-- Screenshot of a conversation with the agent in the Flutter web app -->

## Task 3A — Structured logging

<!-- Paste happy-path and error-path log excerpts, VictoriaLogs query screenshot -->

## Task 3B — Traces

<!-- Screenshots: healthy trace span hierarchy, error trace -->

## Task 3C — Observability MCP tools

<!-- Paste agent responses to "any errors in the last hour?" under normal and failure conditions -->

## Task 4A — Multi-step investigation

<!-- Paste the agent's response to "What went wrong?" showing chained log + trace investigation -->

## Task 4B — Proactive health check

<!-- Screenshot or transcript of the proactive health report that appears in the Flutter chat -->

## Task 4C — Bug fix and recovery

<!-- 1. Root cause identified
     2. Code fix (diff or description)
     3. Post-fix response to "What went wrong?" showing the real underlying failure
     4. Healthy follow-up report or transcript after recovery -->
