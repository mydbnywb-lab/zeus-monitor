#!/bin/bash

PROJECT_DIR="/opt/zeus-monitor"
REPO_URL="https://github.com/mydbnywb-lab/zeus-monitor.git"
BACKUP_DIR="/root/zeus-backups"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

pause() {
    echo
    read -rp "برای بازگشت به منو Enter بزنید..."
}

require_root() {
    if [ "$EUID" -ne 0 ]; then
        echo "Please run this installer as root."
        exit 1
    fi
}

get_domain() {
    "$PROJECT_DIR/venv/bin/python" -c \
    'from dotenv import dotenv_values; print((dotenv_values("/opt/zeus-monitor/.env").get("MINI_APP_DOMAIN") or "").replace("https://","").replace("http://","").rstrip("/"))'
}

install_config() {
    echo
    echo "ZEUS Configuration"
    echo "------------------"

    read -rp "Telegram Bot Token: " BOT_TOKEN
    read -rp "Telegram Admin ID: " ADMIN_ID
    read -rp "Mini App Domain (example.com): " DOMAIN
    read -rp "PasarGuard Panel URL: " PANEL_URL
    read -rsp "PasarGuard API Key: " PANEL_API_KEY
    echo

    read -rp "Check interval in seconds [60]: " CHECK_INTERVAL
    CHECK_INTERVAL=${CHECK_INTERVAL:-60}

    DOMAIN="${DOMAIN#https://}"
    DOMAIN="${DOMAIN#http://}"
    DOMAIN="${DOMAIN%/}"
    PANEL_URL="${PANEL_URL%/}"

    if [ -z "$BOT_TOKEN" ] || [ -z "$PANEL_API_KEY" ] ||
       ! [[ "$ADMIN_ID" =~ ^[0-9]+$ ]] ||
       ! [[ "$CHECK_INTERVAL" =~ ^[0-9]+$ ]] ||
       [ "$CHECK_INTERVAL" -lt 10 ] ||
       [ -z "$DOMAIN" ] || [ -z "$PANEL_URL" ]; then
        echo -e "${RED}Invalid configuration. Please check your values.${NC}"
        return 1
    fi

    cat > "$PROJECT_DIR/.env" <<ENV
BOT_TOKEN="$BOT_TOKEN"
ADMIN_ID="$ADMIN_ID"
MINI_APP_DOMAIN="https://$DOMAIN"
PANEL_URL="$PANEL_URL"
PANEL_API_KEY="$PANEL_API_KEY"
DATABASE_URL="sqlite+aiosqlite:////opt/zeus-monitor/database/zeus.db"
CHECK_INTERVAL="$CHECK_INTERVAL"
LOG_LEVEL="INFO"
ENV

    chmod 600 "$PROJECT_DIR/.env"
    echo -e "${GREEN}Configuration saved.${NC}"
}

install_zeus() {
    echo -e "${GREEN}Starting ZEUS installation...${NC}"

    apt-get update
    apt-get install -y git python3 python3-venv python3-pip nginx certbot python3-certbot-nginx curl nano

    if [ ! -d "$PROJECT_DIR/.git" ]; then
        if [ -d "$PROJECT_DIR" ] && [ -n "$(ls -A "$PROJECT_DIR" 2>/dev/null)" ]; then
            echo -e "${RED}Project directory exists but is not a Git repository. Installation stopped.${NC}"
            pause
            return
        fi
        git clone "$REPO_URL" "$PROJECT_DIR" || {
            echo "Git clone failed."
            pause
            return
        }
    fi

    mkdir -p "$PROJECT_DIR/database" "$PROJECT_DIR/miniapp/assets"
    cd "$PROJECT_DIR" || return

    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt

    if [ ! -f .env ]; then
        install_config || {
            pause
            return
        }
    else
        echo "Existing .env file found. Keeping current configuration."
    fi

    if ! ./venv/bin/python -c \
        'from config.settings import validate_settings; e=validate_settings(); print("\n".join(e)); exit(bool(e))'; then
        echo -e "${RED}Configuration validation failed.${NC}"
        pause
        return
    fi

    DOMAIN=$(get_domain)

    if [ -z "$DOMAIN" ]; then
        echo "Domain is missing."
        pause
        return
    fi

    cat > /etc/systemd/system/zeus-backend.service <<SERVICE
[Unit]
Description=ZEUS MONITOR Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

    cat > /etc/systemd/system/zeus-bot.service <<SERVICE
[Unit]
Description=ZEUS MONITOR Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python -m bot.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

    if [ -f /etc/nginx/sites-available/zeus-monitor ]; then
        cp /etc/nginx/sites-available/zeus-monitor \
        "/root/zeus-nginx-backup-$(date +%Y%m%d-%H%M%S)"
    fi

    cat > /etc/nginx/sites-available/zeus-monitor <<NGINX
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX

    ln -sfn /etc/nginx/sites-available/zeus-monitor \
    /etc/nginx/sites-enabled/zeus-monitor

    nginx -t || {
        echo "Nginx configuration test failed."
        pause
        return
    }

    systemctl daemon-reload
    systemctl enable zeus-backend zeus-bot
    systemctl restart zeus-backend zeus-bot
    systemctl reload nginx

    echo
    read -rp "Email for HTTPS certificate: " EMAIL

    if [ -n "$EMAIL" ]; then
        certbot --nginx -d "$DOMAIN" \
        --non-interactive --agree-tos --redirect -m "$EMAIL"
    else
        echo "HTTPS setup skipped. You can configure it later."
    fi

    echo
    echo -e "${GREEN}ZEUS installation process finished.${NC}"
    echo "Backend: $(systemctl is-active zeus-backend)"
    echo "Bot: $(systemctl is-active zeus-bot)"
    pause
}

