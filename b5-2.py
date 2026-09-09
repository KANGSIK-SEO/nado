#!/usr/bin/env python3
"""b5-2 | 파일 변경 이력을 흉내 내는 Mini Git (메타데이터만, 실제 파일 추적 없음)
실행: python3 b5-2.py (Python 3.10+, 표준 라이브러리)
INIT "Alice" → COMMIT "Initial commit" → BRANCH feature → SWITCH feature
LOG는 모든 브랜치의 커밋을 부모 우선으로 출력한다.
정렬: 직접 구현한 안정 병합정렬. 평균/최악 O(n log n), 추가 공간 O(n).
탐색: 조상 DFS O(V+E), 최단경로 BFS O(V+E), 사전순 선택에 인접 정렬 비용 추가.
역색인: 단어를 split/lower로 정규화. 여러 단어 검색은 토큰 AND 교집합.
해시: 고정 길이 증가 번호로 세션 내 충돌 방지. 새 부모는 기존 커밋만 참조하여 DAG 유지.
INIT 재호출은 데이터 유실을 방지하도록 차단한다. 프로그램 종료 시 데이터는 사라진다.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import shlex


# merge_sort: 표준 sorted/list.sort 없이 안정 병합 정렬을 수행한다.
def merge_sort(values, key=lambda x: x):
    """동률이면 왼쪽 항목을 먼저 선택해 안정성을 보장한다."""
    if len(values) <= 1:
        return list(values)
    middle = len(values) // 2
    left, right = merge_sort(values[:middle], key), merge_sort(values[middle:], key)
    result, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        if key(left[i]) <= key(right[j]):
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    return result + left[i:] + right[j:]


@dataclass
class Commit:
    hash: str
    message: str
    author: str
    timestamp: str
    parents: list[str]


class MiniGit:
    def __init__(self):
        self.commits, self.branches, self.keyword, self.author_index, self.edges = (
            {},
            {},
            {},
            {},
            {},
        )
        self.user, self.branch, self.counter = None, None, 0

    def add_commit(self, message, extra=None):
        parents = [self.branches[self.branch]] if self.branches[self.branch] else []
        if extra and extra not in parents:
            parents.append(extra)
        self.counter += 1
        identifier = f"{self.counter:016x}"
        commit = Commit(
            identifier,
            message,
            self.user,
            datetime.now(timezone.utc).isoformat(),
            parents,
        )
        self.commits[identifier] = commit
        self.edges[identifier] = list(parents)
        for parent in parents:
            self.edges[parent].append(identifier)
        self.branches[self.branch] = identifier
        for token in set(message.lower().split()):
            self.keyword.setdefault(token, []).append(identifier)
        self.author_index.setdefault(self.user, []).append(identifier)
        return f"[{self.branch} {identifier}] {message}"

    def ancestors(self, identifier):
        result, visited, stack = [], set(), list(self.commits[identifier].parents)
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            result.append(current)
            stack.extend(self.commits[current].parents)
        return result

    def path(self, start, end):
        # 정렬된 이웃 순서의 BFS: 같은 깊이에서 사전순 최소 경로를 먼저 발견.
        queue, parents, index = [start], {start: None}, 0
        while index < len(queue):
            current = queue[index]
            index += 1
            if current == end:
                path = []
                while current is not None:
                    path.append(current)
                    current = parents[current]
                return "Path: " + " -> ".join(path[::-1])
            for neighbor in merge_sort(self.edges[current]):
                if neighbor not in parents:
                    parents[neighbor] = current
                    queue.append(neighbor)
        return "No path"

    def topological(self):
        indegree = {h: len(c.parents) for h, c in self.commits.items()}
        children = {h: [] for h in self.commits}
        for h, c in self.commits.items():
            for p in c.parents:
                children[p].append(h)
        queue = [h for h in self.commits if indegree[h] == 0]
        index, result = 0, []
        while index < len(queue):
            h = queue[index]
            index += 1
            result.append(self.commits[h])
            for child in children[h]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
        return result

    def display(self, commits):
        return (
            "\n".join(
                f"commit {c.hash} ({c.author}, {c.timestamp})\n{c.message}"
                for c in commits
            )
            or "No commits"
        )

    def execute(self, line):
        try:
            words = shlex.split(line)
        except ValueError:
            return "Invalid args"
        if not words:
            return ""
        cmd, args = words[0].upper(), words[1:]
        if cmd == "INIT":
            if len(args) != 1 or not args[0].strip():
                return "Invalid args"
            if self.user is not None:
                return "Already initialized"
            self.user, self.branch, self.branches = args[0], "main", {"main": None}
            return (
                "Initialized repository.\nCurrent branch: main\nCurrent user: "
                + self.user
            )
        if self.user is None:
            return "Run INIT <user_name> first"
        if cmd in ("BRANCH", "SWITCH", "COMMIT", "ANCESTORS", "SEARCH", "MERGE"):
            if len(args) != 1 or not args[0].strip():
                return "Invalid args"
        elif cmd == "PATH":
            if len(args) != 2:
                return "Invalid args"
        elif cmd == "LOG":
            if len(args) > 1 or (
                args and args[0] not in ("--sort-by=date", "--sort-by=author")
            ):
                return "Invalid args"
        else:
            return "Unknown command: " + words[0]
        if cmd == "BRANCH":
            if args[0] in self.branches:
                return "Branch already exists: " + args[0]
            self.branches[args[0]] = self.branches[self.branch]
            return "Created branch: " + args[0]
        if cmd in ("SWITCH", "MERGE"):
            if args[0] not in self.branches:
                return "Unknown branch: " + args[0]
            if cmd == "SWITCH":
                self.branch = args[0]
                return "Switched to branch: " + args[0]
            return self.add_commit("Merge " + args[0], self.branches[args[0]])
        if cmd == "COMMIT":
            return self.add_commit(args[0])
        if cmd in ("PATH", "ANCESTORS"):
            for h in args:
                if h not in self.commits:
                    return "Unknown commit: " + h
            return (
                self.path(*args)
                if cmd == "PATH"
                else self.display([self.commits[h] for h in self.ancestors(args[0])])
            )
        if cmd == "SEARCH":
            if args[0].startswith("--author="):
                ids = self.author_index.get(args[0][9:], [])
            else:
                tokens = args[0].lower().split()
                candidates = set(self.keyword.get(tokens[0], []))
                for token in tokens[1:]:
                    candidates.intersection_update(self.keyword.get(token, []))
                ids = merge_sort(list(candidates))
            return self.display([self.commits[h] for h in ids])
        commits = self.topological()
        if args:
            commits = merge_sort(
                commits,
                key=(
                    (lambda c: c.timestamp)
                    if args[0].endswith("date")
                    else (lambda c: c.author)
                ),
            )
        return self.display(commits)


if __name__ == "__main__":
    app = MiniGit()
    while True:
        try:
            line = input("mini-git> ")
            if line.strip().lower() in ("exit", "quit"):
                break
            print(app.execute(line))
        except (EOFError, KeyboardInterrupt):
            print()
            break
