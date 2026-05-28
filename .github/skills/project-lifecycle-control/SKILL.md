---
name: project-lifecycle-control
description: 启动或关闭 Smart Appointment AI Agent 项目。当用户说启动、运行、打开、开启、开始、关闭、停止、退出、结束、关掉项目，或要求打开/关闭项目前端页面时使用。
---

# Project Lifecycle Control

## Purpose

Use this skill to control the local Smart Appointment AI Agent project lifecycle in this workspace.

## When To Use

- Start the project when the user asks to 启动、运行、打开、开启、开始项目.
- Stop the project when the user asks to 关闭、停止、退出、结束、关掉项目.
- Open the browser to the local front-end page after startup.
- Close the browser tab or page after shutdown when the browser tooling supports it; otherwise navigate the page to about:blank.

## Start Workflow

1. Treat the workspace root as the project root unless the user points to another folder.
2. Use the project entry in [app.py](app.py) and start it from the workspace root with `python app.py`.
3. Wait until the server is ready before opening the browser.
4. Open the front-end page at `http://127.0.0.1:8001/`.
5. If the root page is unavailable, report the startup error instead of guessing another URL.

## Stop Workflow

1. Reuse the terminal session that started the app when it is still available.
2. Send `Ctrl+C` to stop the running server.
3. If the process does not exit cleanly, terminate the terminal session.
4. Close the browser page for this project after the server stops, or navigate it to `about:blank` if close is not available.

## Operating Rules

- Do not edit project files as part of start/stop actions.
- Do not start duplicate servers if the project is already running.
- Keep the response short and state the final project URL or shutdown status clearly.
