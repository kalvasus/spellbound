/* =======================================================================
   ROGUELIKE MODE — 분기 맵 · 유물 · 골드/상점 · 랜덤 이벤트
   ======================================================================= */

/* ---------- 일반 몹 ---------- */
const ENEMIES = [
  { emoji:"slime", en:"Slime",     es:"Limo",       ko:"슬라임",   hp:85,  dmg:8,  gims:[] },
  { emoji:"goblin", en:"Goblin",    es:"Duende",     ko:"고블린",   hp:100, dmg:10, gims:[] },
  { emoji:"spider", en:"Spider",    es:"Araña",      ko:"거미",     hp:95,  dmg:9,  gims:["haste"] },
  { emoji:"zombie", en:"Zombie",    es:"Zombi",      ko:"좀비",     hp:120, dmg:9,  gims:["drain"] },
  { emoji:"scorpion", en:"Scorpion",  es:"Escorpión",  ko:"전갈",     hp:105, dmg:13, gims:[] },
  { emoji:"wolf", en:"Wolf",      es:"Lobo",       ko:"늑대",     hp:110, dmg:11, gims:["haste"] },
  { emoji:"bat", en:"Bat",       es:"Murciélago", ko:"박쥐",     hp:90,  dmg:10, gims:["drain"] },
  { emoji:"rock", en:"Rock Beast",es:"Bestia",     ko:"바위 짐승", hp:135, dmg:10, gims:["shield"] }
];

/* ---------- 엘리트 ---------- */
const ELITES = [
  { emoji:"golem", en:"Stone Golem",  es:"El Gólem",    ko:"스톤 골렘",       hp:190, dmg:15, gims:["shield"],
    gim:"방패", gimDesc:"콤보 3 미만이면 데미지 절반" },
  { emoji:"ghost", en:"Cursed Ghost", es:"El Fantasma", ko:"저주받은 유령",   hp:175, dmg:16, gims:["curse"],
    gim:"저주", gimDesc:"첫 글자 힌트가 사라진다" },
  { emoji:"wraith", en:"Storm Wraith", es:"El Espectro", ko:"폭풍 망령",       hp:180, dmg:16, gims:["haste"],
    gim:"가속", gimDesc:"맞힐수록 제한시간이 짧아진다" },
  { emoji:"vampire", en:"Vampire",      es:"El Vampiro",  ko:"흡혈귀",          hp:200, dmg:15, gims:["drain"],
    gim:"흡혈", gimDesc:"틀리면 적이 체력을 회복한다" }
];

/* ---------- 구간 보스 ---------- */
const RUN_BOSSES = [
  { emoji:"wyrm", en:"Wyrm",        es:"La Sierpe",  ko:"어린 용",     hp:260, dmg:17, gims:["shield"],
    gim:"방패", gimDesc:"콤보 3 미만이면 데미지 절반" },
  { emoji:"ogre", en:"Ogre King",   es:"El Ogro",    ko:"오우거 왕",   hp:330, dmg:20, gims:["haste","drain"],
    gim:"가속+흡혈", gimDesc:"시간이 짧아지고, 틀리면 회복한다" },
  { emoji:"dragon", en:"Dragon Lord", es:"El Dragón",  ko:"드래곤 로드", hp:420, dmg:24, gims:["curse","haste","drain"],
    gim:"최종", gimDesc:"힌트 없음 + 가속 + 흡혈" }
];

