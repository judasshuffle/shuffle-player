/* Run ONCE in the broadcasting viewer in cromptonmoor. Never on each visitor. */
(function () {
    'use strict';
    var BASE = 'http://127.0.0.1:18791';
    var place = String(location.placename || location.hostname).toLowerCase();
    if (place !== 'cromptonmoor' && place !== '6ad726af-0095-1000-8000-3b449dbf752a') {
        print('SHUFFLE: Enter cromptonmoor by place name before loading this script.');
        Script.stop(); return;
    }
    var originalDomain = location.hostname;
    var speaker, label, injector = null, enabled = false, volume = 0.25;
    var queue = [], session = '', lastID = 0, busy = false, ended = false;
    var nextPlayAt = 0, generation = 0, request = null, lastPoll = 0;
    var pos = Vec3.sum(MyAvatar.position,
        Vec3.multiply(3, Quat.getForward(MyAvatar.orientation)));
    speaker = Entities.addEntity({type: 'Box', name: 'ROBOTDOLLY Shuffle LIVE test',
        position: pos, dimensions: {x: 0.5, y: 0.8, z: 0.4},
        color: {red: 40, green: 80, blue: 160}, collisionless: true,
        lifetime: 3600, userData: JSON.stringify({experiment: 'shuffle-phase1'})}, 'domain');
    if (!speaker || speaker === '{00000000-0000-0000-0000-000000000000}') {
        print('SHUFFLE: Cannot rez domain entity; stopping.'); Script.stop(); return;
    }
    label = Entities.addEntity({type: 'Text', name: 'Shuffle LIVE controls',
        position: Vec3.sum(pos, {x: 0, y: 0.8, z: 0}),
        dimensions: {x: 2.5, y: 0.5, z: 0.01}, lineHeight: 0.11,
        text: 'Shuffle LIVE (off)\nBroadcaster: click box; +/- volume',
        billboardMode: 'full', collisionless: true, lifetime: 3600}, 'domain');
    print('SHUFFLE: speaker=' + speaker + ' position=' + JSON.stringify(pos));

    function updateLabel() {
        Entities.editEntity(label, {text: 'Shuffle LIVE ' + (enabled ? 'ON' : 'OFF') +
            ' volume ' + Math.round(volume * 100) + '%\nBroadcaster: click box; +/- volume'});
    }
    function stopAudio() {
        generation++;
        queue = []; lastID = 0; nextPlayAt = 0;
        var old = injector; injector = null;
        if (old) { old.stop(); }
    }
    function playNext() {
        if (!enabled || ended || !queue.length || Date.now() < nextPlayAt) { return; }
        var item = queue[0];
        if (!item.sound.downloaded) { return; }
        queue.shift();
        var properties = Entities.getEntityProperties(speaker, ['position']);
        if (!properties.position) { Script.stop(); return; }
        var old = injector;
        injector = Audio.playSound(item.sound, {position: properties.position,
            volume: volume, localOnly: false, loop: false});
        if (!injector) { print('SHUFFLE: injector failed'); return; }
        var now = Date.now();
        print('SHUFFLE: play ' + item.id + ' at=' + Date.now() +
            ' lateMs=' + (nextPlayAt ? now - nextPlayAt : 0));
        // Do not create another injector inside a native finished signal callback.
        // Keep a bounded wall-clock schedule; restart at the live edge after stalls.
        nextPlayAt = nextPlayAt && now - nextPlayAt < 250 ? nextPlayAt + 2000 : now + 2000;
        if (old) { old.stop(); }
    }
    function poll() {
        if (!enabled || ended || busy) { return; }
        busy = true;
        var stamp = generation;
        request = new XMLHttpRequest();
        var xhr = request;
        xhr.open('GET', BASE + '/manifest.json?t=' + Date.now());
        xhr.timeout = 2000;
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== 4) { return; }
            busy = false;
            if (ended || !enabled || stamp !== generation || xhr.status !== 200) { return; }
            try {
                var m = JSON.parse(xhr.responseText);
                if (m.age > 5 || !m.ids.length) { stopAudio(); return; }
                if (session !== m.session) { stopAudio(); session = m.session; }
                var newest = m.ids[m.ids.length - 1];
                if (!lastID || newest - lastID > 3 || queue.length > 4) {
                    stopAudio(); lastID = Math.max(0, newest - 2);
                }
                m.ids.forEach(function (id) {
                    if (id > lastID) {
                        queue.push({id: id, sound: SoundCache.getSound(BASE + '/chunk/' + session + '/' + id + '.wav')});
                        lastID = id;
                    }
                });
                playNext();
            } catch (e) { print('SHUFFLE: ' + e); }
        };
        xhr.onerror = xhr.ontimeout = function () { busy = false; };
        xhr.send();
    }
    function click(id, event) {
        if (id !== speaker || !event.isLeftButton) { return; }
        enabled = !enabled; stopAudio(); updateLabel(); poll();
    }
    function key(event) {
        if (event.text !== '+' && event.text !== '-' && event.text !== '=') { return; }
        volume = Math.max(0, Math.min(1, volume + (event.text === '-' ? -0.05 : 0.05)));
        if (injector) { injector.setOptions({volume: volume, localOnly: false, loop: false,
            position: Entities.getEntityProperties(speaker, ['position']).position}); }
        updateLabel();
    }
    var timer = Script.setInterval(function () {
        if (location.hostname !== originalDomain) { Script.stop(); return; }
        if (Date.now() - lastPoll >= 250) { lastPoll = Date.now(); poll(); }
        playNext();
    }, 10);
    Entities.clickDownOnEntity.connect(click);
    Controller.keyPressEvent.connect(key);
    Script.scriptEnding.connect(function () {
        ended = true; enabled = false; Script.clearInterval(timer); stopAudio();
        if (request) { request.abort(); }
        Entities.clickDownOnEntity.disconnect(click); Controller.keyPressEvent.disconnect(key);
        Entities.deleteEntity(speaker); Entities.deleteEntity(label);
    });
}());
