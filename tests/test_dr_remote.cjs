const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function exercise(owner) {
  const ids=['volume','volumeValue','query','search','results','more','play','append','shuffle','next','dj','status','interpretation','nowPlaying'];
  const elements=Object.fromEntries(ids.map(id=>[id,{value:'',hidden:false,disabled:false,children:[],append(x){this.children.push(x);},replaceChildren(){this.children=[];}}]));
  let tick,receive;const sent=[];
  vm.runInNewContext(fs.readFileSync('synology/dr-remote.js','utf8'),{
    document:{getElementById:id=>elements[id],createElement:()=>({})},
    window:{EventBridge:{scriptEventReceived:{connect(f){receive=f;}},emitWebEvent(raw){sent.push(JSON.parse(raw));}}},
    setInterval(f){tick=f;return 1;},clearInterval(){}
  });
  tick();assert(sent.some(m=>m.hello));assert(sent.some(m=>m.ready));
  const respond=m=>receive(JSON.stringify({app:'shufflizer-remote',...m}));
  respond({init:true,owner,volume:80});
  assert.equal(elements.dj.hidden,!owner);
  elements.volume.value='45';elements.volume.oninput();assert.equal(sent.at(-1).sound,45);
  if(!owner){elements.next.onclick();assert.equal(sent.at(-1).sound,45);return;}
  let command=sent.findLast(m=>m.command);assert.equal(command.command,'state');
  respond({request:command.request,result:{current:{artist:'A',title:'B'},queue_count:2}});
  elements.query.value='play 70s Bob Dylan';elements.search.onsubmit({preventDefault(){}});
  command=sent.at(-1);assert.equal(command.command,'search');
  respond({request:command.request,result:{tracks:[{artist:'Bob Dylan',title:'Hurricane',available:true}],has_more:false},query:command.query});
  assert.equal(elements.play.disabled,false);assert.equal(elements.append.disabled,false);
  elements.play.onclick();command=sent.at(-1);assert.equal(command.command,'play');assert.equal(command.query,'play 70s Bob Dylan');
  respond({request:command.request,result:{queue_count:1}});
  elements.append.onclick();command=sent.at(-1);assert.equal(command.command,'append');
  respond({request:command.request,result:{queue_count:2}});
  elements.query.value='a different search';elements.query.oninput();assert.equal(elements.play.disabled,true);
  elements.shuffle.onclick();command=sent.at(-1);assert.equal(command.command,'shuffle');
  respond({request:command.request,error:'Rejected'});assert.equal(elements.status.textContent,'Rejected');
  elements.next.onclick();assert.equal(sent.at(-1).command,'next');
}
exercise(false);exercise(true);console.log('Remote UI search review, play/append, shuffle/next and visitor volume passed');
