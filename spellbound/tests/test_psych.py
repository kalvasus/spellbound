"""심리 요소 테스트 — 전리품 뱅킹(손실 회피) / 위험 보너스 / 더블 오어 나씽"""
from playwright.sync_api import sync_playwright

import os, pathlib
URL = os.environ.get("GAME_URL") or (
    pathlib.Path(__file__).resolve().parent.parent / "dist" / "index.html").as_uri()
errors, fails = [], []

def check(l, c, e=""):
    print(("  OK   " if c else "  FAIL ") + l + ("  " + str(e) if e != "" else ""))
    if not c: fails.append(l)

FREEZE = "() => { for(let i=1;i<99999;i++) clearTimeout(i); clearInterval(timerId); }"
SEED = """() => {
  ['en','es'].forEach(l=>{
    const bank = l==='en' ? WORDS_EN : WORDS_ES;
    [1,2,3,4,5].forEach(t=>bank[t].forEach(w=>MASTERY.set(l+':'+w[0], MAX_STAGE)));
  });
}"""
MOCK = """() => {
  const v=[{name:'Google US English',lang:'en-US',localService:true}];
  window.speechSynthesis.getVoices=()=>v;
  window.speechSynthesis.speak=()=>{}; window.speechSynthesis.cancel=()=>{};
  window.SpeechSynthesisUtterance=function(t){this.text=t;this.voice=null;this.lang='';this.rate=1;};
  loadVoices();
}"""

