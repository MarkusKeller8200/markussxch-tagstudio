"""#192: Native Browser-Tooltips dürfen nicht gegen das TagStudio-Design antreten."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")

JS = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('node:assert/strict');
const listeners = {};
const winlisteners = {};
const observers = [];
class Node {
  constructor(tag='div', attrs={}) {
    this.nodeType=1; this.tagName=tag.toUpperCase();
    this.attrs=new Map(Object.entries(attrs));
    this.dataset={}; this.children=[]; this.parentNode=null;
    this.isConnected=true; this.hidden=false; this.className='';
    this.style={}; this.textContent=''; this.innerHTML='';
    this.offsetWidth=160; this.offsetHeight=40;
  }
  setAttribute(k,v){this.attrs.set(k,String(v))}
  getAttribute(k){return this.attrs.has(k)?this.attrs.get(k):null}
  hasAttribute(k){return this.attrs.has(k)}
  removeAttribute(k){this.attrs.delete(k)}
  matches(s){return s==='button' && this.tagName==='BUTTON'}
  appendChild(c){this.children.push(c);c.parentNode=this;return c}
  querySelectorAll(sel){
    const nodes=[];
    for(const c of this.children){
      if(sel==='[title]'&&c.hasAttribute('title'))nodes.push(c);
      nodes.push(...c.querySelectorAll(sel));
    }
    return nodes;
  }
  contains(n){for(;n;n=n.parentNode)if(n===this)return true;return false}
  closest(q){let n=this;for(;n;n=n.parentNode){
    if(q.includes('[data-tip-title]')&&(n.dataset.tipTitle!==undefined||n.dataset.tipHtml!==undefined||n.hasAttribute('title')))return n;
  }return null}
  getBoundingClientRect(){return{left:40,top:30,width:25,height:20,bottom:50}}
}
const body=new Node('body');
const skip=body.appendChild(new Node('button',{title:'Voriger Titel'}));
const cue=body.appendChild(new Node('button',{title:'Voriger Cue (Shift+←)'}));
const metro=body.appendChild(new Node('button',{title:'Beatgrid-Metronom A'}));
const update=body.appendChild(new Node('button',{title:'Pause (Leertaste)'}));
const rich=body.appendChild(new Node('span'));rich.dataset.tipHtml='<b>Info</b>';
const doc={
  body,createElement:(tag)=>new Node(tag),
  addEventListener:(k,v)=>{listeners[k]=v},
};
const win={addEventListener:(k,v)=>{winlisteners[k]=v}};
class Observer {
  constructor(fn){this.callback=fn;observers.push(this)}
  observe(root,opts){this.opts=opts;this.root=root}
}
const ctx=vm.createContext({document:doc,window:win,MutationObserver:Observer,
  innerWidth:900,innerHeight:650,setTimeout,clearTimeout,
  esc:(v)=>String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
});
vm.runInContext(fs.readFileSync('web/tooltips.js','utf8'),ctx,{filename:'tooltips.js'});
function run(code){return vm.runInContext(code,ctx)}
ctx.skip=skip;ctx.cue=cue;ctx.metro=metro;ctx.update=update;ctx.rich=rich;
run('initTips()');
assert.equal(observers.length,1);
assert.equal(observers[0].opts.attributeFilter[0],'title');
for(const item of [skip,cue,metro,update]){
  assert.equal(item.hasAttribute('title'),false,'Native title must be removed');
  assert(item.dataset.tipTitle,'TagStudio tooltip should be retained');
  assert(item.hasAttribute('aria-label'),'Icon buttons keep accessibility labels');
}
run('initTips()');assert.equal(observers.length,1,'init is idempotent');
listeners.mouseover({target:cue});
assert.equal(run('TIP.target === cue'),true);
run('tipShow(cue)');
assert(run('TIP.el.innerHTML').includes('Voriger Cue'));
assert.equal(run('TIP.el.hidden'),false);
assert(run('TIP.el.className')==='tip');

// Tooltips are kept fresh even if source writes element.title after hover.
metro.setAttribute('title','Metronom: 80 %');
observers[0].callback([{type:'attributes',target:metro}]);
assert.equal(metro.hasAttribute('title'),false);
assert.equal(metro.dataset.tipTitle,'Metronom: 80 %');
listeners.mouseover({target:metro});run('tipShow(metro)');
assert(run('TIP.el.innerHTML').includes('80 %'));
metro.setAttribute('title','Metronom: 100 %');
observers[0].callback([{type:'attributes',target:metro}]);
assert(run('TIP.el.innerHTML').includes('100 %'),'active tooltip must update');
assert.equal(metro.hasAttribute('title'),false);

// Newly added Cue markers and other dynamically generated nodes also normalize.
const marker=body.appendChild(new Node('button',{title:'Cue 3 · 1:24'}));
observers[0].callback([{type:'childList',addedNodes:[marker]}]);
assert.equal(marker.dataset.tipTitle,'Cue 3 · 1:24');
assert.equal(marker.hasAttribute('title'),false);
listeners.focusin({target:marker});
assert.equal(run('TIP.target.isConnected'),true);
assert.equal(run('TIP.target===cue'),false);
assert.equal(run('TIP.target===metro'),false);
// rich tooltips keep HTML rendering.
ctx.marker=marker;
run('tipActivate(rich);tipShow(rich)');
assert.equal(run('TIP.el.innerHTML'),'<b>Info</b>');
listeners.mouseout({target:rich,relatedTarget:null});
assert.equal(run('TIP.el.hidden'),true);
run('tipHide()');
console.log('shared TagStudio tooltips: OK');
"""


class TestTooltipFiles(unittest.TestCase):
    def test_loaded_in_both_windows(self):
        main = (ROOT / "web/index.html").read_text(encoding="utf-8")
        detached = (ROOT / "web/player-window.html").read_text(encoding="utf-8")
        app = (ROOT / "web/app.js").read_text(encoding="utf-8")
        player = (ROOT / "web/playerwin.js").read_text(encoding="utf-8")
        for html in (main, detached):
            self.assertIn('<script src="tooltips.js"></script>', html)
        self.assertIn("initTips();", app)
        self.assertIn("initTips();", player)
        self.assertNotIn("const TIP = ", app)

    @unittest.skipUnless(NODE, "Node.js is required for tooltip regression test")
    def test_native_titles_are_replaced_and_dynamic_updates_work(self):
        result = subprocess.run(
            [NODE, "-e", JS], cwd=ROOT, encoding="utf-8",
            capture_output=True, text=True, timeout=25,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)


if __name__ == "__main__":
    unittest.main()
