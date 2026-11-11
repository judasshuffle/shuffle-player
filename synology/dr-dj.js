/* Run as an Interface script, not an entity script. Public file contains no key.
 * Your private installer pairs the owner key in local Settings. Everyone else
 * gets personal volume only. Synology independently verifies every DJ command.
 */
(function () {
    'use strict';
    var BASE = 'http://shuffle.tplinkdns.com:8001';
    var LOCAL = /^(?:file:|[A-Za-z]:[\\/])/.test(Script.resolvePath('dr-dj.js'));
    var PAGE = LOCAL ? Script.resolvePath('dr-remote.html') : BASE + '/dr-remote';
    var KEY_SETTING = 'darkride/shufflizer/owner-key';
    var VOLUME_SETTING = 'darkride/shufflizer/sound';
    var sha256 = Script.require(Script.resolvePath('sha256.js'));
    var tablet = Tablet.getTablet('com.highfidelity.interface.tablet.system');
    var button = tablet.addButton({text: 'SHUFFLIZER'});
    var active = false, busy = false, epoch = '', closed = false;
    function volume() {
        var value = Number(Settings.getValue(VOLUME_SETTING, 100));
        return isFinite(value) ? Math.max(0,Math.min(100,value)) : 100;
    }
    function key() { return String(Settings.getValue(KEY_SETTING, '')); }
    function owner() { return LOCAL && /^[0-9a-f]{64}$/.test(key()); }
    function send(message) {
        if (!active || closed) return;
        message.app = 'shufflizer-remote'; tablet.emitScriptEvent(JSON.stringify(message));
    }
    function http(method, path, data, signed, callback) {
        var xhr = new XMLHttpRequest(), body = data ? JSON.stringify(data) : '';
        xhr.open(method, BASE + path);
        xhr.timeout = 90000;
        if (body) xhr.setRequestHeader('Content-Type','application/json');
        if (signed) {
            var stamp=String(Math.floor(Date.now()/1000)), nonce=String(Uuid.generate());
            var message=[method,path,epoch,stamp,nonce,sha256(body)].join('\n');
            xhr.setRequestHeader('X-Shuffle-Epoch',epoch);
            xhr.setRequestHeader('X-Shuffle-Time',stamp);
            xhr.setRequestHeader('X-Shuffle-Nonce',nonce);
            xhr.setRequestHeader('X-Shuffle-Signature',sha256.hmac(key(),message));
        }
        var done=false;
        function finish(error,result) { if(done)return;done=true;callback(error,result); }
        xhr.onreadystatechange=function(){
            if(xhr.readyState!==4)return;
            if(xhr.status!==200) return finish('DJ request rejected ('+xhr.status+'). Check your owner pairing and clock.');
            try { finish(null,JSON.parse(xhr.responseText)); } catch(e) { finish('Invalid server response.'); }
        };
        xhr.onerror=function(){finish('Station unreachable.');};
        xhr.ontimeout=function(){finish('Station request timed out.');};
        xhr.send(body || null);
    }
    function onEvent(raw) {
        if (!active || closed) return;
        var m;try {m=JSON.parse(raw);}catch(e){return;}
        if(!m || m.app!=='shufflizer-remote')return;
        if(m.hello || m.ready) {send({init:true,owner:owner(),volume:volume()});return;}
        if(typeof m.sound==='number' && isFinite(m.sound)) {
            var value=Math.max(0,Math.min(100,m.sound));Settings.setValue(VOLUME_SETTING,value);
            Messages.sendLocalMessage('darkride.shufflizer',JSON.stringify({sound:value}));return;
        }
        if(['state','search','play','append','shuffle','next'].indexOf(m.command)<0)return;
        if(!owner()) {send({request:m.request,error:'Owner pairing required. Run your private local installer.'});return;}
        if(busy) {send({request:m.request,error:'A DJ request is already in progress.'});return;}
        busy=true;
        var payload={action:m.command,query:typeof m.query==='string'?m.query:'',offset:m.offset || 0};
        http('GET','/api/owner-challenge',null,false,function(error,challenge){
            if(error){busy=false;send({request:m.request,error:error});return;}
            epoch=challenge.epoch;
            http('POST','/api/dj',payload,true,function(error,result){busy=false;send({request:m.request,query:payload.query,error:error,result:result});});
        });
    }
    function onScreen(type,url) {active=type==='Web' && url===PAGE;button.editProperties({isActive:active});}
    function toggle() {if(active)tablet.gotoHomeScreen();else tablet.gotoWebScreen(PAGE);}
    tablet.screenChanged.connect(onScreen);
    tablet.webEventReceived.connect(onEvent);
    button.clicked.connect(toggle);
    Script.scriptEnding.connect(function(){
        closed=true;tablet.webEventReceived.disconnect(onEvent);tablet.screenChanged.disconnect(onScreen);
        button.clicked.disconnect(toggle);tablet.removeButton(button);if(active)tablet.gotoHomeScreen();
    });
})();
