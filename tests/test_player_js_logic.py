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
  document: {activeElement: {tagName:'BODY', closest:()=>null}},
  window: {}, navigator: {}, toast:()=>{},
  S: {module:'tagger'}, TG: {order:[], anchor:0},
  $:()=>({hidden:true})
});
for (const name of ['player.js', 'player2.js', 'metronome.js']) {
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
  await run("plCrossfade(1)");
  approx(run("gridPhase(gridOf(PLAYER.info),newer.currentTime)"),run("gridPhase({bpm:120,markers:[{pos:0,bpm:120}]},older.currentTime)"));
  assert.equal(newer.volume,0,'Fade must start silent');
  run("clearInterval(PLAYER.fade.timer); PLAYER.fade=null;");
  console.log('player 4.4.1 JS regression checks passed');
})().catch((e)=>{console.error(e);process.exitCode=1});
"""


@unittest.skipUnless(NODE, "Node.js nicht installiert")
class TestPlayerJavaScript(unittest.TestCase):
    def test_browser_player_logic_without_browser(self):
        result = subprocess.run(
            [NODE, "-e", CHECK], cwd=ROOT, capture_output=True,
            text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)


if __name__ == "__main__":
    unittest.main()
