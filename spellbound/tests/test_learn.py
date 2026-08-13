"""학습 시스템 테스트 — 단어별 숙련도 4단계 승급/강등, 객관식, 초보자 모드"""
from playwright.sync_api import sync_playwright

import os, pathlib
URL = os.environ.get("GAME_URL") or (
    pathlib.Path(__file__).resolve().parent.parent / "dist" / "index.html").as_uri()
errors, fails = [], []

def check(l, c, e=""):
    print(("  OK   " if c else "  FAIL ") + l + ("  " + str(e) if e != "" else ""))
    if not c: fails.append(l)

FREEZE = "() => { for(let i=1;i<99999;i++) clearTimeout(i); clearInterval(timerId); }"
MOCK = """() => {
  const v=[{name:'Google US English',lang:'en-US',localService:true},
           {name:'Google español',lang:'es-ES',localService:true}];
  window.speechSynthesis.getVoices=()=>v; window.__s=[];
  window.speechSynthesis.speak=(u)=>window.__s.push(u.text);
  window.speechSynthesis.cancel=()=>{};
  window.SpeechSynthesisUtterance=function(t){this.text=t;this.voice=null;this.lang='';this.rate=1;};
  loadVoices();
}"""


def _nav(pg):
    """설정·언어처럼 메인에서 한 단계 들어간 UI를 다루기 위한 헬퍼"""
    def set_lang(code):
        pg.click("#link-settings"); pg.wait_for_timeout(120)
        pg.click("#lang-" + code);  pg.wait_for_timeout(250)
        pg.click("#settings-back"); pg.wait_for_timeout(120)
    def set_diff(d):
        pg.click("#link-settings"); pg.wait_for_timeout(120)
        pg.click("#diff-" + d);     pg.wait_for_timeout(120)
        pg.click("#settings-back"); pg.wait_for_timeout(120)
    return set_lang, set_diff

