#!/usr/bin/env python3
## 쉬운 설명: Git 변경 내용을 읽어 AI에게 커밋이나 PR 설명을 부탁한다.
"""b3-2: git diff를 AI API에 보내 커밋/PR 초안을 출력한다.
실행: AI_API_KEY=... python3 b3-2.py commit --safe-mode
키는 환경변수로만 읽고 diff의 API key/token/email은 마스킹한다. 자동 commit/push는 하지 않는다.
"""
import argparse, json, os, re, subprocess, sys, urllib.request


# git: Git 명령을 실행하고 표준 출력을 반환한다.
def git(*args):
    p = subprocess.run(["git", *args], text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or "git 실패")
    return p.stdout


# ask: AI API에 프롬프트를 보내 생성 결과를 반환한다.
def ask(prompt, model, temperature, max_tokens):
    key = os.getenv("AI_API_KEY")
    if not key:
        raise RuntimeError("AI_API_KEY 환경변수가 없습니다")
    body = json.dumps(
        {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": "Senior developer. Follow the requested output format.",
                },
                {"role": "user", "content": prompt},
            ],
        }
    ).encode()
    req = urllib.request.Request(
        os.getenv("AI_API_URL", "https://api.openai.com/v1/chat/completions"),
        data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)["choices"][0]["message"]["content"].strip()


# main: 변경사항 수집부터 초안 출력까지의 전체 흐름을 실행한다.
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["commit", "pr"])
    p.add_argument("--model", default="gpt-4o-mini")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-tokens", type=int, default=700)
    p.add_argument("--safe-mode", action="store_true")
    a = p.parse_args()
    status = git("status", "--short")
    diff = git("diff")
    diff = re.sub(
        r"(?i)(api[_-]?key|token|password)(\s*[:=]\s*)[^\s]+", r"\1\2[REDACTED]", diff
    )
    diff = re.sub(r"[\w.+-]+@[\w.-]+", "[EMAIL]", diff)
    if a.safe_mode:
        status = "\n".join(status.splitlines()[:10])
        diff = "\n".join(diff.splitlines()[:200])
    if not status.strip() and not diff.strip():
        print("[INFO] 변경 사항이 없습니다.")
        return
    if a.command == "commit":
        prompt = "커밋 제목 72자 이내 1줄과 핵심 변경 불릿 2개를 만들어라.\n"
    else:
        prompt = "첫 줄은 PR 제목, 다음에는 ## Why, ## What, ## How to Test 헤더와 각 1개 이상 불릿을 만들어라.\n"
    print(
        "[INFO] Git status/diff 수집 완료\n[INFO] AI API 요청 중...\n"
        + ask(
            prompt + "STATUS\n" + status + "\nDIFF\n" + diff,
            a.model,
            a.temperature,
            a.max_tokens,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("[ERROR]", error, file=sys.stderr)
        sys.exit(1)
