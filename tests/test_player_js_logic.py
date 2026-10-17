"""#181/#182: JavaScript-Playerlogik unter Node prüfen, ohne Browser/Audio-Hardware.

Node ist optional (Test wird ohne Node übersprungen), läuft in GitHub Actions aber
auf den Windows-/macOS-Runnern. Der Browser-Praxistest bleibt zusätzlich nötig.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")

CHECK = r"""
'use strict';
const fs = require('fs');
const vm = require('vm');
const assert = require('assert').strict;
const { performance } = require('perf_hooks');
const ctx = vm.createContext({
  console, performance, setTimeout, clearTimeout, setInterval, clearInterval,
  document: {activeElement: {tagName:'BODY', closest:()=>null}, getElementById:()=>null},
  window: {}, navigator: {}, toast:()=>{},
  S: {module:'tagger'}, TG: {order:[], anchor:0},
  $:()=>({hidden:true})
});
for (const name of ['player.js', 'player2.js', 'metronome.js', 'xfadesync.js']) {
  vm.runInContext(fs.readFileSync('web/' + name,'utf8'), ctx, {filename:name});
}
const run = (code) => vm.runInContext(code,ctx);
run('plRender = () => {}; dbRender = () => {};');
function approx(a,b,delta=0.00001){assert(Math.abs(a-b)<=delta, a+' != '+b);}

// #181: signierte Verzögerung kalibriert die Mediaposition (bei 0 ms exakt unverändert).
const g120 = run("({bpm:120,markers:[{pos:0,bpm:120}]})"); ctx.g120 = g120;
approx(run("plXfadeCalibratedTime(g120,10,0,1)"),10);
approx(run("plXfadeCalibratedTime(g120,10,100,1)"),9.9); // +100 ms: Folgetrack später
approx(run("plXfadeCalibratedTime(g120,10,-100,1)"),10.1); // -100 ms: früher
approx(run("plXfadeCalibratedTime(g120,10,100,1.05)"),9.895); // Tempoänderung
approx(run("plXfadeCalibratedTime(g120,0,100,1,1)"),0.4); // negative Seek-Zeit vermeiden
approx(run("plXfadeCalibratedTime(g120,0,100,1,4)"),1.9); // Taktphase bewahren
approx(run("plXfadeCalibratedTime(g120,10,2000,1)"),9.5); // Eingabe auf ±500 begrenzen
// Beat-/Taktrechnung: Am Titelanfang darf das Alignment nicht auf Position null
// gekappt werden, sonst stimmt die Phase bei verzögertem erstem Beat nicht.
const aligned = run("gridAlign({bpm:120,markers:[{pos:0.3,bpm:120}]},0,0.75)");
assert(aligned>=0);
approx(run("gridPhase({bpm:120,markers:[{pos:0.3,bpm:120}]},"+aligned+")"),0.75);
// Die inverse Beatfunktion muss auch bei Tempo-Marker-Wechsel 4 Beats springen.
const jump = run("(() => {const g={bpm:120,markers:[{pos:0.5,bpm:120},{pos:32.5,bpm:128}]};const t=30.5;const x=gridTimeOfBeat(g,gridBeatAt(g,t)+4);return gridBeatAt(g,x)-gridBeatAt(g,t)})()");
approx(jump,4);

