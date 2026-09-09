#!/usr/bin/env python3
'b2-1 | 나만의 용돈 기입장 프로그램 만들기\n실행: python3 b2-1.py; cd generated/b2-1; python3 main.py --help\nPython 3.10+, 외부 패키지 없음. --data-dir ./data 는 명령 앞에 둔다.\n예: python3 main.py --data-dir ./data add (대화형)\npython3 main.py update --id ID --amount 2000 (옵션 방식으로 고정)\npython3 main.py search --from 2026-01-01 --to 2026-12-31 --tag lunch\npython3 main.py budget set --month 2026-09 --amount 500000\npython3 main.py summary --month 2026-09 --top 3\npython3 main.py export --out backup.csv --month 2026-09\npython3 main.py import --from backup.csv\n저장: transactions.jsonl / categories.jsonl / budgets.jsonl (UTF-8).\nCSV: date,type,category,amount,memo,tags 헤더. tags는 쉼표 구분하며 CSV 인용규칙 준수.\nimport는 전 행 검증 후 원자적 반영, 오류면 0건 반영. 재가져오기는 중복 거래를 만든다.\n최신순 기준: 날짜 내림차순, 같은 날짜는 나중에 추가한 거래 우선.\n스트리밍: JSONL yield → 임시 SQLite 외부 정렬 → 한 행씩 출력. 전체 거래 리스트 적재 없음.\n원본 데이터 영구 저장 형식은 JSONL이며 SQLite는 정렬 중에만 쓰고 삭제한다.\n파일 변경은 동일 디렉터리 임시 파일+fsync+os.replace; POSIX flock으로 동시 변경 보호.\n기본 카테고리: food, transport, rent, etc, salary. 사용 중인 카테고리는 삭제 거부.\n오류는 원인/힌트 및 exit 1, 정상 exit 0. 예외/시간 측정은 데코레이터로 분리.\n'

from pathlib import Path
import argparse

