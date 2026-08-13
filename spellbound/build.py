#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPELLBOUND 빌드 스크립트

src/ 의 조각들을 합쳐 dist/index.html 한 장으로 만든다.
결과물은 외부 의존성이 전혀 없어서 파일을 더블클릭하면 그대로 실행된다.

    python3 build.py            # 빌드
    python3 build.py --check    # 빌드하지 않고 소스 무결성만 검사
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src"
DIST = ROOT / "dist"

SHELL = "engine.html"                 # 플레이스홀더를 가진 껍데기
PLACEHOLDER = "/*__WORDDATA__*/"      # 이 자리에 아래 파일들이 순서대로 들어간다
PARTS = ["data_en.js", "data_es.js", "art.js", "rogue.js"]


def fail(msg: str) -> None:
    print(f"[실패] {msg}", file=sys.stderr)
    sys.exit(1)


def check_words() -> None:
    """단어 데이터 무결성 검사 — 중복·결측·티어 수를 본다."""
    for path, var in [(SRC / "data_en.js", "WORDS_EN"), (SRC / "data_es.js", "WORDS_ES")]:
        if not path.exists():
            fail(f"{path.name} 이(가) 없습니다.")
        body = path.read_text(encoding="utf-8")
        seen, total = {}, 0
        for tier in range(1, 6):
            m = re.search(rf'(?<!\d){tier}\s*:\s*\[(.*?)\]\s*,?\s*(?=\d\s*:|\}}\s*;?\s*$)',
                          body, re.S)
            if not m:
                fail(f"{path.name}: 티어 {tier} 를 찾지 못했습니다.")
            rows = re.findall(r'\["(.*?)","(.*?)","(.*?)"\]', m.group(1))
            if not rows:
                fail(f"{path.name}: 티어 {tier} 가 비어 있습니다.")
            for word, ko, tag in rows:
                if not word or not ko or not tag:
                    fail(f"{path.name}: 빈 필드가 있습니다 → {word!r}/{ko!r}/{tag!r}")
                key = word.lower()
                if key in seen:
                    fail(f"{path.name}: '{word}' 가 티어 {seen[key]} 와 {tier} 에 중복됩니다.")
                seen[key] = tier
            total += len(rows)
            print(f"  {var} 티어{tier}: {len(rows):3d}개")
        print(f"  {var} 합계: {total}개 (중복 없음)")


def build() -> None:
    shell_path = SRC / SHELL
    if not shell_path.exists():
        fail(f"{SHELL} 이(가) src/ 에 없습니다.")
    shell = shell_path.read_text(encoding="utf-8")
    if PLACEHOLDER not in shell:
        fail(f"{SHELL} 에서 {PLACEHOLDER} 를 찾지 못했습니다.")

    chunks = []
    for name in PARTS:
        path = SRC / name
        if not path.exists():
            fail(f"{name} 이(가) src/ 에 없습니다.")
        chunks.append(f"/* ===== {name} ===== */\n" + path.read_text(encoding="utf-8"))

    out = shell.replace(PLACEHOLDER, "\n".join(chunks))
    if PLACEHOLDER in out:
        fail("플레이스홀더가 남아 있습니다.")

    DIST.mkdir(exist_ok=True)
    target = DIST / "index.html"
    target.write_text(out, encoding="utf-8")
    print(f"\n빌드 완료 → {target.relative_to(ROOT)}  ({target.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="SPELLBOUND 빌드")
    ap.add_argument("--check", action="store_true", help="빌드 없이 소스 검사만 수행")
    args = ap.parse_args()

    print("단어 데이터 검사")
    check_words()
    if not args.check:
        build()