with sync_playwright() as p:
    br = p.chromium.launch(); pg = br.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append("CONSOLE " + m.text) if m.type == "error" else None)

    def new_run():
        pg.goto(URL); pg.wait_for_timeout(350)
        pg.evaluate(MOCK); pg.evaluate(SEED)
        pg.click("#mode-normal"); pg.wait_for_timeout(500)
        pg.evaluate("S.floorIdx=0; startEncounter(S.floors[0][0]);"); pg.wait_for_timeout(1900)

    def ask(word, **kw):
        pg.evaluate(FREEZE)
        ex = "".join(f"S.{k}={v};" for k, v in kw.items())
        pg.evaluate(f"""() => {{
          setMastery({word!r}, MAX_STAGE);
          S.enc={{emoji:'🟢',hp:99999,dmg:20,tier:1,time:14000,gims:[],ko:'적',en:'F',es:'F'}};
          S.bossHP=99999; S.bossMax=99999; S.playerHP=100; S.playerMax=100;
          S.combo=0; S.choiceLocked=false; showScreen('battle'); {ex}
          S.queue=[{{w:{word!r},ko:'뜻',tag:'태그'}},{{w:'zebra',ko:'얼룩말',tag:'명사'}},
                   {{w:'melon',ko:'멜론',tag:'명사'}}]; nextWord();
          S.wordStart = performance.now() - S.timerBase;   // 속도 보너스를 0으로 고정
        }}""")
        pg.wait_for_timeout(140)

    def answer(word):
        pg.fill("#word-input", word); pg.keyboard.press("Enter"); pg.wait_for_timeout(450)

    print("\n=== 1. 전리품 누적 ===")
    new_run()
    check("전투 시작 시 0", pg.evaluate("S.pot") == 0 and pg.evaluate("S.potStreak") == 0)
    check("회수 버튼 비활성", pg.evaluate("document.getElementById('bank-btn').disabled"))
    ask("apple", pot=0, potStreak=0, potPeak=0)
    gains = []
    for w in ["apple", "water", "house"]:
        before = pg.evaluate("S.pot")
        ask(w, pot=f"{before}", potStreak=f"{len(gains)}")
        answer(w)
        gains.append(pg.evaluate("S.pot") - before)
    check("맞힐수록 가속 증가", gains[0] < gains[1] < gains[2], gains)
    check("연속 카운터 증가", pg.evaluate("S.potStreak") == 3, pg.evaluate("S.potStreak"))
    check("최대 전리품 기록", pg.evaluate("S.potPeak") == pg.evaluate("S.pot"))
    check("회수 버튼 활성", not pg.evaluate("document.getElementById('bank-btn').disabled"))
    check("UI 금액 일치", pg.evaluate("document.getElementById('pot-amt').textContent") == str(pg.evaluate("S.pot")))
    check("연속 표시", "연속" in pg.evaluate("document.getElementById('pot-streak').textContent"))

    print("\n=== 2. 위험 보너스 ===")
    ask("apple", pot=0)
    check("전리품 0이면 보너스 없음", pg.evaluate("riskBonus()") == 0)
    pg.evaluate("S.pot=40")
    b40 = pg.evaluate("riskBonus()")
    pg.evaluate("S.pot=200")
    check("전리품 클수록 보너스 증가", pg.evaluate("riskBonus()") > b40 > 0, f"40→{b40:.3f}")
    check("보너스 상한 30%", abs(pg.evaluate("riskBonus()") - 0.30) < 1e-9, pg.evaluate("riskBonus()"))

    ask("apple", pot=0, wrongTried="true")     # 크리티컬 차단
    answer("apple"); d_low = 99999 - pg.evaluate("S.bossHP")
    ask("apple", pot=200, wrongTried="true")
    answer("apple"); d_high = 99999 - pg.evaluate("S.bossHP")
    check("전리품 보유 시 데미지 상승", d_high > d_low, f"{d_low} → {d_high}")

    print("\n=== 3. 손실 — 오답 / 시간초과 / 건너뛰기 ===")
    ask("apple", pot=60, potStreak=5, potLost=0)
    pg.fill("#word-input", "zzz"); pg.keyboard.press("Enter"); pg.wait_for_timeout(400)
    check("오답 → 전액 소멸", pg.evaluate("S.pot") == 0 and pg.evaluate("S.potStreak") == 0)
    check("날린 금액 누적", pg.evaluate("S.potLost") == 60, pg.evaluate("S.potLost"))
    check("상실 문구 노출", "잃었습니다" in pg.evaluate("document.getElementById('pot-line').textContent"))
    check("격려 문구 포함", any(s in pg.evaluate("document.getElementById('pot-line').textContent")
                          for s in ["괜찮", "남습니다", "타이밍", "나쁘지"]),
          pg.evaluate("document.getElementById('pot-line').textContent"))

    ask("apple", pot=45, potStreak=4, potLost=0)
    pg.evaluate("clearInterval(timerId); onTimeout();"); pg.wait_for_timeout(400)
    check("시간 초과 → 전액 소멸", pg.evaluate("S.pot") == 0 and pg.evaluate("S.potLost") == 45)

    ask("apple", pot=50, potStreak=4, potLost=0, skips=3)
    pg.keyboard.press("Tab"); pg.wait_for_timeout(400)
    check("건너뛰기 → 절반만 손실", pg.evaluate("S.pot") == 25 and pg.evaluate("S.potLost") == 25,
          f"남은={pg.evaluate('S.pot')} 잃은={pg.evaluate('S.potLost')}")
    check("건너뛰기도 연속은 초기화", pg.evaluate("S.potStreak") == 0)

    # 일반 모드에는 소개 단계가 없다 — 처음 보는 단어도 힌트 타이핑이라 오답이면 잃는다
    ask("apple", pot=30, potStreak=3, potLost=0)
    pg.evaluate("setMastery('apple',0); S.queue=[{w:'apple',ko:'사과',tag:'명사'}]; nextWord();")
    pg.wait_for_timeout(200)
    check("일반 모드: 처음 보는 단어도 2단계", pg.evaluate("S.wstage") == 2 and pg.evaluate("S.wstageRaw") == 0)
    pg.fill("#word-input", "zzz"); pg.keyboard.press("Enter"); pg.wait_for_timeout(400)
    check("처음 보는 단어도 오답이면 소멸", pg.evaluate("S.pot") == 0 and pg.evaluate("S.potLost") == 30,
          f"남은={pg.evaluate('S.pot')} 잃은={pg.evaluate('S.potLost')}")

    print("\n=== 4. 회수 ===")
    ask("apple", pot=80, potStreak=6, gold=100, potBanked=0)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    check("Esc 로 회수", pg.evaluate("S.gold") == 180 and pg.evaluate("S.pot") == 0)
    check("회수 누적 기록", pg.evaluate("S.potBanked") == 80)
    check("회수 시 연속 초기화", pg.evaluate("S.potStreak") == 0)
    check("회수 후 버튼 비활성", pg.evaluate("document.getElementById('bank-btn').disabled"))
    ask("apple", pot=40, gold=0)
    pg.click("#bank-btn"); pg.wait_for_timeout(250)
    check("버튼 클릭으로도 회수", pg.evaluate("S.gold") == 40)
    g0 = pg.evaluate("S.gold")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    check("전리품 0이면 회수 무효", pg.evaluate("S.gold") == g0)

    print("\n=== 5. 긴장 단계 연출 ===")
    for amt, cls in [(10, ""), (40, "hot"), (90, "blaze")]:
        pg.evaluate(f"S.pot={amt}; updatePotUI();"); pg.wait_for_timeout(80)
        c = pg.evaluate("document.getElementById('pot-bar').className")
        ok = (cls == "" and "hot" not in c and "blaze" not in c) or (cls and cls in c)
        check(f"전리품 {amt} → {cls or '기본'} 연출", ok, c)
    pg.evaluate("S.pot=90; updatePotUI();")
    check("고액일 때 압박 문구", "뼈아픕니다" in pg.evaluate("document.getElementById('pot-line').textContent"))

    print("\n=== 6. 전투 종료 시 자동 확정 ===")
    ask("apple", pot=55, gold=0, potBanked=0)
    pg.evaluate("S.enc.gold=[20,20]; S.enc.kind='battle'; S.bossHP=1;")
    answer("apple"); pg.wait_for_timeout(1200)
    check("전리품 자동 확정", pg.evaluate("S.potBanked") >= 55 and pg.evaluate("S.gold") >= 55,
          f"gold={pg.evaluate('S.gold')} banked={pg.evaluate('S.potBanked')}")
    check("보상 패널 표시", pg.evaluate("document.getElementById('panel').classList.contains('show')"))

    print("\n=== 7. 더블 오어 나씽 ===")
    new_run()
    pg.evaluate(FREEZE)
    pg.evaluate("S.gold=0; S.pendingGold=50; S.gambleMul=1; S.gambleRound=0; showGoldSettle();")
    pg.wait_for_timeout(300)
    check("정산 화면", "50G" in pg.evaluate("document.getElementById('pn-sub').textContent"))
    check("선택지 2개(챙기기/걸기)", pg.evaluate("document.querySelectorAll('#pn-opts .opt').length") == 2)

    # 안전하게 챙기기
    pg.evaluate("document.querySelectorAll('#pn-opts .opt')[0].click()"); pg.wait_for_timeout(300)
    check("챙기면 골드 확정", pg.evaluate("S.gold") == 50)
    check("맵으로 복귀", pg.evaluate("document.getElementById('map').classList.contains('active')"))

    # 도박 승리
    pg.evaluate("S.gold=0; S.pendingGold=50; S.gambleMul=1; S.gambleRound=0; S.gambleWins=0; startGamble();")
    pg.wait_for_timeout(300)
    check("도박 화면 표시", pg.evaluate("document.getElementById('gamble-input') !== null"))
    check("판돈 2배 표기", "100" in pg.evaluate("document.getElementById('pn-title').textContent"))
    gw = pg.evaluate("S.gambleWord.w")
    check("이미 본 단어에서 출제", pg.evaluate("masteryOf(S.gambleWord.w)") >= 1, gw)
    pg.fill("#gamble-input", gw); pg.keyboard.press("Enter"); pg.wait_for_timeout(400)
    check("정답 → 승리 판정", pg.evaluate("S.gambleWins") == 1 and pg.evaluate("S.gambleMul") == 2)
    check("승리 문구", "배짱" in pg.evaluate("document.getElementById('pn-title').textContent"))
    pg.evaluate("showGoldSettle()"); pg.wait_for_timeout(250)
    check("판돈 100으로 상승", "100G" in pg.evaluate("document.getElementById('pn-sub').textContent"))
    pg.evaluate("document.querySelectorAll('#pn-opts .opt')[0].click()"); pg.wait_for_timeout(250)
    check("2배 확정 수령", pg.evaluate("S.gold") == 100, pg.evaluate("S.gold"))

    # 도박 패배
    pg.evaluate("S.gold=0; S.pendingGold=50; S.gambleMul=1; S.gambleRound=0; S.gambleLosses=0; S.potLost=0; startGamble();")
    pg.wait_for_timeout(300)
    pg.fill("#gamble-input", "zzzzz"); pg.keyboard.press("Enter"); pg.wait_for_timeout(400)
    check("오답 → 패배 판정", pg.evaluate("S.gambleLosses") == 1)
    check("골드 획득 없음", pg.evaluate("S.gold") == 0)
    check("날린 금액 집계", pg.evaluate("S.potLost") == 50)
    check("정답 공개", pg.evaluate("S.gambleWord.w") in pg.evaluate("document.getElementById('pn-sub').textContent"))
    check("격려 문구", "기억에 남았을" in pg.evaluate("document.getElementById('pn-sub').textContent"))
    check("오답노트 기록", pg.evaluate("S.missed.has(S.gambleWord.w)"))
    pg.evaluate("document.querySelector('#pn-foot .ov-btn').click()"); pg.wait_for_timeout(300)
    check("패배 후 맵 복귀", pg.evaluate("document.getElementById('map').classList.contains('active')"))

    # 시간 초과 = 패배
    pg.evaluate("S.gold=0; S.pendingGold=30; S.gambleMul=1; S.gambleRound=0; S.gambleLosses=0; startGamble();")
    pg.wait_for_timeout(200)
    pg.evaluate("clearInterval(gambleTimer); resolveGamble('');"); pg.wait_for_timeout(300)
    check("시간 초과 → 패배", pg.evaluate("S.gambleLosses") == 1 and pg.evaluate("S.gold") == 0)

    # 1회 제한
    check("상한 상수 = 1", pg.evaluate("MAX_GAMBLE_ROUNDS") == 1)
    pg.evaluate("S.pendingGold=50; S.gambleMul=1; S.gambleRound=0; showGoldSettle();"); pg.wait_for_timeout(250)
    check("첫 정산엔 도박 가능", pg.evaluate("document.querySelectorAll('#pn-opts .opt').length") == 2)
    pg.evaluate("S.pendingGold=50; S.gambleMul=2; S.gambleRound=1; showGoldSettle();"); pg.wait_for_timeout(250)
    check("1회 후 도박 불가", pg.evaluate("document.querySelectorAll('#pn-opts .opt').length") == 1)
    check("최대 2배까지만", "100G" in pg.evaluate("document.getElementById('pn-sub').textContent"))
    check("종료 안내 문구", "여기까지" in pg.evaluate("document.getElementById('pn-foot').textContent"))
    # 승리 직후에도 추가 배팅 버튼이 없어야 한다
    pg.evaluate("S.gold=0; S.pendingGold=50; S.gambleMul=1; S.gambleRound=0; startGamble();")
    pg.wait_for_timeout(250)
    gw2 = pg.evaluate("S.gambleWord.w")
    pg.fill("#gamble-input", gw2); pg.keyboard.press("Enter"); pg.wait_for_timeout(400)
    pg.evaluate("document.querySelector('#pn-foot .ov-btn').click()"); pg.wait_for_timeout(300)
    check("승리 후 재배팅 불가", pg.evaluate("document.querySelectorAll('#pn-opts .opt').length") == 1)
    pg.evaluate("document.querySelectorAll('#pn-opts .opt')[0].click()"); pg.wait_for_timeout(250)
    check("최종 수령 = 원금 2배", pg.evaluate("S.gold") == 100, pg.evaluate("S.gold"))
    pg.screenshot(path="psych_settle.png")

    print("\n=== 8. 유물 → 정산 순서 ===")
    new_run()
    pg.evaluate(FREEZE)
    pg.evaluate("S.relics=[]; S.enc.kind='elite'; S.enc.gold=[40,40]; S.enc.final=false; S.pot=0; encounterCleared();")
    pg.wait_for_timeout(300)
    check("먼저 유물 선택", "유물" in pg.evaluate("document.getElementById('pn-sub').textContent"))
    pg.click("#pn-opts .opt"); pg.wait_for_timeout(300)
    check("유물 후 골드 정산", "40G" in pg.evaluate("document.getElementById('pn-sub').textContent"))
    check("유물 획득됨", pg.evaluate("S.relics.length") == 1)

    print("\n=== 9. 결과 화면 통계 ===")
    pg.evaluate("S.potPeak=88; S.potLost=140; S.gambleWins=2; S.gambleLosses=1; endGame(false);")
    pg.wait_for_timeout(300)
    check("최대 전리품", pg.evaluate("document.getElementById('st-peak').textContent") == "88")
    check("날린 골드", pg.evaluate("document.getElementById('st-lost').textContent") == "140")
    check("도박 전적", pg.evaluate("document.getElementById('st-gamble').textContent") == "2승 1패")
    pg.screenshot(path="psych_result.png")

    print("\n=== 10. 초보자 모드: 도박 요소 제거 ===")
    pg.goto(URL); pg.wait_for_timeout(350); pg.evaluate(MOCK); pg.evaluate(SEED)
    pg.wait_for_timeout(120)
    pg.click("#mode-beginner"); pg.wait_for_timeout(500)
    pg.evaluate("S.floorIdx=0; startEncounter(S.floors[0][0]);"); pg.wait_for_timeout(1900)
    check("라벨 = 획득 골드", pg.evaluate("document.getElementById('pot-label').textContent") == "이번 전투 획득 골드")
    check("회수 버튼 숨김", pg.evaluate("document.getElementById('bank-btn').style.display") == "none")
    ask("apple", gold=0, pot=0, potBanked=0)
    pg.fill("#word-input", "apple"); pg.keyboard.press("Enter"); pg.wait_for_timeout(500)
    gN = pg.evaluate("S.gold")
    check("정답 골드 즉시 확정", gN > 0 and pg.evaluate("S.potBanked") == gN, gN)
    ask("apple", pot=40, potLost=0, gold=gN)
    pg.fill("#word-input", "zzz"); pg.keyboard.press("Enter"); pg.wait_for_timeout(400)
    check("오답에도 손실 없음", pg.evaluate("S.pot") == 40 and pg.evaluate("S.potLost") == 0)
    ask("apple", pot=40, potLost=0, skips=3)
    pg.keyboard.press("Tab"); pg.wait_for_timeout(400)
    check("건너뛰기에도 손실 없음", pg.evaluate("S.potLost") == 0)
    ask("apple", pot=200)
    check("위험 보너스 0", pg.evaluate("riskBonus()") == 0)
    check("긴장 연출 없음", "blaze" not in pg.evaluate("document.getElementById('pot-bar').className"))
    pg.evaluate(FREEZE)
    pg.evaluate("S.gold=0; S.pendingGold=50; S.gambleMul=1; S.gambleRound=0; showGoldSettle();")
    pg.wait_for_timeout(300)
    check("도박 선택지 없음", pg.evaluate("document.querySelectorAll('#pn-opts .opt').length") == 1)
    br.close()

print("\n" + "=" * 46)
print("JS 에러:", errors if errors else "없음")
print("실패:", fails if fails else "없음  ✅ 전체 통과")
