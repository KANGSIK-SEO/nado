#!/usr/bin/env python3
'b5-1 | 정보를 엄청 빠르게 찾아주는 작은 저장소 만들기\n실행: python3 b5-1.py → python3 generated/b5-1/main.py\n표준 라이브러리만 사용. dict/set/collections/heapq 사용 없이 직접 구현한다.\n해시맵 평균 O(1), 최악 O(n); 확장은 분할상환 O(1). 연결 리스트 이동 O(1).\nTTL 힙 O(log n), 만료는 모든 명령 시작 시 정리. 시간은 monotonic 사용.\nTTL 변경/삭제는 세대 번호로 무효화(lazy deletion), 과도한 잔여 힙은 재구성한다.\nCONFIG로 제한 축소 시에도 즉시 LRU 제거. OOM SET은 기존 값/TTL을 보존한다.\n메모리 산식은 UTF-8 키+값 바이트만 계산하며 실제 프로세스 RSS와 다르다.\n예시의 user:2(Bob)+user:3(Charlie)는 22가 아니라 6+3+6+7=22 바이트이다.\n'

from pathlib import Path
import argparse

# 각 문자열은 해당 경로에 생성되는 실제 소스입니다. 설명도 소스 주석에 담습니다.
FILES = {
'dll.py': r'''
class Node:
    """노드는 데이터와 양방향 포인터를 보유한다."""
    def __init__(self, data=None):
        self.data, self.prev, self.next = data, None, None

class LinkedList:
    def __init__(self):
        self.head, self.tail = Node(), Node()
        self.head.next, self.tail.prev = self.tail, self.head

    def insert_front(self, data):
        node = Node(data)
        self._insert(self.head, node, self.head.next)
        return node

    def insert_back(self, data):
        node = Node(data)
        self._insert(self.tail.prev, node, self.tail)
        return node

    def _insert(self, left, node, right):
        left.next, node.prev, node.next, right.prev = node, left, right, node

    def remove_node(self, node):
        node.prev.next, node.next.prev = node.next, node.prev
        node.prev = node.next = None
        return node.data

    def remove_front(self):
        return None if self.head.next is self.tail else self.remove_node(self.head.next)

    def remove_back(self):
        return None if self.tail.prev is self.head else self.remove_node(self.tail.prev)

    def move_to_front(self, node):
        self.remove_node(node)
        self._insert(self.head, node, self.head.next)

    def __iter__(self):
        node = self.head.next
        while node is not self.tail:
            yield node.data
            node = node.next
''',
'hashmap.py': r'''
class HashMap:
    """배열 버킷 + 체이닝. 내장 hash도 사용하지 않는다."""
    def __init__(self):
        self.buckets = [[] for _ in range(8)]
        self.count = 0

    def _index(self, key):
        value = 2166136261
        for byte in key.encode('utf-8'):
            value = ((value ^ byte) * 16777619) & 0xffffffff
        return value % len(self.buckets)

    def put(self, key, value):
        bucket = self.buckets[self._index(key)]
        for pair in bucket:
            if pair[0] == key:
                pair[1] = value
                return
        bucket.append([key, value])
        self.count += 1
        if self.count / len(self.buckets) > .75:
            old = self.buckets
            self.buckets = [[] for _ in range(len(old) * 2)]
            self.count = 0
            for bucket in old:
                for key, value in bucket:
                    self.put(key, value)

    def get(self, key):
        for candidate, value in self.buckets[self._index(key)]:
            if key == candidate:
                return value
        return None

    def remove(self, key):
        bucket = self.buckets[self._index(key)]
        for i, pair in enumerate(bucket):
            if pair[0] == key:
                self.count -= 1
                return bucket.pop(i)[1]
        return None

    def contains(self, key):
        return any(pair[0] == key for pair in self.buckets[self._index(key)])

    def keys(self):
        return [pair[0] for bucket in self.buckets for pair in bucket]

    def size(self):
        return self.count
''',
'heap.py': r'''
class MinHeap:
    """완전 이진 트리를 배열로 저장: 부모 (i-1)//2, 자식 2i+1/2i+2."""
    def __init__(self):
        self.items = []

    def size(self):
        return len(self.items)

    def peek(self):
        return self.items[0] if self.items else None

    def push(self, value):
        self.items.append(value)
        self._heapify_up(len(self.items)-1)

    def _heapify_up(self, i):
        while i > 0:
            p = (i-1)//2
            if self.items[p] <= self.items[i]:
                break
            self.items[p], self.items[i] = self.items[i], self.items[p]
            i = p

    def pop(self):
        if not self.items:
            return None
        value, last = self.items[0], self.items.pop()
        if self.items:
            self.items[0] = last
            self._heapify_down(0)
        return value

    def _heapify_down(self, i):
        n = len(self.items)
        while 2*i+1 < n:
            child = 2*i+1
            if child+1 < n and self.items[child+1] < self.items[child]:
                child += 1
            if self.items[i] <= self.items[child]:
                break
            self.items[i], self.items[child] = self.items[child], self.items[i]
            i = child
''',
'main.py': r'''
import json
import shlex
import time
from dll import LinkedList
from hashmap import HashMap
from heap import MinHeap

class Entry:
    def __init__(self, key, value):
        self.key, self.value = key, value
        self.deadline, self.version, self.node = None, 0, None
        self.cost = len(key.encode()) + len(value.encode())

class MiniRedis:
    def __init__(self, clock=time.monotonic):
        self.data, self.lru, self.expiry = HashMap(), LinkedList(), MinHeap()
        self.used_memory = self.maxmemory = self.evicted_keys = self.sequence = 0
        self.clock = clock

    def _delete(self, key):
        entry = self.data.remove(key)
        if entry is None:
            return 0
        self.lru.remove_node(entry.node)
        self.used_memory -= entry.cost
        # 힙 항목은 세대 번호와 데이터 존재 여부로 논리적으로 삭제된다.
        return 1

    def _expire(self):
        now = self.clock()
        while self.expiry.size() and self.expiry.peek()[0] <= now:
            deadline, version, key = self.expiry.pop()
            entry = self.data.get(key)
            if entry and entry.version == version and entry.deadline == deadline:
                self._delete(key)
        if self.expiry.size() > max(64, 2*self.data.size()):
            self.expiry = MinHeap()
            for key in self.data.keys():
                entry = self.data.get(key)
                if entry.deadline is not None:
                    self.expiry.push((entry.deadline, entry.version, key))

    def _evict(self):
        while self.maxmemory and self.used_memory > self.maxmemory:
            self._delete(self.lru.tail.prev.data)
            self.evicted_keys += 1

    def execute(self, line):
        self._expire()
        try:
            words = shlex.split(line)
        except ValueError:
            return '(error) ERR Invalid quotes'
        if not words:
            return ''
        cmd, args = words[0].upper(), words[1:]
        commands = [('SET',2),('GET',1),('DEL',1),('EXISTS',1),('DBSIZE',0),
                    ('KEYS',0),('CONFIG',3),('INFO',1),('EXPIRE',2),('TTL',1)]
        expected = next((n for name,n in commands if name == cmd), None)
        if expected is None:
            return f"(error) ERR unknown command '{words[0]}'"
        if len(args) != expected:
            return f"(error) ERR wrong number of arguments for '{cmd}' command"
        if cmd == 'SET':
            key, value = args
            entry = Entry(key, value)
            if self.maxmemory and entry.cost > self.maxmemory:
                return "(error) OOM command not allowed when used_memory > 'maxmemory'"
            self._delete(key)
            entry.node = self.lru.insert_front(key)
            self.data.put(key, entry)
            self.used_memory += entry.cost
            self._evict()
            return 'OK'
        if cmd == 'GET':
            entry = self.data.get(args[0])
            if entry is None:
                return '(nil)'
            self.lru.move_to_front(entry.node)
            return json.dumps(entry.value, ensure_ascii=False)
        if cmd == 'DEL':
            return f'(integer) {self._delete(args[0])}'
        if cmd == 'EXISTS':
            return f'(integer) {int(self.data.contains(args[0]))}'
        if cmd == 'DBSIZE':
            return f'(integer) {self.data.size()}'
        if cmd == 'KEYS':
            return '\n'.join(f'{i}. {json.dumps(k, ensure_ascii=False)}' for i,k in enumerate(self.data.keys(),1)) or '(empty array)'
        if cmd == 'INFO':
            if args[0].lower() != 'memory':
                return '(error) ERR unsupported INFO section'
            return f'used_memory:{self.used_memory}\nmaxmemory:{self.maxmemory}\nevicted_keys:{self.evicted_keys}'
        if cmd == 'CONFIG':
            if args[:2] != ['SET','maxmemory'] and [a.lower() for a in args[:2]] != ['set','maxmemory']:
                return '(error) ERR unsupported CONFIG'
            try:
                amount = int(args[2])
                if amount < 0: raise ValueError()
            except ValueError:
                return '(error) ERR value is not an integer or out of range'
            self.maxmemory = amount
            self._evict()
            return 'OK'
        if cmd == 'EXPIRE':
            try:
                seconds = int(args[1])
                if abs(seconds) > 2147483647: raise ValueError()
            except ValueError:
                return '(error) ERR value is not an integer or out of range'
            entry = self.data.get(args[0])
            if not entry: return '(integer) 0'
            if seconds <= 0:
                self._delete(args[0])
            else:
                self.sequence += 1
                entry.version, entry.deadline = self.sequence, self.clock()+seconds
                self.expiry.push((entry.deadline, entry.version, args[0]))
            return '(integer) 1'
        entry = self.data.get(args[0])
        remaining = -2 if entry is None else (-1 if entry.deadline is None else max(0,int(entry.deadline-self.clock())))
        return f'(integer) {remaining}'

if __name__ == '__main__':
    app = MiniRedis()
    while True:
        try:
            line = input('mini-redis> ')
            if line.strip().lower() in ('exit','quit'): break
            print(app.execute(line))
        except (EOFError, KeyboardInterrupt):
            print()
            break
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