run("PLAYER.audio={src:'file',currentTime:10,duration:80,paused:true}; PLAYER.info={bpm:120,grid:{bpm:120,markers:[{pos:0,bpm:120}]},cues:[{pos:22,kind:'cue'},{pos:8,kind:'cue'},{pos:12,kind:'loop'}]};");
run("plBarJump(1)");approx(run("PLAYER.audio.currentTime"),12);
run("plBarJump(-1)");approx(run("PLAYER.audio.currentTime"),10);
run("plCueJump(1)");approx(run("PLAYER.audio.currentTime"),22);
run("plCueJump(-1)");approx(run("PLAYER.audio.currentTime"),8);
// Direkt nach dem Anspringen eines Cue zeigt Shift+← auf den davor liegenden Cue.
run("PLAYER.info.cues=[{pos:2,kind:'cue'},{pos:10,kind:'cue'},{pos:40,kind:'cue'}]; PLAYER.audio.currentTime=11");
run("plCueJump(-1)");approx(run("PLAYER.audio.currentTime"),2);
run("PLAYER.audio.currentTime=19");
run("plCueJump(-1)");approx(run("PLAYER.audio.currentTime"),10);
run("PLAYER.audio.currentTime=11");
run("plCueJump(1)");approx(run("PLAYER.audio.currentTime"),40);
// Bei variablem Grid bestimmt die Beatanzahl statt einer festen Sekundenanzahl das Fenster.
const gVar = run("({bpm:120,markers:[{pos:0,bpm:120},{pos:20,bpm:128}]})");
ctx.testGrid = gVar;
const cueVar = run("plCueTarget([{pos:5,kind:'cue'},{pos:25,kind:'cue'}],27,-1,testGrid,120)");
assert.equal(cueVar,5);
run("PLAYER.info.cues=[{pos:22,kind:'cue'},{pos:8,kind:'cue'},{pos:12,kind:'loop'}]; PLAYER.audio.currentTime=8");
const old = run("PLAYER.audio.currentTime");
assert.equal(run("plBarSeek(PLAYER.audio,{bpm:0},1)"),false);
approx(run("PLAYER.audio.currentTime"),old);

