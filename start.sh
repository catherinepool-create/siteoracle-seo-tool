#!/bin/bash
set -e

# Railway injects PORT; fall back to 8501 for local runs
PUBLIC_PORT=${PORT:-8501}

# Generate nginx config with the correct public port
cat > /tmp/nginx_runtime.conf << NGINXEOF
worker_processes 1;
error_log /tmp/nginx_error.log warn;
pid /tmp/nginx.pid;

events { worker_connections 64; }

http {
    client_body_temp_path /tmp/nginx_client_body;
    proxy_temp_path       /tmp/nginx_proxy;
    fastcgi_temp_path     /tmp/nginx_fastcgi;
    uwsgi_temp_path       /tmp/nginx_uwsgi;
    scgi_temp_path        /tmp/nginx_scgi;

    server {
        listen ${PUBLIC_PORT};

        location = /robots.txt {
            add_header Content-Type text/plain;
            return 200 "User-agent: *\nAllow: /\nSitemap: https://app.squadconsole.com/sitemap.xml\n";
        }

        location = /sitemap.xml {
            add_header Content-Type application/xml;
            return 200 '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://app.squadconsole.com/</loc><lastmod>2026-05-07</lastmod><changefreq>weekly</changefreq><priority>1.0</priority></url></urlset>';
        }

        location / {
            proxy_pass http://127.0.0.1:8502;
            proxy_http_version 1.1;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_read_timeout 300;
        }
    }
}
NGINXEOF

nginx -c /tmp/nginx_runtime.conf -g "daemon off;" &

exec streamlit run app.py \
    --server.port=8502 \
    --server.address=127.0.0.1
