"""
NexAlfa Custom Domain Setup Wizard
Generates Nginx, Caddy, or Cloudflare Tunnel configurations for reverse-proxying NexAlfa Web UI and WebSocket API.
"""

from __future__ import annotations

from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

console = Console()


def run_domain_setup():
    """Interactive wizard for connecting a custom domain."""
    console.print(Panel(
        "[bold cyan]🌐 NexAlfa Custom Domain & SSL Setup[/bold cyan]\n\n"
        "Connect your custom domain (e.g., https://nexalfa.work or https://agent.mydomain.com)\n"
        "to access NexAlfa remotely from any device.",
        title="Domain Setup",
        border_style="cyan",
    ))

    domain = Prompt.ask("\nEnter your domain name (e.g. nexalfa.work)")
    domain = domain.replace("https://", "").replace("http://", "").strip("/")

    proxy_type = Prompt.ask(
        "\nSelect Reverse Proxy / Deployment Method",
        choices=["nginx", "caddy", "cloudflare", "coolify"],
        default="nginx"
    )

    console.print("\n[bold]Generating reverse proxy configuration...[/bold]\n")

    out_dir = Path("deploy")
    out_dir.mkdir(exist_ok=True)

    if proxy_type == "nginx":
        nginx_config = f"""# Nginx configuration for NexAlfa ({domain})
server {{
    listen 80;
    server_name {domain};

    location / {{
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }}

    location /api/ {{
        proxy_pass http://127.0.0.1:18789/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
    }}

    location /socket.io/ {{
        proxy_pass http://127.0.0.1:18789/socket.io/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }}
}}
"""
        config_path = out_dir / "nginx-domain.conf"
        config_path.write_text(nginx_config, encoding="utf-8")
        console.print(f"✅ Generated Nginx config at [cyan]{config_path}[/cyan]")
        console.print("\n[bold]To enable SSL with Certbot:[/bold]")
        console.print(f"  sudo cp {config_path} /etc/nginx/sites-available/{domain}")
        console.print(f"  sudo ln -s /etc/nginx/sites-available/{domain} /etc/nginx/sites-enabled/")
        console.print(f"  sudo certbot --nginx -d {domain}")

    elif proxy_type == "caddy":
        caddy_config = f"""{domain} {{
    reverse_proxy /socket.io/* 127.0.0.1:18789
    reverse_proxy /api/* 127.0.0.1:18789
    reverse_proxy * 127.0.0.1:3000
}}
"""
        config_path = out_dir / "Caddyfile"
        config_path.write_text(caddy_config, encoding="utf-8")
        console.print(f"✅ Generated Caddyfile at [cyan]{config_path}[/cyan]")
        console.print("\nCaddy will automatically manage Let's Encrypt SSL certificates for you!")

    elif proxy_type == "cloudflare":
        console.print("\n[bold]Cloudflare Tunnel Setup:[/bold]")
        console.print(f"  1. Run: cloudflared tunnel create nexalfa")
        console.print(f"  2. Route DNS: cloudflared tunnel route dns nexalfa {domain}")
        console.print(f"  3. Point ingress rule to http://localhost:3000")

    elif proxy_type == "coolify":
        console.print(f"✅ Coolify template ready at [cyan]docker-compose.coolify.yml[/cyan]")
        console.print(f"Set FQDN in Coolify settings: https://{domain}")

    # Update .env
    env_file = Path(".env")
    if env_file.exists():
        content = env_file.read_text(encoding="utf-8")
        if "NEX_DOMAIN=" in content:
            import re
            content = re.sub(r"NEX_DOMAIN=.*", f"NEX_DOMAIN={domain}", content)
        else:
            content += f"\nNEX_DOMAIN={domain}\n"
        env_file.write_text(content, encoding="utf-8")
        console.print(f"\n✅ Updated .env with NEX_DOMAIN={domain}")

    console.print(Panel(
        f"[bold green]🎉 Domain setup guide for {domain} is complete![/bold green]",
        border_style="green"
    ))
