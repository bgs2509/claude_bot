#!/bin/bash
# Мониторинг сервера: алерты + ежедневный отчёт
# Cron:
#   */5 * * * *  /opt/ai-steward/scripts/healthcheck.sh
#   0 20 * * *   /opt/ai-steward/scripts/healthcheck.sh --report
set -euo pipefail

# --- Настройки ---

ENV_FILE="/opt/ai-steward/.env"
if [[ -f "$ENV_FILE" ]]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT_ID="${ALERT_CHAT_ID:-763463467}"
STATE_FILE="/tmp/healthcheck_last_boot"
PAID_UNTIL="2026-04-05"
MODE="${1:-alert}"

send_tg() {
    if [[ -n "$BOT_TOKEN" && -n "$CHAT_ID" ]]; then
        curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
            -d "chat_id=${CHAT_ID}" \
            -d "text=${1}" \
            -d "parse_mode=HTML" > /dev/null 2>&1
    fi
}

# --- Сбор данных (общий для алертов и отчёта) ---

svc_ok() { systemctl is-active --quiet "$1" 2>/dev/null; }
port_ok() { ss -tln | grep -q ":${1} "; }

DISK_PCT=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
RAM_PCT=$(free | awk '/Mem:/ {printf "%.0f", $3/$2 * 100}')
SWAP_PCT=$(free | awk '/Swap:/ {if($2>0) printf "%.0f", $3/$2*100; else print 0}')
CPU_LOAD=$(awk '{printf "%.1f", $1}' /proc/loadavg)
CPU_LOAD_X10=$(awk '{printf "%.0f", $1 * 10}' /proc/loadavg)
JOURNAL_MB=$(du -sm /var/log/journal 2>/dev/null | awk '{print $1}' || echo 0)
JOURNAL_MB=${JOURNAL_MB:-0}
DAYS_LEFT=$(( ($(date -d "$PAID_UNTIL" +%s) - $(date +%s)) / 86400 ))

OOM_COUNT=$(dmesg 2>/dev/null | tail -100 | grep -c "Out of memory" || true)
OOM_COUNT=${OOM_COUNT:-0}

SEC_FLAG="/tmp/healthcheck_sec_update"
SEC_UPDATES=0
if [[ ! -f "$SEC_FLAG" ]] || (( $(date +%s) - $(stat -c %Y "$SEC_FLAG") > 86400 )); then
    SEC_UPDATES=$(apt list --upgradable 2>/dev/null | grep -c -- "-security" || true)
    SEC_UPDATES=${SEC_UPDATES:-0}
    touch "$SEC_FLAG"
fi

CURRENT_BOOT=$(who -b | awk '{print $3, $4}')

# --- Режим: алерты ---

