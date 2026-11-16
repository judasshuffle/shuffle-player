/* Client entity script. Cinema handshake, independent Shufflizer volume.
 * Attach to the Web entity whose sourceUrl is http://shuffle.tplinkdns.com:8001/dr-screen.
 */
(function () {
    var VOLUME_SETTING = 'darkride/shufflizer/sound';
    var CHANNEL = 'darkride.shufflizer';
    var entityID = null;
    var timer = null;
    var ready = false;
    var lastVolume = null;
    var MUSIC_LOCAL = 'darkride.shufflizer.music.v1';
    var MUSIC_SHARED = 'darkride.shufflizer.music.shared.v1';
    var PUBLISHER_SETTING = 'darkride/shufflizer/musicPublisherEntity';
    var lastMusic = -1, lastShared = -1, musicSession = '', musicSequence = -1;
    function bytes(raw) { return encodeURIComponent(raw).replace(/%[0-9A-F]{2}|./g, 'x').length; }
    function validFeatures(f) {
        if (!f || typeof f !== 'object' || Array.isArray(f)) return false;
        var bounds={rms:[0,4],peak:[0,4],db:[-120,20],energy:[0,1],bass:[0,1],mid:[0,1],treble:[0,1],
            centroid:[0,24000],brightness:[0,1],rolloff:[0,24000],flatness:[0,1],flux:[0,10000],onset:[0,1],
            beatId:[0,1e12],tempoConfidence:[0,1],pitchConfidence:[0,1],trend:[-1,1],crest:[0,20],zcr:[0,1]};
        var key, n;
        for(key in bounds) {
            n=f[key];
            if(typeof n!=='number'||!isFinite(n)||n<bounds[key][0]||n>bounds[key][1])return false;
        }
        var optional={beatTime:[0,1e12],bpm:[70,180],beatPhase:[0,1],pitchHz:[60,1100],dominantHz:[0,24000]};
        for(key in optional) {
            n=f[key];
            if(n!==null&&(typeof n!=='number'||!isFinite(n)||n<optional[key][0]||n>optional[key][1]))return false;
        }
        if(typeof f.beat!=='boolean'||typeof f.silent!=='boolean'||f.beatId%1!==0)return false;
        var arrays={bands:8,chroma:12};
        for(key in arrays) {
            var a=f[key];
            if(!Array.isArray(a)||a.length!==arrays[key])return false;
            for(var i=0;i<a.length;i++)if(typeof a[i]!=='number'||!isFinite(a[i])||a[i]<0||a[i]>1)return false;
        }
        if(f.stereo!==null) {
            var s=f.stereo, sb={left:[0,4],right:[0,4],balance:[-1,1],width:[0,1]};
            if(!s||typeof s!=='object'||Array.isArray(s))return false;
            for(key in sb)if(typeof s[key]!=='number'||!isFinite(s[key])||s[key]<sb[key][0]||s[key]>sb[key][1])return false;
            if(s.correlation!==null&&(typeof s.correlation!=='number'||!isFinite(s.correlation)||Math.abs(s.correlation)>1))return false;
            for(key in s)if(!Object.prototype.hasOwnProperty.call(sb,key)&&key!=='correlation')return false;
        }
        // Reject unknown fields rather than transporting arbitrary Web data.
        for(key in f)if(!Object.prototype.hasOwnProperty.call(bounds,key)&&
            !Object.prototype.hasOwnProperty.call(optional,key)&&key!=='beat'&&key!=='silent'&&key!=='bands'&&key!=='chroma'&&key!=='stereo')return false;
        return true;
    }
    function relayMusic(message) {
        var now=Date.now();
        if(lastMusic>=0&&now-lastMusic<45)return;
        if(message.v!==1||typeof message.session!=='string'||message.session.length>64||!message.session||
            typeof message.epoch!=='number'||message.epoch<0||message.epoch%1!==0||
            typeof message.seq!=='number'||message.seq<0||message.seq%1!==0||
            typeof message.t!=='number'||!isFinite(message.t)||message.t<0||
            typeof message.wall!=='number'||!isFinite(message.wall)||
            ['playing','paused','buffering','suspended'].indexOf(message.state)<0||
            typeof message.stationTrackId!=='string'||message.stationTrackId.length>64||!validFeatures(message.f))return;
        if(message.session===musicSession&&message.seq<=musicSequence)return;
        var packet={type:'shufflizer.music',v:1,session:message.session,epoch:message.epoch,seq:message.seq,
            t:message.t,wall:message.wall,state:message.state,stationTrackId:message.stationTrackId,f:message.f,
            sourceEntity:String(entityID),sourceSession:String(MyAvatar.sessionUUID)};
        var raw=JSON.stringify(packet);
        if(bytes(raw)>1200)return;
        lastMusic=now; musicSession=message.session; musicSequence=message.seq;
        // Always local first. No visitor is a shared lighting controller by default.
        Messages.sendLocalMessage(MUSIC_LOCAL,raw);
        if(String(Settings.getValue(PUBLISHER_SETTING,''))===String(entityID)&&
            (lastShared<0||now-lastShared>=100)) {
            Messages.sendMessage(MUSIC_SHARED,raw); lastShared=now;
        }
    }
    function sendVolume() {
        if (!ready) { return; }
        var volume = Number(Settings.getValue(VOLUME_SETTING, 100));
        if (!isFinite(volume)) { volume = 100; }
        volume = Math.max(0, Math.min(100, volume));
        if (volume === lastVolume) { return; }
        Entities.emitScriptEvent(entityID, JSON.stringify({volume: volume}));
        lastVolume = volume;
    }
    function onWebEvent(id, raw) {
        if (id !== entityID) { return; }
        if(typeof raw!=='string'||raw.length>4096)return;
        var message;
        try { message = JSON.parse(raw); } catch (error) { return; }
        if(message&&message.type==='shufflizer.music') { relayMusic(message); return; }
        if (message && typeof message.sound === 'number' && isFinite(message.sound)) {
            Settings.setValue(VOLUME_SETTING, Math.max(0, Math.min(100, message.sound)));
            lastVolume = null;
            sendVolume();
            return;
        }
        if (!message || (!message.hello && !message.ready)) { return; }
        ready = true;
        lastVolume = null;
        sendVolume();
    }
    function onMessage(channel, raw, sender, localOnly) {
        if (channel !== CHANNEL || !localOnly || sender !== MyAvatar.sessionUUID) { return; }
        var message;
        try { message = JSON.parse(raw); } catch (error) { return; }
        if (!message || typeof message.sound !== 'number' || !isFinite(message.sound)) { return; }
        Settings.setValue(VOLUME_SETTING, Math.max(0, Math.min(100, message.sound)));
        sendVolume();
    }
    this.preload = function (id) {
        entityID = id;
        lastMusic=-1; lastShared=-1; musicSession=''; musicSequence=-1;
        Entities.webEventReceived.connect(onWebEvent);
        Messages.subscribe(CHANNEL);
        Messages.messageReceived.connect(onMessage);
        timer = Script.setInterval(sendVolume, 500);
    };
    this.unload = function () {
        Entities.webEventReceived.disconnect(onWebEvent);
        Messages.messageReceived.disconnect(onMessage);
        Messages.unsubscribe(CHANNEL);
        if (timer !== null) { Script.clearInterval(timer); }
        ready = false;
        entityID = null;
    };
})