// #181: Pegelregler, Begrenzung, Stummstellung und neuer obertonreicher Klick.
assert.equal(run("plMetroVolume(150)"), 100);
assert.equal(run("plMetroVolume(-3)"), 0);
assert.equal(run("plMetroVolume(60.7)"), 61);
approx(run("plMetroPeak(false,80)"), 0.544);
approx(run("plMetroPeak(true,80)"), 0.624);
assert.equal(run("plMetroPeak(false,0)"), 0);
assert(run("plMetroPeak(false,80)") > 0.20);
const gains = [], freqs = [], waves = [], started = [];
ctx.fakeCtx = {
  createOscillator(){
    const osc={type:"sine",frequency:{setValueAtTime:v=>freqs.push(v)},
      connect(){}, disconnect(){}, start(){started.push(true)}, stop(){}};
    waves.push(osc); return osc;
  },
  createGain(){
    return {gain:{setValueAtTime:v=>gains.push(v),
      exponentialRampToValueAtTime:v=>gains.push(v)},
      connect(){}, disconnect(){}};
  },
  destination:{}
};
run("PL_METRO.ctx=fakeCtx;plMetroSetVolume(80);plMetroClick(1,false)");
assert(waves[0].type === 'square'); // mehr Obertöne als Sinuston
approx(gains[1], 0.544);
assert.equal(freqs[0],1600);
const tickCount=started.length;
run("plMetroSetVolume(0);plMetroClick(2,false)");
assert.equal(started.length,tickCount); // bei 0 % kein weiterer Ton
run("plMetroSetVolume(80);PL_METRO.ctx=null;PL_METRO.nodes.clear()");
// #181: geglättete Medienuhr – nach einem Sprung erst wieder planen, wenn die Wiedergabe gleichmässig läuft.
run("var CK={samples:[]}");
for (let k=0;k<8;k++) assert.equal(run(`plClockSample(CK,${1000+k*25},${10+k*0.025},1)`), false);
approx(run("plClockEstimate(CK,1200,1)"), 10.2, 0.002);
// grob gerasterte currentTime (Sprünge um 10 ms) wird geglättet, nicht als Sprung gewertet
run("CK={samples:[]}");
for (let k=0;k<10;k++) { const m=Math.floor((k*0.025)*100)/100; assert.equal(run(`plClockSample(CK,${2000+k*25},${30+m},1)`), false); }
approx(run("plClockEstimate(CK,2250,1)"), 30.25, 0.012);
// Klick in die Wellenform: Sprung → Reset, danach steht die Zeit beim Anlaufen still → kein Schätzwert
assert.equal(run("plClockSample(CK,2275,60,1)"), true);
assert.equal(run("plClockEstimate(CK,2275,1)"), null);
assert.equal(run("plClockSample(CK,2300,60,1)"), false);
assert.equal(run("plClockSample(CK,2350,60,1)"), true);   // Stillstand 50 ms > Toleranz → erneut zurückgesetzt
for (let k=1;k<=7;k++) run(`plClockSample(CK,${2350+k*25},${60+k*0.025},1)`);
approx(run("plClockEstimate(CK,2525,1)"), 60.175, 0.002);
// Tempo angeglichen (rate 1.05): Steigung = rate
run("CK={samples:[]}");
for (let k=0;k<8;k++) run(`plClockSample(CK,${k*25},${5+k*0.025*1.05},1.05)`);
approx(run("plClockEstimate(CK,200,1.05)"), 5.21, 0.002);
// #181: Übergang im Takt halten. Versatz in ms: + = neuer Titel voraus, − = zurück; auf ±½ Schlag gewickelt.
ctx.gA = run("({bpm:120,markers:[{pos:0,bpm:120}]})"); ctx.gB = run("({bpm:120,markers:[{pos:0.3,bpm:120}]})");
approx(run("plXsyncError(gA,10,gB,10.3,1)"), 0, 0.001);
approx(run("plXsyncError(gA,10,gB,10.22,1)"), -80, 0.001);       // 80 ms zu spät
approx(run("plXsyncError(gA,10,gB,10.35,1)"), 50, 0.001);        // 50 ms zu früh
approx(run("plXsyncError(gA,10,gB,10.3+4*0.5+0.02,1)"), 20, 0.001); // ganze Schläge zählen nicht
approx(run("plXsyncError(gA,10,gB,10.22,1.05)"), -80/1.05, 0.001);  // Wanduhr bei angeglichenem Tempo
assert.equal(run("plXsyncError(null,10,gB,10,1)"), null);
assert.equal(run("plXsyncNudge(3)"), 0);                           // Totband
approx(run("plXsyncNudge(-20)"), 0.02, 1e-9);                      // zurück → schneller
approx(run("plXsyncNudge(30)"), -0.03, 1e-9);                      // voraus → langsamer
approx(run("plXsyncNudge(-400)"), 0.04, 1e-9);                     // begrenzt
assert.equal(run("plXsyncLearn(0,-80)"), 56);                      // nächstes Mal 56 ms vorhalten
assert.equal(run("plXsyncLearn(56,-20)"), 70);
assert.equal(run("plXsyncLearn(0,-9000)"), 500);
// Simulation: neuer Titel setzt nach dem Seek 80 ms zu spät ein; currentTime läuft in groben 10-ms-Schritten.
{
  const sim = (lock) => run(`(() => {
    const oldEl={currentTime:20,playbackRate:1}, newEl={currentTime:20.3-0.08,playbackRate:1};
    let ot=20, nt=20.3-0.08;
    const f={}; PLAYER.xfadeLog=[]; PLAYER.xfadeSeekMs=0;
    plXsyncStart(f,{gOld:gA,gNew:gB,ratio:1,lock:${lock},manualMs:0,
      info:{from:'a.mp3',to:'b.mp3',bpmOld:120,bpmNew:120,srcOld:'Serato',srcNew:'Analyse',bar:1,manualMs:0,preMs:0}});
    for (let k=0;k<200;k++) {                     // 8 s Überblenden, Takt 40 ms
      const now=10000+k*40;
      oldEl.currentTime=Math.floor(ot*100)/100; newEl.currentTime=Math.floor(nt*100)/100;
      plXsyncTick(f,oldEl,newEl,now);
      ot+=0.04*oldEl.playbackRate; nt+=0.04*newEl.playbackRate;
    }
    const e=plXsyncStop(f,newEl,'fertig');
    return {e, rate:newEl.playbackRate, pre:PLAYER.xfadeSeekMs, log:PLAYER.xfadeLog.length};
  })()`);
  const on = sim(true);
  assert(Math.abs(on.e.start_err_ms + 80) <= 12, 'Startversatz gemessen: ' + on.e.start_err_ms);
  assert(Math.abs(on.e.end_err_ms) <= 10, 'eingeregelt: ' + on.e.end_err_ms);
  assert(on.e.max_nudge_pct > 0 && on.e.max_nudge_pct <= 4);
  assert.equal(on.rate, 1, 'Korrektur am Ende zurückgenommen');
  assert(on.pre > 40 && on.pre < 70, 'gelernt: ' + on.pre);
  assert.equal(on.log, 1);
  assert.equal(on.e.trace.length >= 10, true);
  assert(on.e.settled_after_ms < 400, 'eingeschwungen nach ' + on.e.settled_after_ms + ' ms');
  const off = sim(false);                                            // nur messen
  assert(Math.abs(off.e.end_err_ms + 80) <= 12, 'ohne Nachführen bleibt der Versatz: ' + off.e.end_err_ms);
  assert.equal(off.e.max_nudge_pct, 0);
  assert.equal(off.pre, 0, 'ohne Nachführen nichts lernen');
}
// Mit gelerntem Vorhalt springt der Seek entsprechend weiter (56 ms vor).
approx(run("plXfadeCalibratedTime(gB,10.3,0-56,1,1)"), 10.356, 1e-9);
// #181: Diagnose-Metronom prüft Grid-Position, PlaybackRate und Markerwechsel.
const metro = run("plMetroBeat({bpm:120,markers:[{pos:0.3,bpm:120}]},0.3,1,1)");
approx(metro.delay,0.5); assert.equal(metro.accent,false);
const strong = run("plMetroBeat({bpm:120,markers:[{pos:0.3,bpm:120}]},7.8,1,16)");
approx(strong.delay,0.5); assert.equal(strong.accent,true);
const faster = run("plMetroBeat({bpm:120,markers:[{pos:0.3,bpm:120}]},0.3,2,1)");
approx(faster.delay,0.25);
const variable = run("plMetroBeat({bpm:120,markers:[{pos:0.5,bpm:120},{pos:32.5,bpm:128}]},32.5,1,65)");
approx(variable.delay,60/128);
assert.equal(run("plMetroBeat(null,10,1,1)"),null);
// #181: tatsächliche Rasterquelle vs. blosses BPM, fehlende Grids und Analysephase.
const statuses = [
  run("plGridStatus({grid:{bpm:124,source:'Serato',exact:true,markers:[{pos:0,bpm:124}]}}).state"),
  run("plGridStatus({grid:{bpm:120,source:'Analyse',analysed:true,markers:[{pos:0,bpm:120}]}}).state"),
  run("plGridStatus({grid:{bpm:122,source:'BPM-Tag',exact:false,markers:[{pos:0,bpm:122}]}}).state"),
  run("plGridStatus({grid:null,wave_key:'x'}).state"),
];
assert.deepEqual(Array.from(statuses), ['external','analysed','estimate','missing']);
// Eventrouting: Pfeiltasten in der normalen Oberfläche und auf Deck B.
function key(k,shift=false) {
  const event={key:k,shiftKey:shift,ctrlKey:false,metaKey:false,altKey:false,
    defaultPrevented:false,preventDefault(){this.defaultPrevented=true},
    stopPropagation(){}};
  ctx.event=event;
  run("plKeydown(event)");
  return event.defaultPrevented;
}
run("PLAYER.audio.currentTime=10");assert(key('ArrowRight'));
approx(run("PLAYER.audio.currentTime"),12);
assert(key('ArrowLeft'));approx(run("PLAYER.audio.currentTime"),10);
assert(key('ArrowRight',true));approx(run("PLAYER.audio.currentTime"),22);
run("PLAYER.audio.currentTime=10");
// Fokussierte Trackliste behält Pfeiltasten für Stems/Navigation.
ctx.document.activeElement={tagName:'DIV',closest:()=>({})};
assert.equal(key('ArrowRight'),false);
approx(run("PLAYER.audio.currentTime"),10);
ctx.document.activeElement={tagName:'BODY',closest:()=>null};
run("PL2.layout='top'; PL2.deck2=true; PLAYER.target='B'; DECKB.audio={src:'fileB',currentTime:10,duration:80,paused:true}; DECKB.info={bpm:120,grid:{bpm:120,markers:[{pos:0,bpm:120}]},cues:[{pos:3,kind:'cue'},{pos:21,kind:'cue'}]};");
assert(key('ArrowRight'));approx(run("DECKB.audio.currentTime"),12);
assert(key('ArrowRight',true));approx(run("DECKB.audio.currentTime"),21);

