#!/usr/bin/env python3
"""b4-2: 제공된 monitor/app 로그에서 실제 관측값을 읽어 장애 보고서를 만든다.
OOM/CPU/Deadlock 증거를 추정하지 않고 로그에 있는 수치만 기록한다.
실행: python3 b4-2.py monitor.log app.log --out reports"""
from pathlib import Path
import argparse,re
# main: 로그를 분석해 장애 보고서를 생성한다.
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('monitor',type=Path);p.add_argument('app',type=Path);p.add_argument('--out',type=Path,default=Path('reports'));a=p.parse_args();monitor=a.monitor.read_text(errors='replace');app=a.app.read_text(errors='replace');a.out.mkdir(parents=True,exist_ok=True)
    kind='OOM' if re.search(r'Memory|OOM|SELF-TERMINATED',app,re.I) else ('CPU' if re.search(r'WATCHDOG|CPU',app,re.I) else 'Deadlock')
    cpu=re.findall(r'CPU[:= ]+([0-9.]+)',monitor,re.I);mem=re.findall(r'MEM(?:ORY)?[:= ]+([0-9.]+)',monitor,re.I)
    report='[Bug] '+kind+' 장애 분석\n\n## 1. Description\n- 실제 로그를 근거로 분류한 장애입니다.\n\n## 2. Evidence & Logs\n- monitor 샘플 수: '+str(len(monitor.splitlines()))+'\n- CPU 최근값: '+str(cpu[-5:])+'\n- MEM 최근값: '+str(mem[-5:])+'\n- 앱 마지막 로그: '+str(app.splitlines()[-1:] or ['없음'])+'\n\n## 3. Root Cause Analysis\n- OOM은 메모리 보호 정책, CPU는 Watchdog, Deadlock은 PID 유지와 로그 정지를 확인합니다.\n\n## 4. Workaround & Verification\n- MEMORY_LIMIT/CPU_MAX_OCCUPY/MULTI_THREAD_ENABLE을 한 번에 하나씩 바꾸고 Before/After 생존시간과 수치를 기록합니다.\n- 근본 해결은 누수·busy loop·락 순서 수정과 회귀 테스트입니다.\n'
    (a.out/(kind.lower()+'.txt')).write_text(report,encoding='utf-8');print(report)
if __name__=='__main__':main()