/* ---------- 유물 ---------- */
const RELICS = [
  { id:"glass",   ic:"glass", nm:"돋보기",        ds:"힌트가 항상 1글자 더 공개된다. 대신 속도 보너스를 받지 못한다." },
  { id:"pen",   ic:"pen", nm:"속기사의 펜",    ds:"8글자 이상 긴 단어의 데미지 +40%" },
  { id:"ring",   ic:"ring", nm:"흡혈 반지",      ds:"단어를 맞힐 때마다 체력을 3 회복한다" },
  { id:"sword",   ic:"sword", nm:"콤보의 검",      ds:"콤보 5 이상일 때 데미지 +50%" },
  { id:"hour",   ic:"hour", nm:"모래시계",       ds:"모든 제한시간 +3초. 대신 데미지 -10%" },
  { id:"seal",   ic:"seal", nm:"정확의 인장",    ds:"백스페이스 없이 맞히면 +30%, 쓰면 -20%" },
  { id:"curseD",   ic:"curseD", nm:"저주받은 사전",  ds:"EXP 2배. 대신 오답 피해가 2배가 된다" },
  { id:"bell",   ic:"bell", nm:"메아리의 종",    ds:"틀리거나 건너뛴 단어가 훨씬 자주 다시 나온다" },
  { id:"specs",   ic:"specs", nm:"학자의 안경",    ds:"획득 EXP +50%" },
  { id:"quill",   ic:"quill", nm:"황금 깃펜",      ds:"단어를 맞힐 때마다 골드 +3" },
  { id:"amulet",   ic:"amulet", nm:"수호 부적",      ds:"시간 초과로 받는 피해가 절반이 된다" },
  { id:"bolt",   ic:"bolt", nm:"이중 타격",      ds:"속도 보너스가 25% 더 강해진다 (최대 +125%)" },
  { id:"map",   ic:"map", nm:"여행자의 지도",  ds:"건너뛰기 가능 횟수 +2" },
  { id:"phoenix",   ic:"phoenix", nm:"불사조 깃털",    ds:"쓰러질 때 1회 부활한다 (체력 50% 회복, 소모됨)" },
  { id:"lexicon",   ic:"lexicon", nm:"사전 편찬자",    ds:"첫 글자에 더해 마지막 글자도 공개된다" },
  { id:"rune",   ic:"rune", nm:"각성의 룬",      ds:"최대 체력 +25 (즉시 회복)", onGet:()=>{ S.playerMax+=25; S.playerHP+=25; } },
  { id:"tongue",   ic:"tongue", nm:"날카로운 혀",    ds:"기본 공격력 +6",              onGet:()=>{ S.bonusAtk+=6; } },
  { id:"crown",   ic:"crown", nm:"학자의 왕관",    ds:"레벨업에 필요한 EXP가 20% 줄어든다" }
];

function hasRelic(id){ return !!(S && S.relics && S.relics.includes(id)); }
function relicById(id){ return RELICS.find(r => r.id === id); }

function giveRelic(id){
  if(!S || hasRelic(id)) return false;
  S.relics.push(id);
  if(!S.relicMeta) S.relicMeta = {};
  S.relicMeta[id] = (S.floorIdx || 0) + 1;      // 몇 층에서 얻었는지 기록
  const r = relicById(id);
  if(r && r.onGet) r.onGet();
  if(id === "map"){ S.skipsMax += 2; S.skips += 2; updateSkipUI && updateSkipUI(); }
  if(typeof AUDIO !== "undefined") AUDIO.sfx("relic");
  updateRelicBar();
  return true;
}
function randomRelics(n){
  const pool = RELICS.filter(r => !hasRelic(r.id));
  return shuffle(pool).slice(0, n);
}

