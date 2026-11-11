const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto');
// Load the same pure JS code used by DarkRide, without Node's crypto fast path.
const library={module:{exports:{}}}; vm.runInNewContext(fs.readFileSync('synology/sha256.js','utf8'),library);
const sha256=library.module.exports;
for(const value of ['', 'Bob Dylan — 70s', 'a'.repeat(10000)]) {
  assert.equal(sha256(value),crypto.createHash('sha256').update(value).digest('hex'));
  assert.equal(sha256.hmac('a'.repeat(64),value),crypto.createHmac('sha256','a'.repeat(64)).update(value).digest('hex'));
}
function exercise(owner) {
  let receive,screen,end,requestCount=0;
  const outgoing=[],requests=[],settings=new Map(owner?[['darkride/shufflizer/owner-key','a'.repeat(64)]]:[]),local=[];
  const signal=setter=>({connect:setter,disconnect(){}});
  const button={clicked:signal(()=>{}),editProperties(){}};
  const tablet={addButton(){return button;},removeButton(){},gotoHomeScreen(){},screenChanged:signal(f=>screen=f),webEventReceived:signal(f=>receive=f),emitScriptEvent(raw){outgoing.push(JSON.parse(raw));}};
  function XHR(){this.headers={};this.open=(method,url)=>{this.method=method;this.url=url;};this.setRequestHeader=(k,v)=>{this.headers[k]=v;};this.send=body=>{
    requests.push({method:this.method,url:this.url,headers:this.headers,body});
    this.status=200;this.readyState=4;this.responseText=this.method==='GET'?JSON.stringify({epoch:'test-epoch'}):JSON.stringify({can_control:true,queue_count:2});
    this.onreadystatechange();
  };}
  vm.runInNewContext(fs.readFileSync('synology/dr-dj.js','utf8'),{
    Script:{require(){return sha256;},resolvePath(p){return owner?'file:///private/'+p:'http://shuffle.tplinkdns.com:8001/'+p;},scriptEnding:signal(f=>end=f)},
    Settings:{getValue(k,d){return settings.has(k)?settings.get(k):d;},setValue(k,v){settings.set(k,v);}},
    Tablet:{getTablet(){return tablet;}},Messages:{sendLocalMessage(...m){local.push(m);}},
    XMLHttpRequest:XHR,Uuid:{generate(){return '01234567-89ab-cdef-0123-456789abcdef';}}
  });
  const send=m=>receive(JSON.stringify({app:'shufflizer-remote',...m}));
  screen('Web','https://unrelated.test/'); send({command:'next',request:1}); assert.equal(requests.length,0);
  screen('Web',owner?'file:///private/dr-remote.html':'http://shuffle.tplinkdns.com:8001/dr-remote');
  send({hello:true});assert.equal(outgoing.at(-1).owner,owner);
  send({sound:35});assert.equal(settings.get('darkride/shufflizer/sound'),35);assert.equal(JSON.parse(local[0][1]).sound,35);
  send({command:'play',query:'play 70s Bob Dylan',request:2});
  if(owner){
    assert.equal(requests.length,2);
    const req=requests[1],path='/api/dj',headers=req.headers;
    const canonical=['POST',path,headers['X-Shuffle-Epoch'],headers['X-Shuffle-Time'],headers['X-Shuffle-Nonce'],crypto.createHash('sha256').update(req.body).digest('hex')].join('\n');
    assert.equal(headers['X-Shuffle-Signature'],crypto.createHmac('sha256','a'.repeat(64)).update(canonical).digest('hex'));
    assert.equal(JSON.parse(req.body).action,'play');assert.equal(JSON.parse(req.body).query,'play 70s Bob Dylan');
  }else{assert.equal(requests.length,0);assert.match(outgoing.at(-1).error,/Owner pairing/);}
  assert(!JSON.stringify(outgoing).includes('a'.repeat(64)),'Key never sent to the web page');
  end();
}
exercise(false);exercise(true);
console.log('Owner signing, native remote, visitor isolation and personal volume passed');