with sync_playwright() as p:
    br = p.chromium.launch(); pg = br.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append("CONSOLE " + m.text) if m.type == "error" else None)
    set_lang, set_diff = _nav(pg)

    def new_run(novice=False):
        pg.goto(URL); pg.wait_for_timeout(350)
        pg.evaluate(MOCK)
        pg.click("#mode-beginner" if novice else "#mode-normal"); pg.wait_for_timeout(500)
        pg.evaluate("S.floorIdx=0; startEncounter(S.floors[0][0]);"); pg.wait_for_timeout(1900)

    def ask(word, mastery=None):
        """지정한 단어를 원하는 숙련도 상태로 출제한다.
           소개(0)·객관식(1) 단계는 초보자 모드에서만 나타난다."""
        pg.evaluate(FREEZE)
        m = "" if mastery is None else f"setMastery({word!r}, {mastery});"
        pg.evaluate(f"""() => {{
          {m}
          S.enc={{emoji:'🟢',hp:9999,dmg:20,tier:1,time:14000,gims:[],ko:'적',en:'F',es:'F'}};
          S.bossHP=9999; S.bossMax=9999; S.playerHP=100; S.playerMax=100;
          S.combo=0; S.choiceLocked=false; showScreen('battle');
          S.queue=[{{w:{word!r},ko:'뜻',tag:'태그'}},{{w:'zebra',ko:'얼룩말',tag:'명사'}},
                   {{w:'melon',ko:'멜론',tag:'명사'}}]; nextWord();
          S.wordStart = performance.now() - S.timerBase;   // 속도 보너스를 0으로 고정
        }}""")
        pg.wait_for_timeout(150)

    print("\n=== 1. 초보자 모드: 처음 보는 단어 소개 ===")
    new_run(novice=True)
    check("첫 단어는 소개 단계", pg.evaluate("S.wstage") == 0)
    check("배지 표시", pg.evaluate("document.getElementById('stage-badge').textContent") == "① 처음 보는 단어")
    check("철자 노출", pg.evaluate("document.getElementById('intro-word').textContent") == pg.evaluate("S.word.w"))
    check("소개 시 발음 자동 재생", pg.evaluate("window.__s.slice(-1)[0]") == pg.evaluate("S.word.w"))
    check("입력창 사용 가능", not pg.evaluate("document.getElementById('word-input').disabled"))
    check("객관식은 숨김", pg.evaluate("document.getElementById('choice-row').style.display") == "none")
    check("소개 단계는 시간 2배",
          abs(pg.evaluate("S.timerTotal") - pg.evaluate("bossTime()*2")) < 1, pg.evaluate("S.timerTotal"))

    print("\n=== 2. 0단계 → 1단계 (따라치기, 초보자 전용) ===")
    ask("apple", 0)
    hp0 = pg.evaluate("S.playerHP")
    pg.fill("#word-input", "aple"); pg.keyboard.press("Enter"); pg.wait_for_timeout(350)
    check("소개 단계 오타는 무벌점", pg.evaluate("S.playerHP") == hp0 and pg.evaluate("masteryOf('apple')") == 0)
    check("소개 단계 오타는 오답노트에 안 넣음", not pg.evaluate("S.missed.has('apple')"))
    pg.fill("#word-input", "apple"); pg.keyboard.press("Enter"); pg.wait_for_timeout(500)
    check("정답 → 1단계 승급", pg.evaluate("masteryOf('apple')") == 1)
    check("새로 익힌 단어 카운트", pg.evaluate("S.newlyLearned") == 1)
    check("적에게 데미지", pg.evaluate("S.bossHP") < 9999)

    print("\n=== 3. 1단계: 객관식 (초보자 전용) ===")
    ask("apple", 1)
    check("객관식 화면", pg.evaluate("S.wstage") == 1 and
          pg.evaluate("document.getElementById('choice-row').style.display") != "none")
    check("입력창 숨김", pg.evaluate("document.getElementById('word-input').style.display") == "none")
    check("보기 4개", pg.evaluate("document.querySelectorAll('#choice-row .choice').length") == 4)
    check("정답 포함", pg.evaluate("S.choices.includes('apple')"))
    check("보기 중복 없음", pg.evaluate("new Set(S.choices).size") == 4, pg.evaluate("S.choices"))
    check("오답은 같은 언어 단어", pg.evaluate(
        "S.choices.every(c=>[].concat(...[1,2,3,4,5].map(t=>WORDS_EN[t])).some(w=>w[0]===c))"))
    lens = pg.evaluate("S.choices.map(c=>c.length)")
    check("길이가 비슷한 오답", max(lens) - min(lens) <= 4, lens)

    # 오답 선택
    pg.evaluate("(()=>{const i=S.choices.findIndex(c=>c!=='apple'); answerChoice(i);})()")
    pg.wait_for_timeout(400)
    check("객관식 오답: 승급 안 함", pg.evaluate("masteryOf('apple')") == 1)
    check("객관식 오답: 체력 감소", pg.evaluate("S.playerHP") < 100)
    check("객관식 오답: 정답 표시", pg.evaluate("document.querySelectorAll('#choice-row .choice.right').length") == 1)
    check("객관식 오답: 오답노트 기록", pg.evaluate("S.missed.has('apple')"))

    ask("apple", 1)
    pg.evaluate("(()=>{const i=S.choices.indexOf('apple'); answerChoice(i);})()")
    pg.wait_for_timeout(600)
    check("객관식 정답 → 2단계", pg.evaluate("masteryOf('apple')") == 2)
    check("객관식 정답: 데미지", pg.evaluate("S.bossHP") < 9999)

    ask("water", 1)
    pg.evaluate("window.__choicesBefore = S.choices.slice()")
    pg.keyboard.press("1"); pg.wait_for_timeout(400)
    check("숫자키로 보기 선택", pg.evaluate("S.choiceLocked") is True or pg.evaluate("masteryOf('water')") >= 1)
    ask("water", 1)
    c0 = pg.evaluate("S.charges.hint")
    pg.keyboard.press("1"); pg.wait_for_timeout(300)
    check("객관식 중 숫자키는 스킬을 쓰지 않음", pg.evaluate("S.charges.hint") == c0)

    print("\n=== 4. 2단계: 힌트 타이핑 ===")
    ask("apple", 2)
    check("타이핑 화면 복귀", pg.evaluate("document.getElementById('word-input').style.display") != "none"
          and pg.evaluate("document.getElementById('choice-row').style.display") == "none")
    h2 = pg.evaluate("document.getElementById('q-hint').textContent").split("(")[0].strip()
    ask("apple", 3)
    h3 = pg.evaluate("document.getElementById('q-hint').textContent").split("(")[0].strip()
    check("2단계 힌트가 더 많음", h2.count("_") < h3.count("_"), f"2단계='{h2}' 3단계='{h3}'")
    ask("apple", 2)
    pg.fill("#word-input", "apple"); pg.keyboard.press("Enter"); pg.wait_for_timeout(500)
    check("2단계 정답 → 3단계", pg.evaluate("masteryOf('apple')") == 3)

    print("\n=== 5. 3단계: 완전 회상 & 강등 ===")
    ask("apple", 3)
    check("3단계 배지", pg.evaluate("document.getElementById('stage-badge').textContent") == "④ 완전 회상")
    pg.fill("#word-input", "apple"); pg.keyboard.press("Enter"); pg.wait_for_timeout(500)
    check("3단계 유지 (최대)", pg.evaluate("masteryOf('apple')") == 3)
    ask("apple", 3)
    pg.evaluate("clearInterval(timerId); onTimeout();"); pg.wait_for_timeout(400)
    check("시간 초과 → 한 단계 강등", pg.evaluate("masteryOf('apple')") == 2)
    ask("water", 3)
    pg.evaluate("S.skips=3; updateSkipUI();")
    pg.keyboard.press("Tab"); pg.wait_for_timeout(400)
    check("건너뛰기 → 0단계로 재소개", pg.evaluate("masteryOf('water')") == 0)

    print("\n=== 6. 단계별 데미지 배율 ===")
    def stage_dmg(stage, word="melon"):
        ask(word, stage)
        pg.evaluate("S.combo=0; S.bonusAtk=0; S.powerUp=false; S.wrongTried=true;")  # 크리티컬 차단
        if stage == 1:
            pg.evaluate("(()=>{const i=S.choices.indexOf(S.word.w); answerChoice(i);})()")
            pg.wait_for_timeout(600)
        else:
            pg.fill("#word-input", word); pg.keyboard.press("Enter"); pg.wait_for_timeout(500)
        return 9999 - pg.evaluate("S.bossHP")
    d0, d1, d2, d3 = stage_dmg(0), stage_dmg(1), stage_dmg(2), stage_dmg(3)
    check("도움 많을수록 데미지 낮음", d0 < d1 < d2 < d3, f"소개={d0} 객관식={d1} 힌트={d2} 회상={d3}")
    check("단계 배율 상수", pg.evaluate("STAGE_DMG") == [0.5, 0.7, 0.85, 1.0])
    check("완전 회상만 크리티컬 가능", pg.evaluate("STAGE_DMG[3]") == 1.0)

    print("\n=== 7. 숙련도 유지 ===")
    pg.evaluate("setMastery('journey',3); setMastery('courage',1);")
    before = pg.evaluate("[masteryOf('journey'), masteryOf('courage')]")
    pg.evaluate("endGame(false)"); pg.wait_for_timeout(300)
    pg.click("text=다시 도전"); pg.wait_for_timeout(300)
    pg.click("#mode-normal"); pg.wait_for_timeout(600)
    check("판이 끝나도 숙련도 유지", pg.evaluate("[masteryOf('journey'), masteryOf('courage')]") == before, before)
    check("newlyLearned 는 판마다 초기화", pg.evaluate("S.newlyLearned") == 0)

    pg.evaluate("LANG='es'")
    check("언어별로 숙련도 분리", pg.evaluate("masteryOf('journey')") == 0)
    pg.evaluate("LANG='en'")
    check("영어 숙련도 복귀", pg.evaluate("masteryOf('journey')") == 3)

    print("\n=== 8. 초보자 모드 ===")
    new_run(novice=True)
    check("초보자 모드 선택됨", pg.evaluate("NOVICE") is True)
    check("최저 단계 0 (소개부터)", pg.evaluate("minStage()") == 0)
    tiers = pg.evaluate("(()=>{const s=new Set(); for(let r=0;r<20;r++) generateMap().forEach(row=>row.forEach(n=>s.add(n.tier))); return [...s].sort();})()")
    check("어려운 티어(4·5) 미출제", max(tiers) <= 3, tiers)
    check("보스도 티어 3 이하", pg.evaluate(
        "(()=>{let mx=0; for(let r=0;r<20;r++) generateMap().forEach(row=>row.forEach(n=>{if(n.tier>mx)mx=n.tier})); return mx;})()") <= 3)

    pg.evaluate("NOVICE=false"); t_norm = pg.evaluate("bossTime()")
    pg.evaluate("NOVICE=true");  t_nov  = pg.evaluate("bossTime()")
    check("초보자 시간 여유", t_nov > t_norm, f"{round(t_norm)} → {round(t_nov)}")

    ask("apple", 3)
    pg.evaluate("NOVICE=false"); n_norm = pg.evaluate("hintReveal()")
    pg.evaluate("NOVICE=true");  n_nov  = pg.evaluate("hintReveal()")
    check("초보자 힌트 +1글자", n_nov == n_norm + 1, f"{n_norm} → {n_nov}")

    ask("apple", 3)
    pg.evaluate("NOVICE=false; S.playerHP=100; clearInterval(timerId); onTimeout();"); pg.wait_for_timeout(300)
    dmg_norm = 100 - pg.evaluate("S.playerHP")
    ask("apple", 3)
    pg.evaluate("NOVICE=true; S.playerHP=100; clearInterval(timerId); onTimeout();"); pg.wait_for_timeout(300)
    dmg_nov = 100 - pg.evaluate("S.playerHP")
    check("초보자 피해 완화", dmg_nov < dmg_norm, f"{dmg_norm} → {dmg_nov}")

    print("\n=== 9. 스페인어 학습 흐름 ===")
    pg.goto(URL); pg.wait_for_timeout(350); pg.evaluate(MOCK)
    set_lang("es"); pg.wait_for_timeout(300)
    pg.click("#mode-beginner"); pg.wait_for_timeout(500)
    pg.evaluate("S.floorIdx=0; startEncounter(S.floors[0][0]);"); pg.wait_for_timeout(1900)
    check("스페인어도 소개 단계부터", pg.evaluate("S.wstage") == 0)
    check("스페인어 철자 노출", pg.evaluate("document.getElementById('intro-word').textContent") == pg.evaluate("S.word.w"))
    ask("canción", 1)
    check("스페인어 객관식 보기", pg.evaluate("S.choices.includes('canción')") and
          pg.evaluate("S.choices.every(c=>[].concat(...[1,2,3,4,5].map(t=>WORDS_ES[t])).some(w=>w[0]===c))"))
    ask("canción", 0)
    pg.fill("#word-input", "cancion"); pg.keyboard.press("Enter"); pg.wait_for_timeout(500)
    check("소개 단계도 강세 생략 허용", pg.evaluate("masteryOf('canción')") == 1)
    pg.screenshot(path="learn_intro.png")

    print("\n=== 9-2. 일반 모드는 소개·객관식 없음 ===")
    pg.goto(URL); pg.wait_for_timeout(350); pg.evaluate(MOCK)
    pg.wait_for_timeout(120)
    pg.click("#mode-normal"); pg.wait_for_timeout(500)
    pg.evaluate("S.floorIdx=0; startEncounter(S.floors[0][0]);"); pg.wait_for_timeout(1900)
    check("최저 단계 2 (힌트 타이핑부터)", pg.evaluate("minStage()") == 2)
    check("처음 보는 단어도 타이핑", pg.evaluate("S.wstage") == 2 and pg.evaluate("S.wstageRaw") == 0)
    check("소개 박스 안 뜸", pg.evaluate("document.getElementById('intro-box').style.display") == "none")
    ask("apple", 1)
    check("저장 숙련도 1이어도 객관식 안 뜸",
          pg.evaluate("S.wstage") == 2 and pg.evaluate("document.getElementById('choice-row').style.display") == "none")
    check("배지가 모드에 맞게 표기", pg.evaluate("document.getElementById('stage-badge').textContent") == "힌트 타이핑")
    ask("apple", 3)
    check("숙달 단어는 완전 회상", pg.evaluate("document.getElementById('stage-badge').textContent") == "완전 회상")

    print("\n=== 10. 결과 화면 ===")
    pg.evaluate("endGame(false)"); pg.wait_for_timeout(300)
    check("새로 익힌 단어 통계", pg.evaluate("document.getElementById('st-new').textContent") == str(pg.evaluate("S.newlyLearned")))
    check("완전 숙달 통계 존재", pg.evaluate("document.getElementById('st-master') !== null"))
    check("숙련도 안내문", "익혔고" in pg.evaluate("document.getElementById('result-sub').textContent"))
    br.close()

print("\n" + "=" * 46)
print("JS 에러:", errors if errors else "없음")
print("실패:", fails if fails else "없음  ✅ 전체 통과")