/* ---------- 랜덤 이벤트 ---------- */
const EVENTS = [
  { ic:"evBook", t:"수상한 사전", d:"먼지 쌓인 사전이 혼자 페이지를 넘기고 있다. 읽어볼까?",
    opts:[
      { t:"읽는다", d:"50% 확률로 유물, 아니면 체력 -15",
        run:()=> pick(0.5) ? grantRelic("사전이 지식을 내주었다!") : dmgLog(15,"글자들이 눈을 찔렀다! 체력 -15") },
      { t:"덮어둔다", d:"아무 일도 없다", run:()=> log2("조용히 책을 덮었다.") }
    ]},
  { ic:"evSpring", t:"맑은 샘물", d:"차갑고 투명한 샘이 솟는다.",
    opts:[
      { t:"마신다", d:"체력을 전부 회복한다",
        run:()=>{ S.playerHP = S.playerMax; return "몸이 개운해졌다. 체력 완전 회복!"; } },
      { t:"병에 담는다", d:"회복 스킬 +3회",
        run:()=>{ S.charges.heal += 3; return "회복 스킬을 3회 얻었다."; } }
    ]},
  { ic:"evTrader", t:"떠돌이 상인", d:"후드를 쓴 상인이 보따리를 열어 보인다.",
    opts:[
      { t:"40골드로 산다", d:"무작위 유물 1개", cost:40,
        run:()=> grantRelic("상인이 유물을 건넸다!") },
      { t:"지나친다", d:"아무 일도 없다", run:()=> log2("상인은 어둠 속으로 사라졌다.") }
    ]},
  { ic:"evStele", t:"오래된 비석", d:"낯선 문자가 새겨진 비석. 동전을 바치는 자국이 있다.",
    opts:[
      { t:"50골드를 바친다", d:"최대 체력 +20", cost:50,
        run:()=>{ S.playerMax += 20; S.playerHP += 20; return "비석이 빛났다. 최대 체력 +20!"; } },
      { t:"무시한다", d:"아무 일도 없다", run:()=> log2("비석은 침묵했다.") }
    ]},
  { ic:"evThief", t:"밤의 도둑", d:"그림자가 당신의 짐을 노린다.",
    opts:[
      { t:"짐을 지킨다", d:"체력 -18",
        run:()=> dmgLog(18,"몸싸움 끝에 지켜냈다. 체력 -18") },
      { t:"골드를 던진다", d:"골드 -35",
        run:()=>{ const g=Math.min(35,S.gold); S.gold-=g; return "도둑은 골드 "+g+"를 챙겨 사라졌다."; } }
    ]},
  { ic:"evAltar", t:"지혜의 제단", d:"제단 위에 두 개의 그릇이 놓여 있다.",
    opts:[
      { t:"왼쪽 그릇", d:"EXP +90", run:()=>{ gainExp(90); return "머릿속이 환해졌다. EXP +90!"; } },
      { t:"오른쪽 그릇", d:"골드 +70", run:()=>{ S.gold += 70; return "금화가 쏟아졌다. 골드 +70!"; } }
    ]},
  { ic:"evTemple", t:"언어의 신전", d:"신전은 대가를 요구한다.",
    opts:[
      { t:"피를 바친다", d:"최대 체력 -12, 유물 1개",
        run:()=>{ S.playerMax = Math.max(30, S.playerMax-12); S.playerHP = Math.min(S.playerHP, S.playerMax);
                  return grantRelic("신전이 유물을 내주었다. (최대 체력 -12)"); } },
      { t:"물러난다", d:"아무 일도 없다", run:()=> log2("신은 응답하지 않았다.") }
    ]},
  { ic:"evShelf", t:"낡은 책장", d:"쓸 만한 물건이 굴러다닌다.",
    opts:[
      { t:"지도 조각", d:"건너뛰기 +3회",
        run:()=>{ S.skipsMax += 3; S.skips += 3; updateSkipUI(); return "건너뛰기를 3회 얻었다."; } },
      { t:"돋보기 조각", d:"힌트 스킬 +3회",
        run:()=>{ S.charges.hint += 3; return "힌트 스킬을 3회 얻었다."; } }
    ]},
  { ic:"evDice", t:"도박꾼의 탁자", d:"\"운을 시험해 보시겠소?\"",
    opts:[
      { t:"30골드를 건다", d:"50%: 골드 +90 / 50%: 잃는다", cost:30,
        run:()=> pick(0.5) ? (S.gold+=90, "이겼다! 골드 +90") : "졌다... 판돈을 잃었다." },
      { t:"거절한다", d:"아무 일도 없다", run:()=> log2("현명한 선택이었다.") }
    ]}
];