// #181: Simulierter Load/Play-Aufschub verschiebt die Zeit von Deck A.
// Phase erst NACH Play auf dem aktuellen Stand von Deck A ermitteln.
(async()=>{
  run("PLAYER.target='A'; S.module='djset'; PLAYER.xfade=2; PLAYER.xfadePhase=true; PLAYER.xfadeSync=true; PLAYER.vol=0.8; PLAYER.xfadeStart='start'; PLAYER.xfadeReturn=0; PLAYER.info={bpm:120,grid:{bpm:120,markers:[{pos:0,bpm:120}]}};");
  ctx.djSelectTag=()=>{};
  run("plWaveNeeded=()=>false;");
  const older = {src:'old', currentTime:10, playbackRate:1, volume:0.8,
    paused:false,pause(){this.paused=true},removeAttribute(){},load(){}};
  const newer = {src:'', currentTime:0, playbackRate:1, volume:0.8,
    paused:true,async play(){older.currentTime=10.75;this.paused=false},
    pause(){this.paused=true},removeAttribute(){},load(){}};
  ctx.older=older;ctx.newer=newer;
  run("PLAYER.audio=older; PLAYER.spare=newer; PLAYER.fade=null;");
  run("plLoad=async function(){ PLAYER.info={bpm:120,grid:{bpm:120,markers:[{pos:0.3,bpm:120}]}}; newer.src='new'; }");
  // Noch während des Ladens: A ist aktiv auf altem Grid. Die spätere
  // Crossfade-Vorschau darf nicht schon das neue Raster verwenden.
  run("PL_METRO.deck='A';PL_METRO.ctx=fakeCtx;PL_METRO.volume=0");
  await run("plCrossfade(1)");
  approx(run("gridPhase(gridOf(PLAYER.info),newer.currentTime)"),run("gridPhase({bpm:120,markers:[{pos:0,bpm:120}]},older.currentTime)"));
  assert.equal(newer.volume,0,'Fade must start silent');
  assert.equal(run("PLAYER.fade.oldInfo !== PLAYER.info"),true);
  assert.equal(run("plMetroSource('A').audio === older"),true);
  assert.equal(run("plMetroSource('A').info === PLAYER.fade.oldInfo"),true);
  assert.equal(run("plMetroSource('B').audio === DECKB.audio"),true);
  run("older.readyState=4;newer.readyState=4;plMetroTick()");
  assert.equal(run("PL_METRO.audio === older"),true,'During 30s fade use old audio');
  assert.equal(run("PL_METRO.deck"),'A');
  // Das Crossfade-Finish übernimmt NACH dem Stoppen des alten Decks.
  run("plFadeStop()");
  assert.equal(run("PL_METRO.deck"),'A','Metronome remains enabled');
  assert.equal(run("PL_METRO.audio === newer"),true,'New audio only after fade end');
  assert.equal(run("PL_METRO.info === PLAYER.info"),true);
  // Fehlendes Beatgrid beim Folgetrack: Metronom soll nicht abgeschaltet werden.
  run("PLAYER.info={grid:null,bpm:0};plMetroTick()");
  assert.equal(run("PL_METRO.deck"),'A');
  assert.equal(run("PL_METRO.ctx !== null"),true);
  run("PLAYER.info={grid:{bpm:120,markers:[{pos:0.3,bpm:120}]}};plMetroTick()");
  assert.equal(run("PL_METRO.audio === newer"),true);
  assert.equal(run("PL_METRO.info === PLAYER.info"),true);
  run("PL_METRO.ctx=null;PL_METRO.deck=null;PL_METRO.audio=null");
  console.log('player 4.4.1 JS regression checks passed');
})().catch((e)=>{console.error(e);process.exitCode=1});
"""


@unittest.skipUnless(NODE, "Node.js nicht installiert")
class TestPlayerJavaScript(unittest.TestCase):
    def test_browser_player_logic_without_browser(self):
        result = subprocess.run(
            [NODE, "-e", CHECK], cwd=ROOT, capture_output=True,
            text=True, encoding="utf-8", timeout=120,                       # Windows-Runner sind gelegentlich langsam
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)


if __name__ == "__main__":
    unittest.main()
