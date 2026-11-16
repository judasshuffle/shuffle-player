/* Browser adapter: the existing MP3 source, before visitor volume. Opt-out:
 * localStorage['shufflizer.music.enabled']='false', then reload the screen.
 */
(function (root) {
    'use strict';
    root.ShufflizerMusic = {
        attach: function (options) {
            if (root.ShufflizerMusic.stop) return;
            try { if (root.localStorage.getItem('shufflizer.music.enabled') === 'false') return; } catch (_) {}
            if (!root.ShufflizerMusicFeatures) return;
            var context=options.context, player=options.player, analyser=context.createAnalyser();
            analyser.fftSize=4096; analyser.smoothingTimeConstant=0;
            // AnalyserNode can analyse with its output unconnected. This is not
            // a second speaker path, source element or network stream.
            options.source.connect(analyser);
            var features=new root.ShufflizerMusicFeatures(context.sampleRate,analyser.fftSize);
            var wave=new Float32Array(analyser.fftSize), bins=new Float32Array(analyser.frequencyBinCount);
            var stereoInput=null, splitter=null, left=null, right=null, leftWave=null, rightWave=null;
            try {
                if(context.createChannelSplitter && root.localStorage.getItem('shufflizer.music.stereo')!=='false') {
                    // Speakers-mode explicit stereo duplicates mono appropriately
                    // before splitting, rather than mistaking mono for hard-left.
                    stereoInput=context.createGain(); stereoInput.channelCount=2;
                    stereoInput.channelCountMode='explicit'; stereoInput.channelInterpretation='speakers';
                    splitter=context.createChannelSplitter(2); left=context.createAnalyser(); right=context.createAnalyser();
                    left.fftSize=right.fftSize=1024;
                    options.source.connect(stereoInput); stereoInput.connect(splitter);
                    splitter.connect(left,0); splitter.connect(right,1);
                    leftWave=new Float32Array(1024); rightWave=new Float32Array(1024);
                }
            } catch (_) {
                if(stereoInput) { try { options.source.disconnect(stereoInput); } catch (ignored) {} }
                stereoInput=null; splitter=null; left=null; right=null;
            }
            var seq=0, epoch=0, lastState='', lastIdle=0, frames=0, skipped=0;
            var session=Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,8);
            var costs=[], lastDiagnostic=0, timer, stopped=false;
            var clock=function(){return root.performance.now();};
            function text(value,max) { return String(value===undefined||value===null?'':value).slice(0,max); }
            function emit(packet) {
                var raw=JSON.stringify(packet);
                // Leaves room for the entity relay's source IDs in a 1200B message.
                if (encodeURIComponent(raw).replace(/%[0-9A-F]{2}|./g,'x').length>1080) { skipped++; return; }
                options.bridge.emitWebEvent(raw);
            }
            function stereo() {
                if(!left)return null;
                left.getFloatTimeDomainData(leftWave); right.getFloatTimeDomainData(rightWave);
                var a=0,b=0,c=0;
                for(var i=0;i<1024;i++){a+=leftWave[i]*leftWave[i];b+=rightWave[i]*rightWave[i];c+=leftWave[i]*rightWave[i];}
                var l=Math.sqrt(a/1024),r=Math.sqrt(b/1024),correlation=a*b>1e-12?Math.max(-1,Math.min(1,c/Math.sqrt(a*b))):null;
                function round(x){return Math.round(x*1000)/1000;}
                return {left:round(l),right:round(r),balance:round((r-l)/Math.max(1e-6,l+r)),
                    width:correlation===null?0:round((1-correlation)/2),correlation:correlation===null?null:round(correlation)};
            }
            function tick() {
                if(stopped)return;
                var start=clock(), state=context.state!=='running'?'suspended':player.paused?'paused':player.readyState<3?'buffering':'playing';
                // Station metadata can lead buffered audio: advisory ID only,
                // never reset beat/pitch analysis on a polled track change.
                var track=options.track()||{}, stationTrackId=text(track.id,64);
                if(state!==lastState||(features.lastTime!==null&&context.currentTime-features.lastTime>0.5)) {
                    features.reset(); epoch++; lastState=state;
                }
                // Inactive pages send liveness only; don't analyse stale PCM.
                if(state!=='playing' && start-lastIdle<1000)return;
                if(state!=='playing')lastIdle=start;
                try {
                    if(state==='playing') { analyser.getFloatTimeDomainData(wave); analyser.getFloatFrequencyData(bins); }
                    else { wave.fill(0); bins.fill(-Infinity); }
                    var f=features.update(wave,bins,context.currentTime);
                    if(state==='playing')f.stereo=stereo();
                    var packet={type:'shufflizer.music',v:1,session:session,epoch:epoch,seq:++seq,
                        t:Math.round(context.currentTime*1000)/1000,wall:Date.now(),state:state,stationTrackId:stationTrackId,f:f};
                    root.ShufflizerMusic.last=packet;
                    emit(packet); frames++;
                    costs.push(clock()-start); if(costs.length>100)costs.shift();
                    if(start-lastDiagnostic>=1000) {
                        lastDiagnostic=start;
                        var sorted=costs.slice().sort(function(a,b){return a-b;});
                        root.ShufflizerMusic.stats={frames:frames,skipped:skipped,fftSize:4096,hz:20,
                            analysisP95Ms:Math.round(sorted[Math.floor((sorted.length-1)*0.95)]*1000)/1000};
                    }
                } catch(error) {
                    // A telemetry failure must never stop music or the visualiser.
                    root.ShufflizerMusic.error=String(error.message||error); stop();
                }
            }
            function stop() {
                if(stopped)return; stopped=true; root.clearInterval(timer);
                options.source.disconnect(analyser); analyser.disconnect();
                if(stereoInput){options.source.disconnect(stereoInput);stereoInput.disconnect();splitter.disconnect();left.disconnect();right.disconnect();}
            }
            root.ShufflizerMusic.stop=stop;
            timer=root.setInterval(tick,50);
            root.addEventListener('pagehide',stop);
        }
    };
}(window));