update_zeus() {
    echo -e "${BLUE}ZEUS Update${NC}"

    if [ ! -d "$PROJECT_DIR/.git" ]; then
        echo "ZEUS Git repository not found."
        pause
        return
    fi

    mkdir -p "$BACKUP_DIR"
    cp -a "$PROJECT_DIR/.env" "$BACKUP_DIR/env-$(date +%Y%m%d-%H%M%S)" 2>/dev/null

    if [ -f "$PROJECT_DIR/database/zeus.db" ]; then
        cp -a "$PROJECT_DIR/database/zeus.db" \
        "$BACKUP_DIR/database-$(date +%Y%m%d-%H%M%S).db"
    fi

    if [ -n "$(git -C "$PROJECT_DIR" status --porcelain)" ]; then
        echo "Local Git changes detected. Update stopped to protect your files."
        pause
        return
    fi

    git -C "$PROJECT_DIR" pull --ff-only || {
        echo "Git update failed."
        pause
        return
    }

    "$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
    mkdir -p "$PROJECT_DIR/miniapp/assets" "$PROJECT_DIR/database"

    systemctl restart zeus-backend zeus-bot

    echo -e "${GREEN}Update completed.${NC}"
    pause
}

uninstall_zeus() {
    echo -e "${RED}WARNING: ZEUS will be removed from this server.${NC}"
    echo "A backup will be saved before removal."
    echo "Other applications and PasarGuard will not be removed."
    echo

    read -rp 'To confirm, type DELETE: ' CONFIRM

    if [ "$CONFIRM" != "DELETE" ]; then
        echo "Uninstall cancelled."
        pause
        return
    fi

    mkdir -p "$BACKUP_DIR"

    if [ -d "$PROJECT_DIR" ]; then
        tar --exclude="$PROJECT_DIR/venv" \
        -czf "$BACKUP_DIR/zeus-$(date +%Y%m%d-%H%M%S).tar.gz" \
        -C /opt zeus-monitor
    fi

    DOMAIN=""
    if [ -x "$PROJECT_DIR/venv/bin/python" ] && [ -f "$PROJECT_DIR/.env" ]; then
        DOMAIN=$(get_domain)
    fi

    systemctl disable --now zeus-backend zeus-bot 2>/dev/null
    rm -f /etc/systemd/system/zeus-backend.service
    rm -f /etc/systemd/system/zeus-bot.service

    rm -f /etc/nginx/sites-enabled/zeus-monitor
    rm -f /etc/nginx/sites-available/zeus-monitor

    systemctl daemon-reload
    nginx -t && systemctl reload nginx

    if [ -n "$DOMAIN" ] && command -v certbot >/dev/null 2>&1; then
        echo
        read -rp "Also delete the HTTPS certificate for $DOMAIN? [y/N]: " CERT_CONFIRM
        if [[ "$CERT_CONFIRM" =~ ^[Yy]$ ]]; then
            certbot delete --cert-name "$DOMAIN" --non-interactive
        fi
    fi

    rm -rf "$PROJECT_DIR"

    echo -e "${GREEN}ZEUS application removed. Backup is in $BACKUP_DIR${NC}"
    pause
}

edit_config() {
    echo -e "${BLUE}Edit ZEUS Configuration${NC}"

    if [ ! -f "$PROJECT_DIR/.env" ]; then
        echo "Configuration file not found."
        pause
        return
    fi

    nano "$PROJECT_DIR/.env"
    chmod 600 "$PROJECT_DIR/.env"

    if [ -x "$PROJECT_DIR/venv/bin/python" ] &&
       "$PROJECT_DIR/venv/bin/python" -c \
       'from config.settings import validate_settings; e=validate_settings(); print("\n".join(e)); exit(bool(e))'; then
        systemctl restart zeus-backend zeus-bot
        echo "Configuration saved and services restarted."
    else
        echo "Configuration validation failed. Services were not restarted."
    fi

    pause
}

require_root

while true; do
    clear

    echo -e "${BLUE}"
    echo "╔══════════════════════════════════╗"
    echo "║          ⚡ ZEUS MONITOR         ║"
    echo "║             INSTALLER            ║"
    echo "╠══════════════════════════════════╣"
    echo "║                                  ║"
    echo "║  1. Install                      ║"
    echo "║  2. Update                       ║"
    echo "║  3. Uninstall                    ║"
    echo "║  4. Edit Configuration           ║"
    echo "║                                  ║"
    echo "╚══════════════════════════════════╝"
    echo -e "${NC}"

    read -rp "Select an option [1-4]: " choice

    case "$choice" in
        1) install_zeus ;;
        2) update_zeus ;;
        3) uninstall_zeus ;;
        4) edit_config ;;
        *) echo "Invalid option."; sleep 1 ;;
    esac
done