function pick(p){ return Math.random() < p; }
function log2(m){ return m; }
function dmgLog(n, msg){
  S.playerHP = Math.max(1, S.playerHP - n);   // 이벤트로는 죽지 않는다
  return msg;
}
function grantRelic(msg){
  const c = randomRelics(1)[0];
  if(!c) return "더 얻을 유물이 없다. 대신 골드 +50" + (S.gold += 50, "");
  giveRelic(c.id);
  return msg + "  " + c.ic + " " + c.nm;
}

/* ---------- 맵 생성 ---------- */
const RUN_FLOORS   = 16;                 // 0 ~ 15
const BOSS_FLOORS  = [5, 10, 15];
const SHOP_FLOORS  = [3, 8, 13];         // 이 층에는 상점이 반드시 하나 있다

/* 초보자 모드에서는 어려운 티어(4~5)를 출제하지 않는다 */
function nodeTier(floor){
  const t = Math.min(5, 1 + Math.floor(floor / 3.2));
  return (typeof NOVICE !== "undefined" && NOVICE) ? Math.min(3, t) : t;
}

function makeNode(type, floor){
  const tier = nodeTier(floor);
  if(type === "battle"){
    const e = ENEMIES[Math.floor(Math.random()*ENEMIES.length)];
    const scale = 1 + floor * 0.10;
    return { type, tier, emoji:e.emoji, base:e,
             hp: Math.round(e.hp*scale), dmg: Math.round(e.dmg*(1+floor*0.05)),
             gims: e.gims, gold:[18,30] };
  }
  if(type === "elite"){
    const e = ELITES[Math.floor(Math.random()*ELITES.length)];
    const scale = 1 + floor * 0.09;
    return { type, tier, emoji:e.emoji, base:e,
             hp: Math.round(e.hp*scale), dmg: Math.round(e.dmg*(1+floor*0.04)),
             gims: e.gims, gim:e.gim, gimDesc:e.gimDesc, gold:[45,70] };
  }
  if(type === "boss"){
    const idx = BOSS_FLOORS.indexOf(floor);
    const e = RUN_BOSSES[idx] || RUN_BOSSES[RUN_BOSSES.length-1];
    const cap = (typeof NOVICE !== "undefined" && NOVICE) ? 3 : 5;
    return { type, tier: Math.min(cap, tier+1), emoji:e.emoji, base:e,
             hp:e.hp, dmg:e.dmg, gims:e.gims, gim:e.gim, gimDesc:e.gimDesc,
             gold:[80,110], final: idx === RUN_BOSSES.length-1 };
  }
  const meta = {
    shop:     { emoji:"shop", label:"상점" },
    rest:     { emoji:"rest", label:"휴식" },
    event:    { emoji:"event", label:"이벤트" },
    treasure: { emoji:"treasure", label:"보물" }
  }[type];
  return { type, tier, emoji: meta.emoji, label: meta.label };
}

function generateMap(){
  const floors = [];
  for(let f = 0; f < RUN_FLOORS; f++){
    if(BOSS_FLOORS.includes(f)){ floors.push([makeNode("boss", f)]); continue; }
    if(f === 0){ floors.push([makeNode("battle",0), makeNode("battle",0)]); continue; }

    const beforeBoss = BOSS_FLOORS.includes(f+1);
    const count = 2 + (Math.random() < 0.45 ? 1 : 0);
    const types = [];

    if(SHOP_FLOORS.includes(f)) types.push("shop");
    if(beforeBoss) types.push("rest");           // 보스 직전엔 항상 정비 기회

    const pool = ["battle","battle","battle","event","event","elite","treasure","rest"];
    while(types.length < count){
      const t = pool[Math.floor(Math.random()*pool.length)];
      if(t === "elite" && f < 3) continue;        // 초반엔 엘리트 없음
      if(types.includes(t) && t !== "battle") continue;
      types.push(t);
    }
    floors.push(shuffle(types).map(t => makeNode(t, f)));
  }
  return floors;
}
