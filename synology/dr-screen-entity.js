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
        var message;
        try { message = JSON.parse(raw); } catch (error) { return; }
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
