"""Embedded HTML template for the CCB dashboard UI."""

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CCB Dashboard</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        :root {{
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --bg-card: #0f3460;
            --text-primary: #eee;
            --text-secondary: #aaa;
            --accent: #e94560;
            --success: #4ade80;
            --warning: #fbbf24;
            --error: #ef4444;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        header {{
            background: var(--bg-secondary);
            padding: 15px 20px;
            border-bottom: 2px solid var(--accent);
        }}
        header h1 {{ font-size: 1.5rem; }}
        nav {{ margin-top: 10px; }}
        nav a {{
            color: var(--text-secondary);
            text-decoration: none;
            margin-right: 20px;
            padding: 5px 10px;
            border-radius: 4px;
        }}
        nav a:hover, nav a.active {{
            color: var(--text-primary);
            background: var(--bg-card);
        }}
        .card {{
            background: var(--bg-card);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }}
        .card h2 {{ margin-bottom: 15px; font-size: 1.2rem; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }}
        .stat {{
            text-align: center;
            padding: 15px;
        }}
        .stat-value {{ font-size: 2rem; font-weight: bold; color: var(--accent); }}
        .stat-label {{ color: var(--text-secondary); font-size: 0.9rem; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid var(--bg-secondary); }}
        th {{ color: var(--text-secondary); font-weight: 500; }}
        .status-ok {{ color: var(--success); }}
        .status-fail {{ color: var(--error); }}
        .status-pending {{ color: var(--warning); }}
        .btn {{
            background: var(--accent);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
        }}
        .btn:hover {{ opacity: 0.9; }}
        .refresh {{ float: right; font-size: 0.8rem; }}
    </style>
</head>
<body>
    <header>
        <h1>CCB Dashboard</h1>
        <nav>
            <a href="/" class="{nav_home}">Dashboard</a>
            <a href="/tasks" class="{nav_tasks}">Tasks</a>
            <a href="/stats" class="{nav_stats}">Performance</a>
            <a href="/cache" class="{nav_cache}">Cache</a>
            <a href="/ratelimit" class="{nav_ratelimit}">Rate Limit</a>
            <a href="/health" class="{nav_health}">Health</a>
        </nav>
    </header>
    <div class="container">
        {content}
    </div>
</body>
</html>
"""
