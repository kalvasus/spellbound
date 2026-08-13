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
}"""   # 전투 역학 테스트용 — 모든 단어를 완전 회상 단계로 올려둔다

MOCK = """() => {
  const v=[{name:'Google US English',lang:'en-US',localService:true}];
  window.speechSynthesis.getVoices=()=>v; window.__s=[];
  window.speechSynthesis.speak=(u)=>window.__s.push(u.text);
  window.speechSynthesis.cancel=()=>{};
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

    print("\n=== 1. 맵 생성 규칙 ===")
    new_run()
    check("맵 화면 표시", pg.evaluate("document.getElementById('map').classList.contains('active')"))
    check("16층 생성", pg.evaluate("S.floors.length") == 16)

    # 여러 번 생성해 규칙이 항상 지켜지는지
    bad = pg.evaluate("""(() => {
      const errs = [];
      for(let run=0; run<60; run++){
        const f = generateMap();
        if(f.length !== 16) errs.push('층수 '+f.length);
        BOSS_FLOORS.forEach(bf=>{
          if(f[bf].length !== 1 || f[bf][0].type !== 'boss') errs.push('보스층 '+bf);
        });
        if(f[0].some(n=>n.type!=='battle')) errs.push('0층 전투아님');
        SHOP_FLOORS.forEach(sf=>{
          if(!f[sf].some(n=>n.type==='shop')) errs.push('상점없음 '+sf);
        });
        BOSS_FLOORS.forEach(bf=>{
          if(bf>0 && !f[bf-1].some(n=>n.type==='rest')) errs.push('보스전 휴식없음 '+bf);
        });
        f.forEach((row,i)=>{
          if(!BOSS_FLOORS.includes(i) && (row.length<2 || row.length>3)) errs.push('노드수 '+i+'='+row.length);
          if(i<3 && row.some(n=>n.type==='elite')) errs.push('초반 엘리트 '+i);
          row.forEach(n=>{ if(!n.type || !n.emoji) errs.push('불완전 노드'); });
        });
      }
      return [...new Set(errs)];
    })()""")
    check("60회 생성 규칙 위반 없음", bad == [], bad)

    types = pg.evaluate("""(() => {
      const c = {};
      for(let r=0;r<40;r++) generateMap().forEach(row=>row.forEach(n=>c[n.type]=(c[n.type]||0)+1));
      return c;
    })()""")
    check("모든 노드 타입 등장", set(types) >= {"battle","elite","boss","shop","rest","event","treasure"}, types)

    print("\n=== 2. 전투 & 보상 ===")
    new_run()
    pg.evaluate("S.floorIdx=0; renderMap();")
    pg.click(".floor.cur .node"); pg.wait_for_timeout(2000)
    check("전투 화면 진입", pg.evaluate("document.getElementById('battle').classList.contains('active')"))
    check("적 정보 설정", pg.evaluate("S.enc !== null and true") if False else pg.evaluate("S.enc && S.enc.hp > 0"),
          pg.evaluate("S.enc && S.enc.ko"))
    check("적 티어 단어 출제", pg.evaluate("WORDS_EN[S.enc.tier].some(w=>w[0]===S.word.w)"), pg.evaluate("S.word.w"))

    g0 = pg.evaluate("S.gold")
    pg.evaluate(FREEZE)
    pg.evaluate("S.bossHP=1; S.queue=[{w:'apple',ko:'사과',tag:'명사'}]; nextWord();"); pg.wait_for_timeout(150)
    pg.fill("#word-input", "apple"); pg.keyboard.press("Enter"); pg.wait_for_timeout(1500)
    check("승리 패널 표시", pg.evaluate("document.getElementById('panel').classList.contains('show')"))
    check("골드 획득", pg.evaluate("S.gold") > g0, f"{g0} → {pg.evaluate('S.gold')}")
    pg.evaluate("closePanelToMap()"); pg.wait_for_timeout(300)
    check("맵으로 복귀 + 층 진행", pg.evaluate("S.floorIdx") == 1 and pg.evaluate("document.getElementById('map').classList.contains('active')"))
    check("클리어 노드 기록", pg.evaluate("S.cleared[0]") is not None)
    check("맵 HUD 갱신", pg.evaluate("document.getElementById('map-gold').textContent") == str(pg.evaluate("S.gold")))

    print("\n=== 3. 유물 효과 ===")
    def dmg_with(relics, word="apple", post="", **kw):
        """post 는 nextWord() 이후에 적용된다 (nextWord 가 backspaced/extraHint 를 초기화하므로)"""
        pg.evaluate(FREEZE)
        ex = "".join(f"S.{k}={v};" for k, v in kw.items())
        pg.evaluate(f"""() => {{
          S.relics={relics!r}; S.bonusAtk=0; S.combo=0; S.powerUp=false; S.backspaced=false;
          S.pot=0; S.potStreak=0;   // 위험 보너스를 배제하고 유물 배율만 측정한다
          S.extraHint=0; S.wrongTried=false; {ex}
          S.enc={{emoji:'🟢',hp:99999,dmg:10,tier:1,time:99999,gims:[],ko:'테스트'}};
          showScreen('battle'); setMastery({word!r}, MAX_STAGE);
          S.bossHP=99999; S.bossMax=99999; S.playerHP=100;
          S.queue=[{{w:{word!r},ko:'뜻',tag:'태그'}}]; nextWord();
          S.wordStart = performance.now() - S.timerBase;   // 속도 보너스를 0으로 고정
          {post}
        }}""")
        pg.wait_for_timeout(150)
        pg.fill("#word-input", word); pg.keyboard.press("Enter"); pg.wait_for_timeout(450)
        return 99999 - pg.evaluate("S.bossHP")

    NOCRIT = "S.wrongTried=true;"   # 크리티컬을 막아 배수 없는 순수 데미지를 잰다

    base = dmg_with([])
    check("기본 데미지 산출", base > 0, base)
    nocrit = base   # 속도 보너스를 0으로 고정했으므로 기본치와 동일
    check("속도 보너스 없을 때 기본치", base == 16, base)
    check("👅 날카로운 혀 +6", dmg_with([], bonusAtk=6) == base + 6,
          f"{base} → {dmg_with([], bonusAtk=6)}")
    check("✒️ 속기사의 펜(긴 단어 +40%)",
          dmg_with(["pen"], "knowledge") == round(dmg_with([], "knowledge") * 1.4),
          f'{dmg_with([],"knowledge")} → {dmg_with(["pen"],"knowledge")}')
    check("✒️ 짧은 단어엔 효과 없음", dmg_with(["pen"], "apple") == base)
    check("⚔️ 콤보의 검(콤보5 +50%)",
          dmg_with(["sword"], combo=5) == round(dmg_with([], combo=5) * 1.5),
          f'{dmg_with([],combo=5)} → {dmg_with(["sword"],combo=5)}')
    check("⚔️ 저콤보엔 효과 없음", dmg_with(["sword"], combo=2) == dmg_with([], combo=2))
    check("⏳ 모래시계 데미지 -10%", dmg_with(["hour"]) == round(base * 0.9), dmg_with(["hour"]))
    check("🎯 정확의 인장 +30%", dmg_with(["seal"]) == round(base * 1.3), dmg_with(["seal"]))
    check("🎯 백스페이스 시 -20%",
          dmg_with(["seal"], post="S.backspaced=true;") == round(nocrit * 0.8),
          f'{nocrit} → {dmg_with(["seal"], post="S.backspaced=true;")}')
    # 속도 보너스가 최대인 상황에서 관련 유물을 비교한다
    fast = "S.wordStart = performance.now();"      # 남은 시간 100%
    d_base, d_bolt, d_glass = (dmg_with([], post=fast), dmg_with(["bolt"], post=fast),
                               dmg_with(["glass"], post=fast))
    check("속도 최대 시 데미지 2배", d_base == base * 2, f"{base} → {d_base}")
    check("⚡ 이중 타격: 속도 보너스 강화", d_bolt > d_base, f"{d_base} → {d_bolt}")
    check("🔍 돋보기: 속도 보너스 상실", d_glass == base, f"{d_glass} (기본 {base})")

    pg.evaluate(FREEZE)
    pg.evaluate("showScreen('battle'); S.relics=[]; S.enc={emoji:'x',hp:1,dmg:1,tier:1,time:9999,gims:[],ko:'t'}; S.queue=[{w:'apple',ko:'x',tag:'y'}]; nextWord();")
    pg.wait_for_timeout(120)
    n0 = pg.evaluate("hintReveal()")
    pg.evaluate("S.relics=['glass']"); n1 = pg.evaluate("hintReveal()")
    check("🔍 돋보기: 힌트 +1글자", n1 == n0 + 1, f"{n0} → {n1}")
    pg.evaluate("S.relics=['lexicon']; renderHint();")
    h = pg.evaluate("document.getElementById('q-hint').textContent")
    check("📚 사전 편찬자: 마지막 글자 공개", h.strip().startswith("a") and "e" in h.split("(")[0].split()[-1], h.strip()[:16])

    pg.evaluate("S.relics=[]"); t0 = pg.evaluate("bossTime()")
    pg.evaluate("S.relics=['hour']"); t1 = pg.evaluate("bossTime()")
    check("⏳ 모래시계: 시간 +3초", round(t1 - t0) == 3000, f"{round(t0)} → {round(t1)}")

    pg.evaluate("S.relics=[]; S.exp=0; S.level=1; pendingLevelUps=0; gainExp(10)")
    e0 = pg.evaluate("S.exp")
    pg.evaluate("S.relics=['specs']; S.exp=0; gainExp(10)")
    check("👓 학자의 안경: EXP +50%", pg.evaluate("S.exp") == round(e0 * 1.5), f"{e0} → {pg.evaluate('S.exp')}")
    pg.evaluate("S.relics=['curseD']; S.exp=0; gainExp(10)")
    check("📕 저주받은 사전: EXP 2배", pg.evaluate("S.exp") == e0 * 2)
    pg.evaluate("S.relics=[]"); need0 = pg.evaluate("expNeeded()")
    pg.evaluate("S.relics=['crown']")
    check("👑 학자의 왕관: 필요 EXP -20%", pg.evaluate("expNeeded()") == round(need0 * 0.8))

    pg.evaluate(FREEZE)
    pg.evaluate("S.relics=['ring']; S.playerHP=50; S.playerMax=100; S.gold=0;")
    dmg_with(["ring", "quill"], "apple")
    check("🩸 흡혈 반지: 정답 시 회복", pg.evaluate("S.playerHP") > 50, pg.evaluate("S.playerHP"))
    check("🪶 황금 깃펜: 골드 +3", pg.evaluate("S.gold") >= 3, pg.evaluate("S.gold"))

    pg.evaluate(FREEZE)
    pg.evaluate("""showScreen('battle'); S.relics=['amulet']; S.playerHP=100; S.playerMax=100;
      S.enc={emoji:'x',hp:999,dmg:20,tier:1,time:9999,gims:[],ko:'t'};
      S.queue=[{w:'apple',ko:'x',tag:'y'},{w:'water',ko:'물',tag:'명사'}]; nextWord(); onTimeout();""")
    pg.wait_for_timeout(300)
    check("🧿 수호 부적: 시간초과 피해 절반", pg.evaluate("S.playerHP") == 90, pg.evaluate("S.playerHP"))

    pg.evaluate(FREEZE)
    pg.evaluate("S.relics=['bell']; S.queue=[{w:'a',ko:'1',tag:'t'},{w:'b',ko:'2',tag:'t'},{w:'c',ko:'3',tag:'t'}];")
    pg.evaluate("requeue({w:'zz',ko:'z',tag:'t'},4)")
    cnt = pg.evaluate("S.queue.filter(q=>q.w==='zz').length")
    check("🔔 메아리의 종: 2회 재출제", cnt == 2, cnt)
    pg.evaluate("S.relics=[]; S.queue=[{w:'a',ko:'1',tag:'t'}]; requeue({w:'yy',ko:'y',tag:'t'},4)")
    check("🔔 없으면 1회만", pg.evaluate("S.queue.filter(q=>q.w==='yy').length") == 1)

    pg.evaluate(FREEZE)
    pg.evaluate("S.relics=['phoenix']; S.phoenixUsed=false; S.playerMax=100; S.playerHP=10;")
    pg.evaluate("hurtPlayer(99,true)"); pg.wait_for_timeout(400)
    check("🔥 불사조: 부활", pg.evaluate("S.playerHP") == 50 and pg.evaluate("S.phoenixUsed") is True,
          pg.evaluate("S.playerHP"))
    check("🔥 부활 후 유물 소모", not pg.evaluate("hasRelic('phoenix')"))
    check("🔥 결과화면 아님", not pg.evaluate("document.getElementById('result').classList.contains('active')"))
    pg.evaluate("S.playerHP=5; hurtPlayer(99,true)"); pg.wait_for_timeout(1100)
    check("🔥 두 번째는 사망", pg.evaluate("document.getElementById('result').classList.contains('active')"))

    pg.evaluate("S.relics=[]; S.skipsMax=3; S.skips=3; giveRelic('map')")
    check("🗺️ 여행자의 지도: 건너뛰기 +2", pg.evaluate("S.skipsMax") == 5 and pg.evaluate("S.skips") == 5)
    pg.evaluate("S.playerMax=100; S.playerHP=100; S.relics=[]; giveRelic('rune')")
    check("🌟 각성의 룬: 최대체력 +25", pg.evaluate("S.playerMax") == 125 and pg.evaluate("S.playerHP") == 125)
    pg.evaluate("S.bonusAtk=0; S.relics=[]; giveRelic('tongue')")
    check("👅 획득 시 공격력 +6", pg.evaluate("S.bonusAtk") == 6)
    pg.evaluate("S.relics=[]; giveRelic('pen')")
    check("중복 획득 방지", pg.evaluate("giveRelic('pen')") is False and pg.evaluate("S.relics.length") == 1)

    print("\n=== 4. 상점 ===")
    new_run()
    pg.evaluate("S.gold=500; openShop();"); pg.wait_for_timeout(300)
    check("상점 패널 표시", pg.evaluate("document.getElementById('panel').classList.contains('show')"))
    n = pg.evaluate("document.querySelectorAll('#pn-opts .opt').length")
    check("상품 7개(유물3+소모품4)", n == 7, n)
    g0 = pg.evaluate("S.gold"); r0 = pg.evaluate("S.relics.length")
    pg.click("#pn-opts .opt"); pg.wait_for_timeout(250)
    check("유물 구매: 골드 차감", pg.evaluate("S.gold") < g0, f"{g0} → {pg.evaluate('S.gold')}")
    check("유물 구매: 획득", pg.evaluate("S.relics.length") == r0 + 1)
    check("구매한 항목 비활성", pg.evaluate("document.querySelectorAll('#pn-opts .opt.dis').length") >= 1)

    pg.evaluate("S.gold=500; S.playerHP=10; S.playerMax=100; openShop();"); pg.wait_for_timeout(200)
    pg.evaluate("""[...document.querySelectorAll('#pn-opts .opt')].find(e=>e.textContent.includes('치유 물약')).click()""")
    pg.wait_for_timeout(200)
    check("치유 물약: 체력 회복", pg.evaluate("S.playerHP") == 55, pg.evaluate("S.playerHP"))
    pg.evaluate("""[...document.querySelectorAll('#pn-opts .opt')].find(e=>e.textContent.includes('생명의 열매')).click()""")
    pg.wait_for_timeout(200)
    check("생명의 열매: 최대체력 +15", pg.evaluate("S.playerMax") == 115)
    c0 = pg.evaluate("S.charges.hint")
    pg.evaluate("""[...document.querySelectorAll('#pn-opts .opt')].find(e=>e.textContent.includes('스킬 보급')).click()""")
    pg.wait_for_timeout(200)
    check("스킬 보급: 전 스킬 +2", pg.evaluate("S.charges.hint") == c0 + 2)

    pg.evaluate("S.gold=0; openShop();"); pg.wait_for_timeout(200)
    check("골드 부족 시 전부 비활성",
          pg.evaluate("document.querySelectorAll('#pn-opts .opt.dis').length") ==
          pg.evaluate("document.querySelectorAll('#pn-opts .opt').length"))
    g_before = pg.evaluate("S.gold")
    pg.click("#pn-opts .opt"); pg.wait_for_timeout(200)
    check("구매 불가 항목 클릭 무시", pg.evaluate("S.gold") == g_before)

    print("\n=== 5. 이벤트 ===")
    new_run()
    bad_ev = pg.evaluate("""(() => {
      const errs=[];
      EVENTS.forEach(e=>{
        if(!e.t||!e.d||!e.ic) errs.push('필드누락 '+e.t);
        if(!e.opts || e.opts.length<2) errs.push('선택지부족 '+e.t);
        e.opts.forEach(o=>{ if(!o.t||!o.d||typeof o.run!=='function') errs.push('옵션불량 '+e.t); });
      });
      return errs;
    })()""")
    check("이벤트 9종 구조 정상", bad_ev == [], bad_ev)

    pg.evaluate("S.gold=200; S.playerHP=50; S.playerMax=100; openEvent();"); pg.wait_for_timeout(250)
    check("이벤트 패널 표시", pg.evaluate("document.getElementById('panel').classList.contains('show')"))
    pg.evaluate("document.querySelectorAll('#pn-opts .opt:not(.dis)')[0].click()"); pg.wait_for_timeout(300)
    check("선택 후 결과 표시", pg.evaluate("document.getElementById('pn-title').textContent") == "결과")
    check("계속 버튼 존재", "계속" in pg.evaluate("document.getElementById('pn-foot').textContent"))
    check("이벤트로 죽지 않음", pg.evaluate("S.playerHP") >= 1, pg.evaluate("S.playerHP"))

    # 모든 이벤트의 모든 선택지를 강제 실행
    crash = pg.evaluate("""(() => {
      const errs=[];
      EVENTS.forEach((e,ei)=>e.opts.forEach((o,oi)=>{
        S.gold=300; S.playerHP=80; S.playerMax=100; S.relics=[]; S.charges={hint:1,time:1,heal:1,power:1};
        S.skips=1; S.skipsMax=1; S.exp=0; S.level=1; pendingLevelUps=0;
        try{ if(o.cost) S.gold-=o.cost; const r=o.run();
             if(typeof r!=='string'||!r.length) errs.push(e.t+'/'+o.t+' 메시지없음');
             if(S.playerHP<1) errs.push(e.t+'/'+o.t+' 사망');
             if(S.gold<0) errs.push(e.t+'/'+o.t+' 골드음수');
        }catch(err){ errs.push(e.t+'/'+o.t+' 예외:'+err.message); }
      }));
      return errs;
    })()""")
    check("전체 선택지 실행 안전", crash == [], crash)

    pg.evaluate("S.gold=0; openEvent();"); pg.wait_for_timeout(200)
    costly = pg.evaluate("""(()=>{const ev=[...document.querySelectorAll('#pn-opts .opt')].filter(e=>e.querySelector('.price'));
                           return ev.length ? ev.every(e=>e.classList.contains('dis')) : 'N/A';})()""")
    check("골드 부족 시 유료 선택지 잠김", costly in (True, "N/A"), costly)

    print("\n=== 6. 휴식 / 보물 ===")
    new_run()
    pg.evaluate("S.playerHP=10; S.playerMax=100; openRest();"); pg.wait_for_timeout(250)
    check("휴식 선택지 3개", pg.evaluate("document.querySelectorAll('#pn-opts .opt').length") == 3)
    pg.click("#pn-opts .opt"); pg.wait_for_timeout(250)
    check("모닥불 회복", pg.evaluate("S.playerHP") == 50, pg.evaluate("S.playerHP"))
    check("휴식 후 맵 복귀", pg.evaluate("document.getElementById('map').classList.contains('active')"))

    new_run()
    r0 = pg.evaluate("S.relics.length")
    pg.evaluate("openTreasure()"); pg.wait_for_timeout(250)
    check("보물 선택지 3개", pg.evaluate("document.querySelectorAll('#pn-opts .opt').length") == 3)
    pg.click("#pn-opts .opt"); pg.wait_for_timeout(250)
    check("보물에서 유물 획득", pg.evaluate("S.relics.length") == r0 + 1)

    print("\n=== 7. 런 종료 ===")
    new_run()
    pg.evaluate(FREEZE)
    pg.evaluate("""S.floorIdx=15; S.gold=250; S.relics=['pen','ring'];
      startEncounter(S.floors[15][0]);""")
    pg.wait_for_timeout(1900)
    check("최종 보스 진입", pg.evaluate("S.enc.final") is True and pg.evaluate("S.enc.ko") == "드래곤 로드")
    pg.evaluate(FREEZE)
    pg.evaluate("S.bossHP=1; S.queue=[{w:'apple',ko:'사과',tag:'명사'}]; nextWord();"); pg.wait_for_timeout(150)
    pg.fill("#word-input", "apple"); pg.keyboard.press("Enter"); pg.wait_for_timeout(1500)
    check("최종 보스 처치 → 승리", pg.evaluate("document.getElementById('result').classList.contains('active')")
          and pg.evaluate("document.getElementById('result-title').textContent") == "CLEAR")
    check("도달 층 표시", "16" in pg.evaluate("document.getElementById('st-boss').textContent"),
          pg.evaluate("document.getElementById('st-boss').textContent"))
    check("통계 라벨 '도달 층'",
          pg.evaluate("document.getElementById('st-boss').nextElementSibling.textContent") == "도달 층")
    check("유물 목록 표시", "속기사" in pg.evaluate("document.getElementById('result-sub').textContent"))
    _gold = pg.evaluate("S.gold")
    check("골드 표시", f"{_gold}G" in pg.evaluate("document.getElementById('result-sub').textContent"),
          f"S.gold={_gold}")
    pg.screenshot(path="rogue_result.png")

    new_run()
    pg.evaluate(FREEZE)
    pg.evaluate("S.floorIdx=4; startEncounter(S.floors[4][0]);"); pg.wait_for_timeout(1900)
    pg.evaluate("S.relics=[]; S.phoenixUsed=true; S.playerHP=5; hurtPlayer(99,true);"); pg.wait_for_timeout(1100)
    check("사망 → 패배 + 층 표시", pg.evaluate("document.getElementById('result-title').textContent") == "DEFEAT"
          and "5층" in pg.evaluate("document.getElementById('st-boss').textContent"),
          pg.evaluate("document.getElementById('st-boss').textContent"))

    print("\n=== 8. 스크린샷 ===")
    new_run()
    pg.evaluate("S.gold=180; S.relics=['pen','ring','sword','bell']; S.floorIdx=6; renderMap();")
    pg.wait_for_timeout(400); pg.screenshot(path="rogue_map.png")
    pg.evaluate("S.gold=300; openShop();"); pg.wait_for_timeout(300)
    pg.screenshot(path="rogue_shop.png")
    pg.evaluate("closePanelToMap(); S.floorIdx=6; openEvent();"); pg.wait_for_timeout(300)
    pg.screenshot(path="rogue_event.png")

    print("\n=== 10. 유물 상세 정보 (맵) ===")
    new_run()
    check("유물 없을 때 안내", "유물 없음" in pg.evaluate("document.getElementById('relic-bar').textContent"))
    pg.keyboard.press("R"); pg.wait_for_timeout(250)
    check("R 키로 목록 열기", pg.evaluate("document.getElementById('panel').classList.contains('show')"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(250)
    check("Esc 로 닫기", not pg.evaluate("document.getElementById('panel').classList.contains('show')"))

    pg.evaluate("S.floorIdx=3; giveRelic('pen'); S.floorIdx=6; giveRelic('ring'); renderMap();")
    pg.wait_for_timeout(250)
    check("아이콘 렌더링", pg.evaluate("document.querySelectorAll('#relic-bar .rl').length") == 2)
    check("획득 층 기록", pg.evaluate("[S.relicMeta.pen, S.relicMeta.ring]") == [4, 7],
          pg.evaluate("S.relicMeta"))
    tip = pg.evaluate("document.querySelector('#relic-bar .rl-tip').textContent")
    check("툴팁에 이름·효과·획득층", all(k in tip for k in ["속기사의 펜", "+40%", "4층에서 획득"]), tip[:36])
    check("툴팁은 기본 숨김",
          pg.evaluate("getComputedStyle(document.querySelector('.rl-tip')).display") == "none")
    pg.hover("#relic-bar .rl"); pg.wait_for_timeout(250)
    check("호버 시 노출",
          pg.evaluate("getComputedStyle(document.querySelector('.rl-tip')).display") == "block")

    floor_before = pg.evaluate("S.floorIdx")
    pg.click("#relic-bar .rl"); pg.wait_for_timeout(300)
    check("아이콘 클릭으로 목록", pg.evaluate("document.querySelectorAll('#pn-opts .relic-row').length") == 2)
    check("클릭한 유물 강조", pg.evaluate("document.querySelectorAll('#pn-opts .relic-row.hl').length") == 1)
    check("설명이 RELICS 정의와 일치", pg.evaluate(
        "(()=>{const t=document.getElementById('pn-opts').textContent;"
        "return S.relics.every(id=>t.includes(relicById(id).ds));})()"))
    pg.evaluate("document.querySelector('#pn-foot .ov-btn').click()"); pg.wait_for_timeout(300)
    check("닫아도 층 진행 없음", pg.evaluate("S.floorIdx") == floor_before)
    check("맵 화면 유지", pg.evaluate("document.getElementById('map').classList.contains('active')"))

    pg.evaluate("S.floorIdx=0; startEncounter(S.floors[0][0]);"); pg.wait_for_timeout(2000)
    h0 = pg.evaluate("S.charges.hint")
    pg.keyboard.press("R"); pg.wait_for_timeout(250)
    check("전투 중에는 열리지 않음", not pg.evaluate("document.getElementById('panel').classList.contains('show')")
          and pg.evaluate("S.charges.hint") == h0)
    br.close()

print("\n" + "=" * 46)
print("JS 에러:", errors if errors else "없음")
print("실패:", fails if fails else "없음  ✅ 전체 통과")
