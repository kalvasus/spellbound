"""공통 시스템 회귀 테스트 — 단어 데이터 / 언어 / 난이도 / 전투 판정 / 기믹 /
   레벨·스킬 / 건너뛰기 / 스페인어 / 승패 흐름 (로그라이크 단일 모드 기준)"""
from playwright.sync_api import sync_playwright

import os, pathlib
URL = os.environ.get("GAME_URL") or (
    pathlib.Path(__file__).resolve().parent.parent / "dist" / "index.html").as_uri()
errors, fails = [], []

def check(l, c, e=""):
    print(("  OK   " if c else "  FAIL ") + l + ("  " + str(e) if e != "" else ""))
    if not c: fails.append(l)

FREEZE = "() => { for (let i=1;i<99999;i++) clearTimeout(i); clearInterval(timerId); }"
SEED = """() => {
  ['en','es'].forEach(l=>{
    const bank = l==='en' ? WORDS_EN : WORDS_ES;
    [1,2,3,4,5].forEach(t=>bank[t].forEach(w=>MASTERY.set(l+':'+w[0], MAX_STAGE)));
  });
}"""   # 전투 역학 테스트용 — 모든 단어를 완전 회상 단계로 올려둔다

MOCK_VOICES = """
(list) => {
  const voices = list.map(v => ({name:v[0], lang:v[1], localService:true}));
  window.speechSynthesis.getVoices = () => voices;
  window.__spoken = [];
  window.speechSynthesis.speak = (u) => window.__spoken.push({t:u.text, v:u.voice&&u.voice.name, l:u.lang});
  window.speechSynthesis.cancel = () => {};
  window.SpeechSynthesisUtterance = function(t){ this.text=t; this.voice=null; this.lang=""; this.rate=1; };
}
"""


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
    pg.goto(URL); pg.wait_for_timeout(400); pg.evaluate(SEED)

    print("\n=== 1. 단어 데이터 ===")
    for name in ["WORDS_EN", "WORDS_ES"]:
        counts = pg.evaluate(f"[1,2,3,4,5].map(t=>{name}[t].length)")
        dups = pg.evaluate(f"(()=>{{const a=[].concat(...[1,2,3,4,5].map(t=>{name}[t])).map(w=>w[0]);"
                           f"return [...new Set(a.filter((w,i)=>a.indexOf(w)!==i))];}})()")
        bad = pg.evaluate(f"[].concat(...[1,2,3,4,5].map(t=>{name}[t])).filter(w=>w.length!==3||!w[0]||!w[1]||!w[2]).length")
        check(f"{name} 총 500단어", sum(counts) == 500, f"{counts} = {sum(counts)}")
        check(f"{name} 티어당 100단어", all(c == 100 for c in counts), f"{counts}")
        check(f"{name} 중복 없음", dups == [], dups)
        check(f"{name} 형식 정상", bad == 0)

    print("\n=== 2. 보스 러시 흔적 제거 ===")
    check("BOSSES 전역 없음",   pg.evaluate("typeof BOSSES === 'undefined'"))
    check("MODE 전역 없음",     pg.evaluate("typeof MODE === 'undefined'"))
    check("loadStage 없음",     pg.evaluate("typeof loadStage === 'undefined'"))
    check("pickMode 없음",      pg.evaluate("typeof pickMode === 'undefined'"))
    check("모드 선택 UI 없음",   pg.evaluate("document.querySelectorAll('.mode-card').length") == 0)
    check("startRun 진입점 존재", pg.evaluate("typeof startRun === 'function'"))

    print("\n=== 3. 언어 선택 ===")
    pg.evaluate(MOCK_VOICES, [["Google US English","en-US"],["Google español","es-ES"],["Mónica","es-ES"]])
    pg.evaluate("loadVoices()"); pg.wait_for_timeout(150)
    check("영어 기본 선택", pg.evaluate("LANG") == "en")
    check("영어 음성만 필터", pg.evaluate("VOICES.map(v=>v.lang)") == ["en-US"])
    check("영어는 강세 버튼 없음", pg.evaluate("LANGS.en.accents.length") == 0)
    set_lang("es")
    check("스페인어 전환", pg.evaluate("LANG") == "es")
    check("스페인어 음성만 필터", pg.evaluate("VOICES.map(v=>v.lang)") == ["es-ES","es-ES"])
    check("Google 음성 우선", pg.evaluate("curVoice.name") == "Google español")
    check("es 안내문 노출", pg.evaluate("document.getElementById('howto-es').style.display") != "none")
    set_lang("en")
    check("영어 복귀", pg.evaluate("LANG") == "en" and pg.evaluate("curVoice.name") == "Google US English")
    check("es 안내문 숨김", pg.evaluate("document.getElementById('howto-es').style.display") == "none")

    print("\n=== 4. 난이도 ===")
    for d, exp_skip in [("easy",5),("hard",2),("normal",3)]:
        set_diff(d)
        check(f"{d} 선택 + 건너뛰기 {exp_skip}회", pg.evaluate("DIFFI") == d and pg.evaluate(f"DIFF['{d}'].skips") == exp_skip)
    check("지옥은 시간 단축", pg.evaluate("DIFF.hard.timeMul") < 1 < pg.evaluate("DIFF.easy.timeMul"))

    def new_run():
        pg.goto(URL); pg.wait_for_timeout(350)
        pg.evaluate(MOCK_VOICES, [["Google US English","en-US"],["Google español","es-ES"]])
        pg.evaluate("loadVoices()"); pg.evaluate(SEED)
        pg.click("#mode-normal"); pg.wait_for_timeout(500)

    def setfoe(word, gims="[]", **kw):
        """전투 화면에서 지정한 단어 하나를 출제한다"""
        pg.evaluate(FREEZE)
        ex = "".join(f"S.{k}={v};" for k, v in kw.items())
        pg.evaluate(f"""() => {{
          S.enc={{emoji:'🟢',hp:9999,dmg:20,tier:1,time:14000,gims:{gims},ko:'테스트',en:'Test',es:'Test'}};
          S.bossHP=9999; S.bossMax=9999; S.playerHP=100; S.playerMax=100;
          S.combo=0; S.backspaced=false; S.wrongTried=false; S.extraHint=0; S.powerUp=false;
          S.pot=0; S.potStreak=0;   // 위험 보너스를 배제하고 순수 전투 수치를 잰다
          {ex}
          showScreen('battle'); setMastery({word!r}, MAX_STAGE);
          S.queue=[{{w:{word!r},ko:'뜻',tag:'태그'}},{{w:'zebra',ko:'얼룩말',tag:'명사'}},
                   {{w:'melon',ko:'멜론',tag:'명사'}}]; nextWord();
          S.wordStart = performance.now() - S.timerBase;   // 속도 보너스를 0으로 고정
        }}""")
        pg.wait_for_timeout(130)

    print("\n=== 5. 전투 판정 ===")
    new_run()
    setfoe("apple")
    pg.fill("#word-input", "aple"); pg.keyboard.press("Enter"); pg.wait_for_timeout(300)
    check("오답 거부", pg.evaluate("S.bossHP") == 9999 and pg.evaluate("S.playerHP") < 100)
    check("오답 시 콤보 초기화", pg.evaluate("S.combo") == 0)
    check("오답노트 기록(틀림)", pg.evaluate("S.missed.get('apple') && S.missed.get('apple').why !== 'skip'"))

    setfoe("apple")
    pg.fill("#word-input", "APPLE"); pg.keyboard.press("Enter"); pg.wait_for_timeout(400)
    check("대소문자 무시 정답", pg.evaluate("S.bossHP") < 9999)


    print("\n=== 5-2. 속도 비례 데미지 ===")
    def at_speed(remain, clean=True, relics=None, word="apple"):
        """남은 시간 비율을 강제로 만들고 데미지를 측정한다"""
        pg.evaluate(FREEZE)
        pg.evaluate("""(a) => {
          setMastery(a.w, MAX_STAGE);
          S.enc={emoji:'x',hp:99999,dmg:10,tier:1,time:14000,gims:[],ko:'x',en:'x',es:'x'};
          S.bossHP=99999; S.bossMax=99999; S.playerHP=100; S.playerMax=100;
          S.combo=0; S.bonusAtk=0; S.pot=0; S.potStreak=0; S.powerUp=false;
          S.relics=a.relics; S.wrongTried=false; S.extraHint=0; S.backspaced=false;
          showScreen('battle');
          S.queue=[{w:a.w,ko:'뜻',tag:'태그'}]; nextWord();
          S.wordStart = performance.now() - S.timerBase*(1-a.r);
          if(!a.clean) S.backspaced = true;
        }""", {"w": word, "r": remain, "clean": clean, "relics": relics or []})
        pg.wait_for_timeout(70)
        pg.fill("#word-input", word); pg.keyboard.press("Enter"); pg.wait_for_timeout(320)
        return 99999 - pg.evaluate("S.bossHP")

    curve = [(r, at_speed(r)) for r in [1.0, 0.75, 0.5, 0.25, 0.0]]
    dmgs = [d for _, d in curve]
    check("남을수록 데미지가 계속 증가", all(dmgs[i] > dmgs[i+1] for i in range(len(dmgs)-1)),
          " → ".join(f"{int(r*100)}%:{d}" for r, d in curve))
    check("계단이 아니라 연속적", len(set(dmgs)) == len(dmgs), dmgs)
    check("최대 2배", dmgs[0] == dmgs[-1] * 2, f"{dmgs[-1]} → {dmgs[0]}")
    mid = at_speed(0.5)
    check("중간 지점은 1.5배", mid == round(dmgs[-1] * 1.5), f"{mid} (기대 {round(dmgs[-1]*1.5)})")

    check("고쳐 치면 보너스 절반", at_speed(1.0, clean=False) == round(dmgs[-1] * 1.5),
          f"한 번에 {dmgs[0]} vs 수정 {at_speed(1.0, clean=False)}")
    check("⚡ 이중 타격은 보너스 강화", at_speed(1.0, relics=["bolt"]) > dmgs[0])
    check("🔍 돋보기는 보너스 상실", at_speed(1.0, relics=["glass"]) == dmgs[-1])

    # 시간 연장 스킬로 보너스를 부풀릴 수 없어야 한다
    pg.evaluate(FREEZE)
    pg.evaluate("""() => {
      setMastery('apple', MAX_STAGE);
      S.enc={emoji:'x',hp:99999,dmg:10,tier:1,time:14000,gims:[],ko:'x'};
      S.bossHP=99999; S.bossMax=99999; S.combo=0; S.bonusAtk=0; S.pot=0; S.relics=[];
      S.charges={hint:0,time:3,heal:0,power:0}; showScreen('battle');
      S.queue=[{w:'apple',ko:'뜻',tag:'태그'}]; nextWord();
      S.wordStart = performance.now() - S.timerBase*0.9;   // 남은 10%
    }""")
    pg.wait_for_timeout(70)
    base_before = pg.evaluate("S.timerBase")
    pg.keyboard.press("2")          # 시간 연장 스킬
    pg.wait_for_timeout(150)
    check("시간 연장은 속도 기준을 바꾸지 않음",
          pg.evaluate("S.timerBase") == base_before and pg.evaluate("S.timerTotal") > base_before,
          f"base={pg.evaluate('S.timerBase')} total={pg.evaluate('S.timerTotal')}")
    check("연장해도 속도 보너스는 낮게 유지", pg.evaluate("speedRemain()") < 0.2,
          round(pg.evaluate("speedRemain()"), 3))

    # 판정 등급
    check("판정 등급 경계", pg.evaluate("[speedTier(0.75).label, speedTier(0.5).label, "
                                   "speedTier(0.25).label, speedTier(0.1)]")
          == ["PERFECT", "GREAT", "GOOD", None])
    at_speed(1.0)
    check("PERFECT 카운트 집계", pg.evaluate("S.crits") > 0, pg.evaluate("S.crits"))
    check("평균 속도 보너스 기록", pg.evaluate("S.speedN") > 0 and pg.evaluate("S.speedBest") > 0.9,
          f"n={pg.evaluate('S.speedN')} best={round(pg.evaluate('S.speedBest'),2)}")

    # 실시간 표시
    pg.evaluate(FREEZE)
    pg.evaluate("S.queue=[{w:'apple',ko:'뜻',tag:'t'}]; nextWord();"); pg.wait_for_timeout(120)
    t_full = pg.evaluate("document.getElementById('speed-tag').textContent")
    pg.evaluate("S.wordStart = performance.now() - S.timerBase*0.9; updateSpeedTag();")
    pg.wait_for_timeout(80)
    t_low = pg.evaluate("document.getElementById('speed-tag').textContent")
    check("실시간 보너스 표시가 감소", int(t_full.strip("+%")) > int(t_low.strip("+%")),
          f"{t_full} → {t_low}")
    check("최대치일 때 강조 표시", pg.evaluate(
        "(()=>{S.wordStart=performance.now(); updateSpeedTag(); return document.getElementById('speed-tag').className;})()") == "max")

    print("\n=== 6. 적 기믹 ===")
    setfoe("apple", gims="['shield']", combo=0)
    pg.fill("#word-input","apple"); pg.keyboard.press("Enter"); pg.wait_for_timeout(400)
    low = 9999 - pg.evaluate("S.bossHP")
    setfoe("apple", gims="['shield']", combo=5)
    pg.fill("#word-input","apple"); pg.keyboard.press("Enter"); pg.wait_for_timeout(400)
    high = 9999 - pg.evaluate("S.bossHP")
    check("🛡️ 방패: 저콤보 데미지 감소", low < high, f"콤보0={low} < 콤보5={high}")

    setfoe("apple", gims="['curse']")
    h_curse = pg.evaluate("document.getElementById('q-hint').textContent").strip()
    setfoe("apple")
    h_norm = pg.evaluate("document.getElementById('q-hint').textContent").strip()
    check("🔮 저주: 첫 글자 숨김", not h_curse.startswith("a") and h_norm.startswith("a"),
          f"저주='{h_curse[:12]}' 기본='{h_norm[:12]}'")

    setfoe("apple", gims="['haste']", hasteStacks=0)
    t0 = pg.evaluate("bossTime()"); pg.evaluate("S.hasteStacks=6"); t1 = pg.evaluate("bossTime()")
    check("⏩ 가속: 시간 단축", t1 < t0, f"{round(t0)}ms → {round(t1)}ms")

    setfoe("apple", gims="['drain']")
    pg.evaluate("S.bossHP=500")
    pg.fill("#word-input","zzz"); pg.keyboard.press("Enter"); pg.wait_for_timeout(300)
    check("🩸 흡혈: 오답 시 회복", pg.evaluate("S.bossHP") > 500, pg.evaluate("S.bossHP"))

    print("\n=== 7. 레벨 · 강화 ===")
    pg.evaluate(FREEZE)
    pg.evaluate("S.relics=[]; S.level=1; S.exp=0; pendingLevelUps=0; gainExp(100)"); pg.wait_for_timeout(900)
    check("EXP 100 → 레벨업", pg.evaluate("S.level") == 2)
    check("레벨업 창 표시", pg.evaluate("document.getElementById('levelup').classList.contains('show')"))
    check("선택지 3개", pg.evaluate("document.querySelectorAll('#lu-opts .lu-opt').length") == 3)
    hp0 = pg.evaluate("S.playerMax"); pg.evaluate("chooseLevelUp('maxhp')"); pg.wait_for_timeout(200)
    check("최대체력 +20", pg.evaluate("S.playerMax") == hp0 + 20)
    check("레벨업 창 닫힘", not pg.evaluate("document.getElementById('levelup').classList.contains('show')"))
    a0 = pg.evaluate("S.bonusAtk"); pg.evaluate("chooseLevelUp('attack')")
    check("공격력 +4", pg.evaluate("S.bonusAtk") == a0 + 4)
    t0 = pg.evaluate("S.bonusTime"); pg.evaluate("chooseLevelUp('clock')")
    check("제한시간 +1.5초", pg.evaluate("S.bonusTime") == t0 + 1500)
    h0 = pg.evaluate("S.charges.hint"); pg.evaluate("chooseLevelUp('hint')")
    check("힌트 스킬 +2", pg.evaluate("S.charges.hint") == h0 + 2)

    print("\n=== 8. 스킬 4종 ===")
    setfoe("apple")
    pg.evaluate("S.charges={hint:3,time:3,heal:3,power:3}; buildSkillRow();"); pg.wait_for_timeout(100)
    check("스킬 버튼 4개", pg.evaluate("document.querySelectorAll('#skill-row .skill').length") == 4)
    hb = pg.evaluate("document.getElementById('q-hint').textContent")
    pg.keyboard.press("1"); pg.wait_for_timeout(200)
    check("[1] 힌트 추가 공개", pg.evaluate("S.extraHint") == 1 and
          pg.evaluate("document.getElementById('q-hint').textContent") != hb)
    check("힌트 횟수 차감", pg.evaluate("S.charges.hint") == 2)
    tb = pg.evaluate("S.timerTotal"); pg.keyboard.press("2"); pg.wait_for_timeout(150)
    check("[2] 시간연장 +5초", pg.evaluate("S.timerTotal") == tb + 5000)
    pg.evaluate("S.playerHP=40"); pg.keyboard.press("3"); pg.wait_for_timeout(150)
    check("[3] 회복 +30", pg.evaluate("S.playerHP") == 70)
    pg.keyboard.press("4"); pg.wait_for_timeout(150)
    check("[4] 강타 버프", pg.evaluate("S.powerUp") is True)
    setfoe("apple", powerUp="true")
    pg.fill("#word-input","apple"); pg.keyboard.press("Enter"); pg.wait_for_timeout(400)
    pdmg = 9999 - pg.evaluate("S.bossHP")
    setfoe("apple")
    pg.fill("#word-input","apple"); pg.keyboard.press("Enter"); pg.wait_for_timeout(400)
    ndmg = 9999 - pg.evaluate("S.bossHP")
    check("강타 데미지 3배", pdmg == ndmg * 3, f"강타={pdmg} vs 일반={ndmg}")
    pg.evaluate("S.charges.hint=0; buildSkillRow();"); pg.wait_for_timeout(100)
    check("횟수 0이면 비활성", pg.evaluate("document.querySelectorAll('#skill-row .skill.off').length") >= 1)

    print("\n=== 9. 건너뛰기 ===")
    setfoe("treasure", skips=3, skipsMax=3, skipped=0, exp=0, combo=4)
    hp0 = pg.evaluate("S.playerHP"); e0 = pg.evaluate("S.exp")
    pg.evaluate("window.__spoken=[]")
    pg.keyboard.press("Tab"); pg.wait_for_timeout(300)
    check("Tab 으로 건너뛰기", pg.evaluate("S.skipped") == 1 and pg.evaluate("S.skips") == 2)
    check("체력·보스 데미지 없음", pg.evaluate("S.playerHP") == hp0 and pg.evaluate("S.bossHP") == 9999)
    check("EXP 없음 / 콤보 초기화", pg.evaluate("S.exp") == e0 and pg.evaluate("S.combo") == 0)
    check("정답 공개", "treasure" in pg.evaluate("document.getElementById('q-hint').textContent"))
    check("발음 재생", pg.evaluate("window.__spoken.slice(-1)[0].t") == "treasure")
    check("오답노트에 skip 표시", pg.evaluate("S.missed.get('treasure').why") == "skip")
    check("큐에 재삽입", pg.evaluate("S.queue.some(q=>q.w==='treasure')"))
    setfoe("water", skips=0)
    pg.keyboard.press("Tab"); pg.wait_for_timeout(250)
    check("소진 시 무시", pg.evaluate("S.word.w") == "water" and pg.evaluate("S.skips") == 0)
    check("소진 시 버튼 비활성", pg.evaluate("document.getElementById('skip-btn').disabled"))
    pg.evaluate("S.skips=2; S.floorIdx=1; startEncounter(S.floors[1][0]);"); pg.wait_for_timeout(1900)
    check("전투마다 재충전", pg.evaluate("S.skips") == pg.evaluate("S.skipsMax") == 3, pg.evaluate("S.skips"))

    print("\n=== 10. 스페인어 모드 ===")
    pg.goto(URL); pg.wait_for_timeout(350)
    pg.evaluate(MOCK_VOICES, [["Google español","es-ES"]])
    pg.evaluate("loadVoices()"); pg.evaluate(SEED)
    set_lang("es"); pg.wait_for_timeout(350)
    pg.click("#mode-normal"); pg.wait_for_timeout(500)
    pg.click(".floor.cur .node"); pg.wait_for_timeout(2000)
    check("스페인어 단어 출제", pg.evaluate("WORDS_ES[S.enc.tier].some(w=>w[0]===S.word.w)"), pg.evaluate("S.word.w"))
    check("강세 버튼 9개", pg.evaluate("document.querySelectorAll('#accent-row button').length") == 9)
    check("주인공 아이콘(스페인어)", pg.evaluate("!!document.querySelector('#player-emoji svg')") and
          pg.evaluate("LANGS.es.hero") == "heroEs")

    setfoe("canción")
    pg.fill("#word-input","cancion"); pg.keyboard.press("Enter"); pg.wait_for_timeout(400)
    d_loose = 9999 - pg.evaluate("S.bossHP")
    setfoe("canción", tildePerfect=0)
    pg.fill("#word-input","canción"); pg.keyboard.press("Enter"); pg.wait_for_timeout(400)
    d_exact = 9999 - pg.evaluate("S.bossHP")
    check("강세 생략도 정답", d_loose > 0)
    check("강세 정확 시 보너스", d_exact > d_loose and pg.evaluate("S.tildePerfect") == 1, f"{d_loose} → {d_exact}")
    setfoe("mañana")
    pg.fill("#word-input","manana"); pg.keyboard.press("Enter"); pg.wait_for_timeout(400)
    check("ñ 생략 정답", pg.evaluate("S.bossHP") < 9999)
    setfoe("médico")
    pg.click("#accent-row button:nth-child(6)")
    check("강세 버튼 입력", pg.evaluate("document.getElementById('word-input').value") == "ñ")
    check("스페인어 발음", pg.evaluate("window.__spoken.slice(-1)[0].l").startswith("es"))

    print("\n=== 11. 승패 흐름 ===")
    new_run()
    pg.evaluate(FREEZE)
    pg.evaluate("S.floorIdx=15; startEncounter(S.floors[15][0]);"); pg.wait_for_timeout(1900)
    pg.evaluate(FREEZE)
    pg.evaluate("S.bossHP=1; S.queue=[{w:'apple',ko:'사과',tag:'명사'}]; nextWord();"); pg.wait_for_timeout(150)
    pg.fill("#word-input","apple"); pg.keyboard.press("Enter"); pg.wait_for_timeout(1500)
    check("최종 보스 처치 → 승리", pg.evaluate("document.getElementById('result').classList.contains('active')")
          and pg.evaluate("document.getElementById('result-title').textContent") == "CLEAR")
    check("도달 층 16", pg.evaluate("document.getElementById('st-boss').textContent") == "16층")
    check("오답노트 렌더링", pg.evaluate("document.querySelectorAll('#review-list .item').length > 0 || "
                                     "document.querySelector('#review-list .empty') !== null"))
    pg.click("text=다시 도전"); pg.wait_for_timeout(300)
    check("다시 도전 → 시작화면", pg.evaluate("document.getElementById('start').classList.contains('active')"))

    new_run()
    pg.evaluate(FREEZE)
    pg.evaluate("S.floorIdx=3; startEncounter(S.floors[3][0]);"); pg.wait_for_timeout(1900)
    pg.evaluate("S.relics=[]; S.phoenixUsed=true; S.playerHP=5; hurtPlayer(99,true);"); pg.wait_for_timeout(1100)
    check("체력 0 → 패배", pg.evaluate("document.getElementById('result-title').textContent") == "DEFEAT"
          and "4층" in pg.evaluate("document.getElementById('st-boss').textContent"),
          pg.evaluate("document.getElementById('st-boss').textContent"))

    print("\n=== 12. 사운드 ===")
    pg.goto(URL); pg.wait_for_timeout(400)
    pg.evaluate("""() => {
      window.__made={osc:0,buf:0}; window.__scenes=[];
      const C = window.AudioContext || window.webkitAudioContext;
      const po=C.prototype.createOscillator, pb=C.prototype.createBufferSource;
      C.prototype.createOscillator=function(){window.__made.osc++;return po.apply(this,arguments)};
      C.prototype.createBufferSource=function(){window.__made.buf++;return pb.apply(this,arguments)};
      const o=AUDIO.scene.bind(AUDIO);
      AUDIO.scene=(n)=>{ if(window.__scenes[window.__scenes.length-1]!==n) window.__scenes.push(n); return o(n); };
    }""")
    check("AUDIO 모듈 노출", pg.evaluate("typeof AUDIO === 'object'"))
    check("토글 버튼 존재", pg.evaluate("!!document.getElementById('sfx-btn') && !!document.getElementById('bgm-btn')"))
    check("기본값 켜짐", pg.evaluate("AUDIO.isSfxOn() && AUDIO.isBgmOn()"))

    pg.click("#mode-normal"); pg.wait_for_timeout(1800)
    check("맵 BGM 시작", pg.evaluate("window.__scenes")[-1] == "map", pg.evaluate("window.__scenes"))
    check("BGM 음원이 주기적으로 생성", pg.evaluate("window.__made.osc") >= 3, pg.evaluate("window.__made"))

    pg.evaluate("S.floorIdx=0; S.floors[0][0].type='battle'; startEncounter(S.floors[0][0]);")
    pg.wait_for_timeout(2000)
    check("전투 BGM 전환", "battle" in pg.evaluate("window.__scenes"))
    pg.evaluate("S.playerHP=Math.round(S.playerMax*0.2); updateBars();"); pg.wait_for_timeout(200)
    check("위기 BGM 전환", pg.evaluate("window.__scenes")[-1] == "danger")
    pg.evaluate("S.playerHP=S.playerMax; updateBars();"); pg.wait_for_timeout(200)
    check("회복 시 복귀", pg.evaluate("window.__scenes")[-1] == "battle")

    pg.evaluate("window.__made={osc:0,buf:0}")
    pg.keyboard.type("ab"); pg.wait_for_timeout(250)
    check("타건음 발생", pg.evaluate("window.__made.buf") >= 2, pg.evaluate("window.__made"))

    # 음악을 먼저 끈 뒤 효과음만 측정한다 (하이햇은 음악이라 효과음 토글에 반응하지 않는다)
    pg.click("#bgm-btn"); pg.wait_for_timeout(300)
    check("음악 끄기", not pg.evaluate("AUDIO.isBgmOn()"))
    pg.evaluate("window.__made={osc:0,buf:0}")
    pg.click("#sfx-btn"); pg.wait_for_timeout(200)
    pg.keyboard.type("cd"); pg.wait_for_timeout(300)
    check("효과음 끄면 무음", not pg.evaluate("AUDIO.isSfxOn()") and pg.evaluate("window.__made.buf") == 0,
          pg.evaluate("window.__made"))
    pg.click("#sfx-btn"); pg.wait_for_timeout(150)
    pg.evaluate("window.__made={osc:0,buf:0}")
    pg.keyboard.type("ef"); pg.wait_for_timeout(300)
    check("효과음 복구", pg.evaluate("AUDIO.isSfxOn()") and pg.evaluate("window.__made.buf") >= 2,
          pg.evaluate("window.__made"))
    pg.click("#bgm-btn"); pg.wait_for_timeout(200)
    check("음악 복구", pg.evaluate("AUDIO.isBgmOn()"))

    print("\n=== 12-2. 타건음·단어 완성음 ===")
    # 음악을 꺼야 하이햇이 카운트에 섞이지 않는다
    if pg.evaluate("AUDIO.isBgmOn()"): pg.click("#bgm-btn"); pg.wait_for_timeout(300)
    pg.evaluate("window.__made={osc:0,buf:0}")
    pg.keyboard.type("a"); pg.wait_for_timeout(200)
    one = pg.evaluate("window.__made")
    check("타건음 3중 레이어(클릭+바디+하우징)", one["buf"] >= 1 and one["osc"] >= 2, one)

    pg.evaluate("window.__made={osc:0,buf:0}; AUDIO.sfx('wordDone', 0);"); pg.wait_for_timeout(200)
    slow = pg.evaluate("window.__made")
    check("단어 완성 롤 + 3연타", slow["buf"] >= 12 and slow["osc"] >= 15, slow)
    pg.evaluate("window.__made={osc:0,buf:0}; AUDIO.sfx('wordDone', 1);"); pg.wait_for_timeout(200)
    fast = pg.evaluate("window.__made")
    check("빠를수록 롤이 길어짐", fast["buf"] > slow["buf"] and fast["osc"] > slow["osc"], (slow, fast))
    check("구버전 correct 호출도 동작",
          pg.evaluate("(()=>{window.__made={osc:0,buf:0};AUDIO.sfx('correct',0);return window.__made.osc>0})()"))

    # 발음(TTS) 볼륨 — 웹오디오 버스를 타지 않으므로 utterance.volume 으로 확인한다
    pg.evaluate("""() => {
      window.__spoke = [];
      window.SpeechSynthesisUtterance = function(t){ this.text=t; this.voice=null; this.lang=""; this.rate=1; this.volume=1; };
      speechSynthesis.speak  = (u) => { window.__spoke.push({ v: u.volume, t: u.text }); };
      speechSynthesis.cancel = () => {};
      curVoice = { lang: 'en-US', name: 'test' };
    }""")
    check("발음 기본 볼륨 0.40", abs(pg.evaluate("AUDIO.getVol('speech')") - 0.40) < 1e-9,
          pg.evaluate("AUDIO.getVol('speech')"))
    pg.evaluate("AUDIO.setVol('master',1); AUDIO.setVol('speech',0.4); speak('hello');")
    pg.wait_for_timeout(150)
    check("utterance 볼륨에 반영", abs(pg.evaluate("window.__spoke.at(-1).v") - 0.40) < 1e-6,
          pg.evaluate("window.__spoke.at(-1)"))
    pg.evaluate("AUDIO.setVol('master',0.5); speak('hello');"); pg.wait_for_timeout(150)
    check("전체 볼륨도 발음에 곱해짐", abs(pg.evaluate("window.__spoke.at(-1).v") - 0.20) < 1e-6,
          pg.evaluate("window.__spoke.at(-1).v"))
    pg.evaluate("window.__spoke=[]; AUDIO.setVol('speech',0); speak('hello');"); pg.wait_for_timeout(150)
    check("발음 0이면 아예 말하지 않음", pg.evaluate("window.__spoke.length") == 0)
    pg.evaluate("AUDIO.setVol('master',0.85); AUDIO.setVol('speech',0.40);")
    if not pg.evaluate("AUDIO.isBgmOn()"): pg.click("#bgm-btn"); pg.wait_for_timeout(250)

    print("\n=== 13. 볼륨 조절 ===")
    check("패널 기본 닫힘", not pg.evaluate("document.getElementById('vol-panel').classList.contains('show')"))
    pg.click("#vol-btn"); pg.wait_for_timeout(250)
    check("패널 열림", pg.evaluate("document.getElementById('vol-panel').classList.contains('show')"))
    check("슬라이더 4개", pg.evaluate("document.querySelectorAll('#vol-panel input[type=range]').length") == 4)
    for kind, rid, val in [("master","mst-range",40), ("sfx","sfx-range",20),
                           ("bgm","bgm-range",60), ("speech","speech-range",25)]:
        pg.fill("#"+rid, str(val)); pg.dispatch_event("#"+rid, "input"); pg.wait_for_timeout(150)
        check(f"{kind} 볼륨 {val}% 반영", abs(pg.evaluate(f"AUDIO.getVol('{kind}')") - val/100) < 1e-9,
              pg.evaluate(f"AUDIO.getVol('{kind}')"))
    check("표시 숫자 갱신", pg.evaluate("document.getElementById('sfx-val').textContent") == "20")
    pg.fill("#bgm-range", "0"); pg.dispatch_event("#bgm-range", "input"); pg.wait_for_timeout(150)
    check("0이면 아이콘 꺼짐 표시", pg.evaluate("document.getElementById('bgm-btn').classList.contains('off')"))
    pg.fill("#sfx-range", "70"); pg.dispatch_event("#sfx-range", "input"); pg.wait_for_timeout(150)
    # BGM 루프는 볼륨 0 이어도 노드를 계속 만들므로, 효과음만 재려면 음악을 꺼둔다
    if pg.evaluate("AUDIO.isBgmOn()"): pg.click("#bgm-btn"); pg.wait_for_timeout(250)
    pg.click("#sfx-btn"); pg.wait_for_timeout(200)
    pg.evaluate("window.__made={osc:0,buf:0}")
    pg.keyboard.type("gh"); pg.wait_for_timeout(250)
    check("음소거 시 슬라이더값과 무관하게 무음", pg.evaluate("window.__made.buf") == 0, pg.evaluate("window.__made"))
    pg.click("#sfx-btn"); pg.wait_for_timeout(200)
    check("복구 시 이전 볼륨 유지", abs(pg.evaluate("AUDIO.getVol('sfx')") - 0.70) < 1e-9)
    pg.evaluate("window.__made={osc:0,buf:0}")
    pg.keyboard.type("ij"); pg.wait_for_timeout(250)
    check("복구 후 타건음 재개", pg.evaluate("window.__made.buf") >= 2, pg.evaluate("window.__made"))
    pg.click("#vol-btn"); pg.wait_for_timeout(300)
    check("닫으면 입력창 포커스 복귀",
          pg.evaluate("document.activeElement === document.getElementById('word-input')"))
    pg.click("#vol-btn"); pg.wait_for_timeout(200)
    pg.mouse.click(400, 520); pg.wait_for_timeout(300)
    check("바깥 클릭으로 닫힘", not pg.evaluate("document.getElementById('vol-panel').classList.contains('show')"))

    print("\n=== 14. 메인 화면 · 모드 진입 ===")
    pg.goto(URL); pg.wait_for_timeout(400); pg.evaluate(SEED)
    check("모드 버튼 3개", pg.evaluate("document.querySelectorAll('#start .mode-btn').length") == 3)
    check("커스텀은 비활성", pg.evaluate("document.getElementById('mode-custom').disabled"))
    check("메인에 설명 패널 없음", pg.evaluate("document.querySelectorAll('#start .panel').length") == 0)
    check("현재 설정 요약 표시",
          pg.evaluate("document.getElementById('cfg-now').textContent") == "영어 · 보통",
          pg.evaluate("document.getElementById('cfg-now').textContent"))

    pg.click("#link-guide"); pg.wait_for_timeout(250)
    check("설명서 화면 열림", pg.evaluate("document.getElementById('guide').classList.contains('active')"))
    check("설명서에 단축키표", pg.evaluate("document.querySelectorAll('#guide .krow').length") >= 5)
    pg.click("#guide-back"); pg.wait_for_timeout(200)
    check("메인 복귀", pg.evaluate("document.getElementById('start').classList.contains('active')"))

    pg.click("#link-settings"); pg.wait_for_timeout(250)
    check("설정 화면 열림", pg.evaluate("document.getElementById('settings').classList.contains('active')"))
    check("설정에 언어·난이도·음성",
          pg.evaluate("!!document.querySelector('#settings #lang-en') && "
                      "!!document.querySelector('#settings #diff-hard') && "
                      "!!document.querySelector('#settings #voice-select')"))
    pg.click("#diff-hard"); pg.wait_for_timeout(150)
    pg.click("#settings-back"); pg.wait_for_timeout(200)
    check("난이도 변경이 요약에 반영",
          pg.evaluate("document.getElementById('cfg-now').textContent") == "영어 · 지옥",
          pg.evaluate("document.getElementById('cfg-now').textContent"))

    pg.click("#mode-beginner"); pg.wait_for_timeout(500)
    check("비기너 버튼 → NOVICE", pg.evaluate("NOVICE") is True)
    check("비기너도 바로 맵으로", pg.evaluate("document.getElementById('map').classList.contains('active')"))
    pg.goto(URL); pg.wait_for_timeout(400); pg.evaluate(SEED)
    pg.click("#mode-normal"); pg.wait_for_timeout(500)
    check("노말 버튼 → NOVICE 해제", pg.evaluate("NOVICE") is False)

    print("\n=== 15. 라인 아트 아이콘 ===")
    missing = pg.evaluate("""() => {
      const keys = [].concat(
        ENEMIES.map(e=>e.emoji), ELITES.map(e=>e.emoji), RUN_BOSSES.map(e=>e.emoji),
        RELICS.map(r=>r.ic), EVENTS.map(e=>e.ic), LEVEL_OPTIONS.map(o=>o.ic),
        Object.values(SKILLS).map(s=>s.ic),
        ["shop","rest","event","treasure"], Object.values(LANGS).map(l=>l.hero));
      return [...new Set(keys)].filter(k => !ART[k]);
    }""")
    check("모든 아이콘 키가 ART에 정의됨", missing == [], missing)
    check("정적 아이콘도 SVG 로 채워짐",
          pg.evaluate("[...document.querySelectorAll('[data-ico]')].every(el=>el.querySelector('svg'))"))

    pg.evaluate("()=>{ S.floorIdx=0; startEncounter(S.floors[0][0]); }"); pg.wait_for_timeout(2200)
    for sel, name in [("#boss-emoji svg", "적"), ("#player-emoji svg", "주인공"),
                      ("#skill-row .skill svg", "스킬")]:
        check(f"{name} 아이콘 렌더", pg.evaluate(f"!!document.querySelector('{sel}')"))

    # 이모지가 화면 어디에도 남아있지 않아야 한다
    stray = pg.evaluate(r"""() => {
      const re = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}]/u;
      return [...document.querySelectorAll("body *")]
        .filter(el => [...el.childNodes].some(n => n.nodeType === 3 && re.test(n.nodeValue)))
        .map(el => el.tagName + ":" + el.textContent.trim().slice(0, 24));
    }""")
    check("UI 에 이모지 잔존 없음", stray == [], stray)
    br.close()

print("\n" + "=" * 46)
print("JS 에러:", errors if errors else "없음")
print("실패:", fails if fails else "없음  ✅ 전체 통과")