if [[ "$MODE" == "alert" ]]; then
    ALERTS=()

    # Сервисы
    if ! svc_ok ai-steward; then
        ALERTS+=("🔴 ai-steward НЕ запущен!")
        sudo systemctl restart ai-steward 2>/dev/null
        sleep 3
        if svc_ok ai-steward; then
            ALERTS+=("🟢 Перезапуск успешен")
        else
            ALERTS+=("🔴 Перезапуск НЕ удался")
        fi
    fi
    svc_ok x-ui       || ALERTS+=("🔴 x-ui (VPN) НЕ запущен!")
    svc_ok fail2ban    || ALERTS+=("🔴 fail2ban НЕ запущен!")
    port_ok 443        || ALERTS+=("🔴 Порт 443 не слушает — VPN недоступен!")
    port_ok 22         || ALERTS+=("🔴 SSH порт 22 не слушает!")

    # Сеть
    ping -c 1 -W 3 1.1.1.1 > /dev/null 2>&1 || ALERTS+=("🔴 Нет интернета!")

    # Ресурсы
    (( DISK_PCT > 80 ))    && ALERTS+=("⚠️ Диск: ${DISK_PCT}%")
    (( RAM_PCT > 90 ))     && ALERTS+=("⚠️ RAM: ${RAM_PCT}%")
    (( SWAP_PCT > 70 ))    && ALERTS+=("⚠️ Swap: ${SWAP_PCT}%")
    (( CPU_LOAD_X10 > 20 )) && ALERTS+=("⚠️ CPU load: ${CPU_LOAD}")
    (( JOURNAL_MB > 500 )) && ALERTS+=("⚠️ Journal-логи: ${JOURNAL_MB} МБ")

    # Системные события
    (( OOM_COUNT > 0 )) && ALERTS+=("🔴 OOM kill! (${OOM_COUNT})")

    if [[ -f "$STATE_FILE" ]]; then
        LAST_BOOT=$(cat "$STATE_FILE")
        [[ "$CURRENT_BOOT" != "$LAST_BOOT" ]] && ALERTS+=("🔄 Сервер перезагружен! Boot: ${CURRENT_BOOT}")
    fi
    echo "$CURRENT_BOOT" > "$STATE_FILE"

    (( SEC_UPDATES > 0 )) && ALERTS+=("📦 Обновлений безопасности: ${SEC_UPDATES}")

    # Отправка
    if (( ${#ALERTS[@]} > 0 )); then
        MSG="🚨 <b>Alert: $(hostname)</b>"
        for line in "${ALERTS[@]}"; do
            MSG+="
${line}"
        done
        MSG+="

🕐 $(date '+%Y-%m-%d %H:%M') UTC"
        send_tg "$MSG"
    fi
fi

# --- Режим: ежедневный отчёт ---

if [[ "$MODE" == "--report" ]]; then
    echo "$CURRENT_BOOT" > "$STATE_FILE"

    S_STEWARD="✅"; svc_ok ai-steward || S_STEWARD="❌"
    S_XUI="✅";     svc_ok x-ui       || S_XUI="❌"
    S_F2B="✅";     svc_ok fail2ban    || S_F2B="❌"
    P_443="✅";     port_ok 443        || P_443="❌"
    P_22="✅";      port_ok 22         || P_22="❌"

    UPTIME=$(uptime -p | sed 's/up //')
    LOAD_AVG=$(awk '{printf "%.2f / %.2f / %.2f", $1, $2, $3}' /proc/loadavg)
    RAM_INFO=$(free -m | awk '/Mem:/ {printf "%d / %d MB (%d%%)", $3, $2, $3/$2*100}')
    SWAP_INFO=$(free -m | awk '/Swap:/ {if($2>0) printf "%d / %d MB (%d%%)", $3, $2, $3/$2*100; else print "off"}')
    DISK_INFO=$(df -h / | tail -1 | awk '{printf "%s / %s (%s)", $3, $2, $5}')
    JOURNAL_SIZE=$(du -sh /var/log/journal 2>/dev/null | awk '{print $1}' || echo "?")

    TRAFFIC=$(sar -n DEV -f "/var/log/sysstat/sa$(date +%d)" 2>/dev/null \
        | grep "eth0" | grep "Average" \
        | awk '{printf "RX %.1f GB / TX %.1f GB", $4*86400/1048576, $6*86400/1048576}')
    TRAFFIC=${TRAFFIC:-"нет данных"}

    VPN_CONN=$(ss -tn state established '( sport = 443 )' 2>/dev/null | tail -n +2 | wc -l)

    MSG="📊 <b>Отчёт: $(hostname)</b>
$(TZ=Europe/Moscow date '+%Y-%m-%d %H:%M') МСК

<b>Uptime:</b> ${UPTIME}

<b>Ресурсы:</b>
  CPU: ${LOAD_AVG}
  RAM: ${RAM_INFO}
  Swap: ${SWAP_INFO}
  Диск: ${DISK_INFO}
  Логи: ${JOURNAL_SIZE}

<b>Сервисы:</b>
  ${S_STEWARD} ai-steward
  ${S_XUI} x-ui (VPN)
  ${S_F2B} fail2ban
  ${P_443} порт 443
  ${P_22} порт 22

<b>Сеть:</b>
  Трафик: ${TRAFFIC}
  VPN клиентов: ${VPN_CONN}

<b>Безопасность:</b> ${SEC_UPDATES} обновлений
<b>Оплата:</b> ${DAYS_LEFT} дн. до ${PAID_UNTIL}"

    send_tg "$MSG"
fi
