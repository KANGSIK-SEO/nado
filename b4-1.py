#!/usr/bin/env python3
"""b4-1: Linux agent 운영 환경과 monitor.sh를 생성한다.
Ubuntu에서 일반 계정으로 AGENT_HOME, AGENT_PORT=15034, AGENT_LOG_DIR을 설정한다.
스크립트는 프로세스/포트 health check 실패 시 1, 자원 임계 초과는 WARNING만 낸다.
crontab -e에 `* * * * * /path/to/monitor.sh`를 넣고 1분 뒤 로그 증가를 확인한다.
SSH 20022와 앱 15034만 UFW에서 허용하며, 종료 후 계정/디렉터리/방화벽 설정을 기록한다."""
from pathlib import Path
import argparse
SCRIPT='''#!/usr/bin/env bash
set -u
PORT="${AGENT_PORT:-15034}"
LOG_DIR="${AGENT_LOG_DIR:-/var/log/agent-app}"
LOG="$LOG_DIR/monitor.log"
mkdir -p "$LOG_DIR" 2>/dev/null || true
fail=0
PID=$(pgrep -f 'agent_app.py|agent-leak-app' | head -n 1 || true)
if [[ -z "$PID" ]]; then echo "[ERROR] process not running"; fail=1; fi
if ! ss -ltn "sport = :$PORT" | grep -q LISTEN; then echo "[ERROR] port $PORT is not LISTEN"; fail=1; fi
if command -v ufw >/dev/null && ! ufw status | grep -q active; then echo "[WARNING] firewall inactive"; fi
CPU=0; MEM=0
if [[ -n "$PID" ]]; then read CPU MEM < <(ps -p "$PID" -o pcpu=,pmem=); fi
DISK=$(df -P / | awk 'NR==2{gsub(/%/,"",$5);print $5}')
[[ "${CPU%.*}" -gt 20 ]] 2>/dev/null && echo "[WARNING] CPU > 20%"
[[ "${MEM%.*}" -gt 10 ]] 2>/dev/null && echo "[WARNING] MEM > 10%"
[[ "$DISK" -gt 80 ]] && echo "[WARNING] DISK_USED > 80%"
printf '[%s] PID:%s CPU:%s%% MEM:%s%% DISK_USED:%s%%\n' "$(date '+%F %T')" "${PID:-none}" "$CPU" "$MEM" "$DISK" >> "$LOG" 2>/dev/null || true
if [[ -f "$LOG" ]]; then SIZE=$(wc -c < "$LOG"); if [[ "$SIZE" -gt 10485760 ]]; then mv "$LOG" "$LOG.1"; fi; fi
for I in 10 9 8 7 6 5 4 3 2; do PREV=$((I-1)); [[ -f "$LOG.$PREV" ]] && mv "$LOG.$PREV" "$LOG.$I"; done
exit "$fail"
'''
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=Path('monitor.sh'));a=p.parse_args();a.out.write_text(SCRIPT,encoding='utf-8');a.out.chmod(0o750);print('생성 완료:',a.out.resolve())
if __name__=='__main__':main()
