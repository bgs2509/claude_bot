#!/bin/bash
# Скрипт hardening безопасности VPS
# Запускать от root: bash setup-security.sh
set -euo pipefail

SSH_PORT=${1:-2222}

echo "=== Hardening безопасности ==="
echo "SSH порт будет изменён на: $SSH_PORT"
echo ""
echo "ВАЖНО: Убедитесь что у вас есть SSH-ключ и второй терминал открыт!"
read -p "Продолжить? (y/N): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "Отменено."
    exit 0
fi

# SSH Hardening
echo "[1/4] Настройка SSH..."
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

cat > /etc/ssh/sshd_config.d/hardening.conf << EOF
Port $SSH_PORT
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
AllowUsers claude
ClientAliveInterval 300
ClientAliveCountMax 2
EOF

echo "  SSH настроен (порт $SSH_PORT, только ключи, только claude)"

# Firewall
echo "[2/4] Настройка UFW firewall..."
apt install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow "$SSH_PORT/tcp" comment 'SSH'
ufw --force enable
echo "  UFW включён (открыт только порт $SSH_PORT)"

# Fail2ban
echo "[3/4] Настройка fail2ban..."
apt install -y fail2ban

cat > /etc/fail2ban/jail.local << EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port = $SSH_PORT
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 86400
EOF

systemctl enable fail2ban
systemctl restart fail2ban
echo "  Fail2ban настроен (бан на 24ч после 3 попыток)"

# Автообновления
echo "[4/4] Настройка автообновлений..."
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
echo "  Автообновления безопасности включены"

# Перезапуск SSH
echo ""
echo "Перезапуск SSH..."
systemctl restart sshd

echo ""
echo "=== Hardening завершён ==="
echo ""
echo "ПРОВЕРЬТЕ подключение в НОВОМ терминале:"
echo "  ssh -p $SSH_PORT claude@$(hostname -I | awk '{print $1}')"
echo ""
echo "Если не можете подключиться — используйте консоль VPS провайдера"
echo "и восстановите конфиг: cp /etc/ssh/sshd_config.backup /etc/ssh/sshd_config"