# 각 문자열은 해당 경로에 생성되는 실제 소스입니다. 설명도 소스 주석에 담습니다.
FILES = {
'model.py': r'''
from dataclasses import dataclass, field, asdict
from datetime import date
import re
import uuid


# check_date: 날짜 형식을 검증하고 정상 값을 반환한다.
def check_date(value: str) -> str:
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
        raise ValueError('날짜는 YYYY-MM-DD 형식입니다')
    date.fromisoformat(value)
    return value

# check_month: YYYY-MM 월 형식을 검증한다.
def check_month(value: str) -> str:
    check_date(value+'-01')
    return value

# positive: 양의 정수 금액만 허용한다.
def positive(value: str) -> int:
    if not re.fullmatch(r'[0-9]+',str(value)) or int(value)<=0:
        raise ValueError('금액은 양수 정수여야 합니다')
    return int(value)

@dataclass
class Transaction:
    id: str
    type: str
    date: str
    amount: int
    category: str
    memo: str = ''
    tags: list[str] = field(default_factory=list)

    @classmethod
    def create(cls, values: dict, categories: list[str]) -> 'Transaction':
        kind = values['type']
        if kind not in ('income','expense'): raise ValueError('타입은 income 또는 expense입니다')
        category = values['category']
        if category not in categories: raise ValueError('없는 카테고리입니다. category add로 먼저 등록하세요')
        tags = values.get('tags','')
        if isinstance(tags,str): tags=[s.strip() for s in tags.split(',') if s.strip()]
        return cls(values.get('id') or 'TX-'+uuid.uuid4().hex,kind,check_date(values['date']),
                   positive(values['amount']),category,values.get('memo',''),tags)

    def record(self) -> dict:
        return asdict(self)
''',
'storage.py': r'''
from pathlib import Path
from contextlib import contextmanager
from typing import Iterator, Iterable
import json
import os
import tempfile
import sqlite3
import fcntl

class Store:
    """영구 파일은 JSONL, 변경 실패 시 이전 파일을 그대로 보존한다."""
    def __init__(self, directory: Path):
        self.directory=directory
        directory.mkdir(parents=True,exist_ok=True)
        self.transactions=directory/'transactions.jsonl'
        self.categories=directory/'categories.jsonl'
        self.budgets=directory/'budgets.jsonl'

    @contextmanager
    def lock(self):
        with (self.directory/'.lock').open('a') as handle:
            fcntl.flock(handle,fcntl.LOCK_EX)
            try:
                for path in (self.transactions,self.categories,self.budgets): path.touch(exist_ok=True)
                if self.categories.stat().st_size==0:
                    self.write(self.categories,({'name':v} for v in ('food','transport','rent','etc','salary')))
                yield
            finally: fcntl.flock(handle,fcntl.LOCK_UN)

    def read(self, path: Path) -> Iterator[dict]:
        with path.open(encoding='utf-8') as stream:
            for number,line in enumerate(stream,1):
                if line.strip():
                    try:
                        value=json.loads(line)
                        if not isinstance(value,dict): raise ValueError()
                        yield value
                    except (ValueError,TypeError) as error:
                        raise ValueError(f'{path.name}:{number} 손상된 JSONL. 백업을 확인하세요') from error

    def write(self, path: Path, records: Iterable[dict]) -> None:
        name=None
        try:
            with tempfile.NamedTemporaryFile('w',dir=path.parent,encoding='utf-8',delete=False) as stream:
                name=stream.name
                for record in records: stream.write(json.dumps(record,ensure_ascii=False)+'\n')
                stream.flush(); os.fsync(stream.fileno())
            os.replace(name,path)
        finally:
            if name and os.path.exists(name): os.unlink(name)

    def newest(self, records: Iterable[dict]) -> Iterator[dict]:
        # 전체 메모리 정렬 대신 임시 디스크 DB를 사용한다. 영구 저장소가 아니다.
        with tempfile.TemporaryDirectory(prefix='budget-sort-') as directory:
            db=sqlite3.connect(str(Path(directory)/'sort.db'))
            try:
                db.execute('PRAGMA temp_store=FILE')
                db.execute('CREATE TABLE rows (seq INTEGER PRIMARY KEY, date TEXT, payload TEXT)')
                db.executemany('INSERT INTO rows(date,payload) VALUES (?,?)',
                               ((r['date'],json.dumps(r,ensure_ascii=False)) for r in records))
                db.commit()
                for (payload,) in db.execute('SELECT payload FROM rows ORDER BY date DESC, seq DESC'):
                    yield json.loads(payload)
            finally: db.close()
''',
'service.py': r'''
from collections import defaultdict
from itertools import chain, islice
from pathlib import Path
from typing import Iterator
import csv
import json
import os
import tempfile
from model import Transaction, check_date, check_month, positive
from storage import Store

SCHEMA=['date','type','category','amount','memo','tags']

class BudgetService:
    def __init__(self, store: Store): self.store=store
    def categories(self) -> list[str]: return [r['name'] for r in self.store.read(self.store.categories)]
    def add(self, values: dict) -> str:
        item=Transaction.create(values,self.categories())
        self.store.write(self.store.transactions,chain(self.store.read(self.store.transactions),[item.record()]))
        return item.id
    def change(self, identifier: str, changes: dict | None) -> None:
        found=False
        def rows():
            nonlocal found
            for row in self.store.read(self.store.transactions):
                if row['id']==identifier:
                    found=True
                    if changes is not None: yield Transaction.create(row|changes,self.categories()).record()
                else: yield row
            if not found: raise ValueError('없는 데이터: '+identifier)
        self.store.write(self.store.transactions,rows())
    def filtered(self, options) -> Iterator[dict]:
        start=getattr(options,'date_from',None); end=getattr(options,'to',None)
        month=getattr(options,'month',None)
        if start: check_date(start)
        if end: check_date(end)
        if start and end and start>end: raise ValueError('--from은 --to보다 늦을 수 없습니다')
        if month: check_month(month)
        for row in self.store.read(self.store.transactions):
            if start and row['date']<start: continue
            if end and row['date']>end: continue
            if month and not row['date'].startswith(month): continue
            if getattr(options,'category',None) and row['category']!=options.category: continue
            if getattr(options,'type',None) and row['type']!=options.type: continue
            if getattr(options,'q',None) and options.q.casefold() not in row['memo'].casefold(): continue
            if getattr(options,'tag',None) and options.tag not in row['tags']: continue
            yield row
    def summary(self, options) -> None:
        check_month(options.month)
        income=expense=count=0; categories=defaultdict(int)
        for row in self.filtered(options):
            count+=1
            if row['type']=='income': income+=row['amount']
            else: expense+=row['amount']; categories[row['category']]+=row['amount']
        if not count: print('데이터 없음')
        print(f'총 수입: {income}원\n총 지출: {expense}원\n잔액: {income-expense}원')
        for budget in self.store.read(self.store.budgets):
            if budget['month']==options.month:
                print(f"예산: {budget['amount']}원 (사용률 {expense/budget['amount']*100:.1f}%)")
                if expense>budget['amount']: print('[WARNING] 예산 초과')
        for i,(name,amount) in enumerate(sorted(categories.items(),key=lambda p:p[1],reverse=True)[:options.top],1):
            print(f'{i}) {name}: {amount}원')
    def import_csv(self, source: Path) -> int:
        # 먼저 임시 JSONL에 전 행 검증. 오류 발생 시 원본에 단 한 행도 반영하지 않는다.
        with tempfile.TemporaryDirectory() as directory:
            stage=Path(directory)/'stage.jsonl'; count=0
            with source.open(encoding='utf-8-sig',newline='') as stream,stage.open('w',encoding='utf-8') as target:
                reader=csv.DictReader(stream)
                if not reader.fieldnames or not set(SCHEMA[:4]).issubset(reader.fieldnames): raise ValueError('CSV 필수 헤더: date,type,category,amount')
                for index,row in enumerate(reader,2):
                    try:
                        if None in row or any(v is None for v in row.values()): raise ValueError('CSV 열 개수가 잘못되었습니다')
                        item=Transaction.create(row,self.categories())
                    except (ValueError,KeyError) as error: raise ValueError(f'CSV {index}행: {error}') from error
                    target.write(json.dumps(item.record(),ensure_ascii=False)+'\n'); count+=1
            self.store.write(self.store.transactions,chain(self.store.read(self.store.transactions),self.store.read(stage)))
        return count
    def export_csv(self, options) -> int:
        if not options.month and not (options.date_from and options.to): raise ValueError('--month 또는 --from과 --to가 필요합니다')
        target=Path(options.out)
        if target.resolve().parent==self.store.directory.resolve() and target.name in ('transactions.jsonl','categories.jsonl','budgets.jsonl','.lock'):
            raise ValueError('저장소 파일을 내보내기 대상으로 사용할 수 없습니다')
        name=None; count=0
        try:
            with tempfile.NamedTemporaryFile('w',dir=target.parent,encoding='utf-8',newline='',delete=False) as stream:
                name=stream.name; writer=csv.DictWriter(stream,fieldnames=SCHEMA); writer.writeheader()
                for row in self.store.newest(self.filtered(options)):
                    writer.writerow({k:','.join(row[k]) if k=='tags' else row[k] for k in SCHEMA}); count+=1
                stream.flush(); os.fsync(stream.fileno())
            os.replace(name,target)
        finally:
            if name and os.path.exists(name): os.unlink(name)
        return count
''',
'main.py': r'''
import argparse
import functools
import sys
import time
from pathlib import Path
from itertools import islice
from model import check_month,positive
from storage import Store
from service import BudgetService


# guarded: CLI 오류를 사용자 메시지와 종료 코드로 변환한다.
def guarded(function):
    """CLI 공통 예외/종료 코드와 시간 측정을 비즈니스 로직에서 분리."""
    @functools.wraps(function)
    def wrapper():
        started=time.perf_counter()
        try: function(); return 0
        except (ValueError,OSError,KeyError,EOFError) as error:
            print(f'[오류] {error}\n[힌트] --help와 입력 형식, 파일 권한을 확인하세요.',file=sys.stderr); return 1
        except KeyboardInterrupt: print('취소했습니다',file=sys.stderr); return 130
        finally: print(f'[실행시간] {time.perf_counter()-started:.3f}초',file=sys.stderr)
    return wrapper

# natural: argparse에서 사용할 양의 정수 변환기다.
def natural(value):
    try: return positive(value)
    except ValueError as error: raise argparse.ArgumentTypeError(str(error)) from error

# filters: 기간 검색 공통 옵션을 등록한다.
def filters(parser):
    parser.add_argument('--from',dest='date_from'); parser.add_argument('--to'); parser.add_argument('--month')

@guarded
# main: 명령행을 해석하고 서비스 기능을 호출한다.
def main():
    parser=argparse.ArgumentParser(description='JSONL 용돈 기입장')
    parser.add_argument('--data-dir',type=Path,default=Path('data'))
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('add',help='대화형 거래 추가')
    listing=commands.add_parser('list'); listing.add_argument('--limit',type=natural,default=20)
    search=commands.add_parser('search'); filters(search)
    for name in ('category','type','q','tag'): search.add_argument('--'+name)
    summary=commands.add_parser('summary'); summary.add_argument('--month',required=True); summary.add_argument('--top',type=natural,default=3)
    delete=commands.add_parser('delete'); delete.add_argument('--id',required=True)
    update=commands.add_parser('update'); update.add_argument('--id',required=True)
    for name in ('date','type','category','amount','memo','tags'): update.add_argument('--'+name)
    category=commands.add_parser('category').add_subparsers(dest='action',required=True)
    category.add_parser('list')
    for action in ('add','remove'): category.add_parser(action).add_argument('--name')
    budgets=commands.add_parser('budget').add_subparsers(dest='action',required=True)
    setting=budgets.add_parser('set'); setting.add_argument('--month',required=True); setting.add_argument('--amount',type=natural,required=True)
    budgets.add_parser('list')
    importing=commands.add_parser('import'); importing.add_argument('--from',dest='source',type=Path,required=True)
    exporting=commands.add_parser('export'); exporting.add_argument('--out',required=True); filters(exporting)
    options=parser.parse_args(); store=Store(options.data_dir); service=BudgetService(store)
    with store.lock():
        if options.command=='add':
            print('카테고리:',', '.join(service.categories()))
            values={name:input(label).strip() for name,label in [('date','날짜(YYYY-MM-DD): '),('type','타입(income/expense): '),('category','카테고리: '),('amount','금액(양수 정수): '),('memo','메모(선택): '),('tags','태그(쉼표): ')]}
            print('[저장 완료] id='+service.add(values))
        elif options.command in ('list','search'):
            rows=store.newest(store.read(store.transactions) if options.command=='list' else service.filtered(options))
            found=False
            try:
                for row in islice(rows,options.limit) if options.command=='list' else rows:
                    found=True; print(' | '.join(str(row[k]) for k in ('id','date','type','category','amount','memo')))
            finally: rows.close()
            if not found: print('데이터 없음')
        elif options.command=='summary': service.summary(options)
        elif options.command in ('update','delete'):
            changes={k:v for k,v in vars(options).items() if k in ('date','type','category','amount','memo','tags') and v is not None}
            if options.command=='update' and not changes: raise ValueError('수정할 옵션을 지정하세요')
            service.change(options.id,changes if options.command=='update' else None); print('[완료] '+options.id)
        elif options.command=='category':
            names=service.categories()
            if options.action=='list': print('\n'.join(names)); return
            name=(options.name or input('카테고리명: ')).strip()
            if not name: raise ValueError('빈 카테고리명')
            if options.action=='add':
                if name in names: raise ValueError('이미 등록된 카테고리')
                names.append(name)
            else:
                if name not in names: raise ValueError('없는 카테고리')
                if any(row['category']==name for row in store.read(store.transactions)): raise ValueError('사용 중 카테고리는 삭제할 수 없습니다')
                names.remove(name)
                if not names: raise ValueError('최소 한 카테고리는 유지하세요')
            store.write(store.categories,({'name':n} for n in names)); print('[완료] '+name)
        elif options.command=='budget':
            if options.action=='list':
                for row in store.read(store.budgets): print(row['month'],row['amount'])
            else:
                check_month(options.month)
                def rows():
                    for row in store.read(store.budgets):
                        if row['month']!=options.month: yield row
                    yield {'month':options.month,'amount':options.amount}
                store.write(store.budgets,rows()); print('[저장 완료] 예산')
        elif options.command=='import': print(f'[완료] imported={service.import_csv(options.source)}, skipped=0')
        elif options.command=='export': print(f'[완료] {options.out} ({service.export_csv(options)} records)')

if __name__=='__main__': sys.exit(main())
''',
}

def generate(destination: Path) -> None:
    """기존 파일을 덮어쓰지 않는, 반복 실행 가능한 프로젝트 생성기."""
    for relative, source in FILES.items():
        target = destination / relative
        if target.exists() and target.read_text(encoding="utf-8") != source.lstrip("\n"):
            raise SystemExit(f"기존 파일 보존: {target}. 다른 --out 폴더를 지정하세요.")
    for relative, source in FILES.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.lstrip("\n"), encoding="utf-8")
    print(f"생성 완료: {destination.resolve()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path("generated") / Path(__file__).stem)
    args = parser.parse_args()
    generate(args.out)
