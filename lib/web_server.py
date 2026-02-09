"""Web UI server for CCB dashboard."""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add lib to path
script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(script_dir))

try:
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from performance_tracker import PerformanceTracker
from response_cache import ResponseCache
from task_tracker import TaskTracker, TaskStatus

HANDLED_EXCEPTIONS = (Exception,)

def _emit(message: str, *, err: bool = False) -> None:
    stream = sys.stderr if err else sys.stdout
    stream.write(f"{message}\n")

def check_dependencies():
    """Check if required dependencies are installed."""
    if not HAS_FASTAPI:
        _emit("Error: FastAPI is not installed.", err=True)
        _emit("Install with: pip install fastapi uvicorn jinja2", err=True)
        return False
    return True

try:
    from .web_server_template import BASE_TEMPLATE
except ImportError:  # pragma: no cover - script mode
    from web_server_template import BASE_TEMPLATE

def create_app() -> "FastAPI":
    """Create and configure the FastAPI application."""
    if not HAS_FASTAPI:
        raise ImportError("FastAPI is required. Install with: pip install fastapi uvicorn")

    app = FastAPI(title="CCB Dashboard", version="1.0.0")

    # Initialize trackers
    perf_tracker = PerformanceTracker()
    cache = ResponseCache()
    task_tracker = TaskTracker()

    def render_page(content: str, active: str = "") -> str:
        """Render a page with the base template."""
        nav_classes = {
            "nav_home": "active" if active == "home" else "",
            "nav_tasks": "active" if active == "tasks" else "",
            "nav_stats": "active" if active == "stats" else "",
            "nav_cache": "active" if active == "cache" else "",
            "nav_ratelimit": "active" if active == "ratelimit" else "",
            "nav_health": "active" if active == "health" else "",
        }
        return BASE_TEMPLATE.format(content=content, **nav_classes)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        """Main dashboard page."""
        # Get summary stats
        perf_summary = perf_tracker.get_summary(hours=24)
        cache_stats = cache.get_stats()
        task_stats = task_tracker.get_stats()

        content = f"""
        <h2>Overview (Last 24 Hours)</h2>
        <div class="grid">
            <div class="card stat">
                <div class="stat-value">{perf_summary.get('total_requests', 0)}</div>
                <div class="stat-label">Total Requests</div>
            </div>
            <div class="card stat">
                <div class="stat-value">{perf_summary.get('overall_success_rate', 0)*100:.1f}%</div>
                <div class="stat-label">Success Rate</div>
            </div>
            <div class="card stat">
                <div class="stat-value">{cache_stats.total_entries}</div>
                <div class="stat-label">Cached Responses</div>
            </div>
            <div class="card stat">
                <div class="stat-value">{cache_stats.hit_rate*100:.1f}%</div>
                <div class="stat-label">Cache Hit Rate</div>
            </div>
        </div>

        <div class="card">
            <h2>Provider Performance</h2>
            <table>
                <tr>
                    <th>Provider</th>
                    <th>Requests</th>
                    <th>Success Rate</th>
                    <th>Avg Latency</th>
                </tr>
        """

        for p in perf_summary.get('providers', []):
            content += f"""
                <tr>
                    <td>{p['provider']}</td>
                    <td>{p['requests']}</td>
                    <td class="{'status-ok' if p['success_rate'] > 0.9 else 'status-fail'}">{p['success_rate']*100:.1f}%</td>
                    <td>{p['avg_latency_ms']:.0f}ms</td>
                </tr>
            """

        content += """
            </table>
        </div>

        <div class="card">
            <h2>Task Status</h2>
            <div class="grid">
        """

        for status, count in task_stats.items():
            status_class = "status-ok" if status == "completed" else ("status-fail" if status == "failed" else "status-pending")
            content += f"""
                <div class="stat">
                    <div class="stat-value {status_class}">{count}</div>
                    <div class="stat-label">{status.title()}</div>
                </div>
            """

        content += """
            </div>
        </div>
        """

        return render_page(content, active="home")

    @app.get("/tasks", response_class=HTMLResponse)
    async def tasks_page():
        """Tasks list page."""
        tasks = task_tracker.list_tasks(limit=50)

        content = """
        <div class="card">
            <h2>Recent Tasks</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Provider</th>
                    <th>Status</th>
                    <th>Message</th>
                    <th>Created</th>
                </tr>
        """

        for task in tasks:
            status_class = {
                TaskStatus.COMPLETED: "status-ok",
                TaskStatus.FAILED: "status-fail",
                TaskStatus.RUNNING: "status-pending",
                TaskStatus.PENDING: "status-pending",
            }.get(task.status, "")

            created = datetime.fromtimestamp(task.created_at).strftime("%Y-%m-%d %H:%M")
            msg_preview = task.message[:50] + "..." if len(task.message) > 50 else task.message

            content += f"""
                <tr>
                    <td>{task.id}</td>
                    <td>{task.provider}</td>
                    <td class="{status_class}">{task.status.value}</td>
                    <td>{msg_preview}</td>
                    <td>{created}</td>
                </tr>
            """

        content += """
            </table>
        </div>
        """

        return render_page(content, active="tasks")

    @app.get("/stats", response_class=HTMLResponse)
    async def stats_page():
        """Performance statistics page."""
        all_stats = perf_tracker.get_all_stats(hours=24)

        content = """
        <div class="card">
            <h2>Provider Performance (24h)</h2>
            <table>
                <tr>
                    <th>Provider</th>
                    <th>Requests</th>
                    <th>Success</th>
                    <th>Failed</th>
                    <th>Success Rate</th>
                    <th>Avg Latency</th>
                    <th>P95 Latency</th>
                </tr>
        """

        for stats in all_stats:
            rate_class = "status-ok" if stats.success_rate > 0.9 else ("status-fail" if stats.success_rate < 0.7 else "status-pending")
            content += f"""
                <tr>
                    <td>{stats.provider}</td>
                    <td>{stats.total_requests}</td>
                    <td class="status-ok">{stats.successful_requests}</td>
                    <td class="status-fail">{stats.failed_requests}</td>
                    <td class="{rate_class}">{stats.success_rate*100:.1f}%</td>
                    <td>{stats.avg_latency_ms:.0f}ms</td>
                    <td>{stats.p95_latency_ms:.0f}ms</td>
                </tr>
            """

        content += """
            </table>
        </div>
        """

        return render_page(content, active="stats")

    @app.get("/cache", response_class=HTMLResponse)
    async def cache_page():
        """Cache management page."""
        stats = cache.get_stats()
        entries = cache.list_entries(limit=20)

        content = f"""
        <div class="grid">
            <div class="card stat">
                <div class="stat-value">{stats.total_entries}</div>
                <div class="stat-label">Cached Entries</div>
            </div>
            <div class="card stat">
                <div class="stat-value">{stats.hit_rate*100:.1f}%</div>
                <div class="stat-label">Hit Rate</div>
            </div>
            <div class="card stat">
                <div class="stat-value">{stats.total_hits}</div>
                <div class="stat-label">Total Hits</div>
            </div>
            <div class="card stat">
                <div class="stat-value">{stats.total_misses}</div>
                <div class="stat-label">Total Misses</div>
            </div>
        </div>

        <div class="card">
            <h2>Recent Cache Entries</h2>
            <table>
                <tr>
                    <th>Provider</th>
                    <th>Hits</th>
                    <th>Created</th>
                    <th>Expires</th>
                </tr>
        """

        for entry in entries:
            created = datetime.fromtimestamp(entry.created_at).strftime("%Y-%m-%d %H:%M")
            expires = datetime.fromtimestamp(entry.expires_at).strftime("%Y-%m-%d %H:%M")
            content += f"""
                <tr>
                    <td>{entry.provider}</td>
                    <td>{entry.hit_count}</td>
                    <td>{created}</td>
                    <td>{expires}</td>
                </tr>
            """

        content += """
            </table>
        </div>
        """

        return render_page(content, active="cache")

    @app.get("/health", response_class=HTMLResponse)
    async def health_page():
        """Provider health status page."""
        import subprocess
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        providers = ["claude", "codex", "gemini", "opencode", "deepseek", "droid", "iflow", "kimi", "qwen"]
        ping_commands = {
            "claude": "lping", "codex": "cping", "gemini": "gping",
            "opencode": "oping", "deepseek": "dskping", "droid": "dping",
            "iflow": "iping", "kimi": "kping", "qwen": "qping",
        }

        def check_provider(provider: str) -> tuple:
            """Check a single provider's health."""
            ping_cmd = ping_commands.get(provider)
            try:
                import time
                start = time.time()
                result = subprocess.run([ping_cmd], capture_output=True, timeout=5)
                latency = (time.time() - start) * 1000

                if result.returncode == 0:
                    return (provider, "Healthy", "status-ok", latency)
                else:
                    return (provider, "Unavailable", "status-fail", latency)
            except HANDLED_EXCEPTIONS:
                return (provider, "Error", "status-fail", 0)

        # Run health checks in parallel using thread pool
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=len(providers)) as executor:
            results = await asyncio.gather(*[
                loop.run_in_executor(executor, check_provider, p)
                for p in providers
            ])

        content = """
        <div class="card">
            <h2>Provider Health Status</h2>
            <button class="btn refresh" hx-get="/health" hx-target="body">Refresh</button>
            <table>
                <tr>
                    <th>Provider</th>
                    <th>Status</th>
                    <th>Latency</th>
                </tr>
        """

        for provider, status, status_class, latency in results:
            content += f"""
                <tr>
                    <td>{provider}</td>
                    <td class="{status_class}">{status}</td>
                    <td>{latency:.0f}ms</td>
                </tr>
            """

        content += """
            </table>
        </div>
        """

        return render_page(content, active="health")

    # API endpoints
    @app.get("/api/stats")
    async def api_stats():
        """API endpoint for performance stats."""
        return perf_tracker.get_summary(hours=24)

    @app.get("/api/tasks")
    async def api_tasks(limit: int = 20):
        """API endpoint for tasks."""
        tasks = task_tracker.list_tasks(limit=limit)
        return [t.to_dict() for t in tasks]

    @app.get("/api/cache/stats")
    async def api_cache_stats():
        """API endpoint for cache stats."""
        stats = cache.get_stats()
        return {
            "total_entries": stats.total_entries,
            "hit_rate": stats.hit_rate,
            "total_hits": stats.total_hits,
            "total_misses": stats.total_misses,
        }

    @app.post("/api/cache/clear")
    async def api_cache_clear():
        """API endpoint to clear cache."""
        count = cache.clear()
        return {"cleared": count}

    # Rate limiting endpoints
    @app.get("/api/ratelimit")
    async def api_ratelimit_status():
        """API endpoint for rate limit status."""
        try:
            from rate_limiter import get_rate_limiter
            limiter = get_rate_limiter()
            stats = limiter.get_all_stats()
            return [
                {
                    "provider": s.provider,
                    "current_rpm": s.current_rpm,
                    "limit_rpm": s.limit_rpm,
                    "available_tokens": s.available_tokens,
                    "is_limited": s.is_limited,
                    "wait_time_s": s.wait_time_s,
                    "total_requests": s.total_requests,
                    "total_limited": s.total_limited,
                }
                for s in stats
            ]
        except ImportError:
            return {"error": "Rate limiter not available"}

    @app.post("/api/ratelimit/{provider}/reset")
    async def api_ratelimit_reset(provider: str):
        """API endpoint to reset rate limit for a provider."""
        try:
            from rate_limiter import get_rate_limiter
            limiter = get_rate_limiter()
            limiter.reset(provider)
            return {"status": "ok", "provider": provider}
        except ImportError:
            raise HTTPException(status_code=500, detail="Rate limiter not available")

    @app.get("/ratelimit", response_class=HTMLResponse)
    async def ratelimit_page():
        """Rate limit management page."""
        try:
            from rate_limiter import get_rate_limiter
            limiter = get_rate_limiter()
            stats = limiter.get_all_stats()
        except ImportError:
            stats = []

        content = """
        <div class="card">
            <h2>Rate Limit Status</h2>
            <button class="btn refresh" hx-get="/ratelimit" hx-target="body">Refresh</button>
            <table>
                <tr>
                    <th>Provider</th>
                    <th>Status</th>
                    <th>RPM</th>
                    <th>Tokens</th>
                    <th>Wait</th>
                    <th>Limited</th>
                    <th>Actions</th>
                </tr>
        """

        for s in stats:
            status_class = "status-fail" if s.is_limited else "status-ok"
            status_text = "LIMITED" if s.is_limited else "OK"
            rpm_str = f"{s.current_rpm}/{s.limit_rpm}"
            wait_str = f"{s.wait_time_s:.1f}s" if s.wait_time_s > 0 else "-"

            content += f"""
                <tr>
                    <td>{s.provider}</td>
                    <td class="{status_class}">{status_text}</td>
                    <td>{rpm_str}</td>
                    <td>{s.available_tokens:.1f}</td>
                    <td>{wait_str}</td>
                    <td>{s.total_limited}</td>
                    <td>
                        <button class="btn" hx-post="/api/ratelimit/{s.provider}/reset" hx-swap="none" onclick="setTimeout(() => location.reload(), 500)">Reset</button>
                    </td>
                </tr>
            """

        content += """
            </table>
        </div>
        """

        return render_page(content, active="ratelimit")

    return app

def run_server(host: str = "127.0.0.1", port: int = 8080, auto_open: bool = True):
    """Run the web server."""
    if not check_dependencies():
        return 1

    try:
        import uvicorn
    except ImportError:
        _emit("Error: uvicorn is not installed.", err=True)
        _emit("Install with: pip install uvicorn", err=True)
        return 1

    app = create_app()

    if auto_open:
        import webbrowser
        import threading

        def open_browser():
            import time
            time.sleep(1)
            webbrowser.open(f"http://{host}:{port}")

        threading.Thread(target=open_browser, daemon=True).start()

    _emit(f"Starting CCB Dashboard at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0
