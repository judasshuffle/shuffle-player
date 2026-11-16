/* Shufflizer music telemetry v1. No dependencies, network, playback or world edits.
 * Spectrum values must be AnalyserNode float dB bins, waveform float PCM.
 * Estimates are deliberately confidence-qualified; no instrument recognition.
 */
(function (root, factory) {
    if (typeof module === 'object' && module.exports) module.exports = factory();
    else root.ShufflizerMusicFeatures = factory();
}(typeof window !== 'undefined' ? window : this, function () {
    'use strict';
    function clamp(x, lo, hi) { return Math.max(lo, Math.min(hi, x)); }
    function rounded(x) { return Math.round((isFinite(x) ? x : 0) * 1000) / 1000; }
    function smooth(old, value, dt, seconds) { return old + (value - old) * (1 - Math.exp(-dt / seconds)); }
    function Features(sampleRate, fftSize) {
        this.sampleRate = sampleRate; this.fftSize = fftSize;
        this.previous = new Float32Array(fftSize / 2);
        this.bandEdges = [20, 60, 150, 400, 1000, 2500, 6000, 12000, 20000];
        this.binBands = new Int8Array(fftSize / 2);
        this.binChroma = new Int8Array(fftSize / 2);
        for (var i = 0; i < this.binBands.length; i++) {
            var hz = i * sampleRate / fftSize, band = -1;
            for (var b = 0; b < 8; b++) if (hz >= this.bandEdges[b] && hz < this.bandEdges[b + 1]) band = b;
            this.binBands[i] = band;
            // Low FFT bins cannot resolve semitones: limit chroma to 250..4000Hz.
            this.binChroma[i] = hz >= 250 && hz <= 4000 ? ((Math.round(69 + 12 * Math.log(hz / 440) / Math.LN2) % 12) + 12) % 12 : -1;
        }
        this.reset();
    }
    Features.prototype.reset = function () {
        this.previous.fill(0); this.lastTime = null; this.startedAt = null; this.fast = 0; this.slow = 0;
        this.fluxMean = 0; this.fluxDeviation = 0; this.lastBeat = -100;
        // Consumers can deduplicate beats even across pauses and timing gaps.
        this.beatId = this.beatId || 0; this.beatTime = null; this.history = []; this.nextTempo = 0;
        this.bpm = null; this.tempoConfidence = 0; this.pitchHz = null; this.pitchConfidence = 0;
        this.nextPitch = 0; this.chroma = new Float32Array(12); this.silentFor = 0;
    };
    Features.prototype.tempo = function (time) {
        var h = this.history;
        if (h.length < 100 || h[h.length - 1].t - h[0].t < 5) return;
        var attacks=h.filter(function(frame){return frame.v>0;});
        if(attacks.length<6||time-attacks[attacks.length-1].t>2) {
            this.bpm=null; this.tempoConfidence=0; return;
        }
        var best = 0, bestBpm = 0;
        // Fixed-cost grid; onset history, not frame-rate assumptions. 70..180BPM.
        for (var bpm = 70; bpm <= 180; bpm++) {
            var period = 60 / bpm, score = 0, weight = 0;
            for (var i = 1; i < attacks.length; i++) {
                var gap=attacks[i].t-attacks[i-1].t;
                var multiple=clamp(Math.round(gap/period),1,3), error=gap-multiple*period;
                var w=Math.min(attacks[i].v,attacks[i-1].v)*Math.exp(-(time-attacks[i].t)/5);
                // Common denominator for every candidate. Prefer direct beats to
                // an equally plausible doubled tempo; tolerate missed attacks.
                score+=w*Math.exp(-error*error/(2*0.035*0.035))*(multiple===1?1:0.65);
                weight+=w;
            }
            score = weight > 0 ? score / weight : 0;
            if (score > best) { best = score; bestBpm = bpm; }
        }
        this.tempoConfidence = clamp((best - 0.2) / 0.7, 0, 1)*Math.min(1,(attacks.length-3)/5);
        this.bpm = this.tempoConfidence >= 0.35 ? bestBpm : null;
    };
    Features.prototype.pitch = function (wave, rms, dominantHz) {
        this.pitchHz = null; this.pitchConfidence = 0;
        if (rms < 0.008 || dominantHz<60 || dominantHz>1100) return;
        // Full-rate samples avoid decimation aliasing. Bounded to 4096 samples,
        // 70..1000Hz and four calls/s; dominant-bin gate rejects high-only tones.
        var stride=1, rate=this.sampleRate, n=Math.min(4096,wave.length);
        var minLag=Math.max(2,Math.floor(rate/1000)), maxLag=Math.min(Math.ceil(rate/70),Math.floor(n/2)-2);
        var mean = 0, i, lag, best = 0, bestLag = 0, values = [];
        for (i = 0; i < n; i++) mean += wave[i * stride];
        mean /= n;
        for (lag = minLag-1; lag <= maxLag+1; lag++) {
            var dot = 0, a2 = 0, b2 = 0;
            for (i = 0; i < n - maxLag-2; i++) {
                var a = wave[i * stride] - mean, b = wave[(i + lag) * stride] - mean;
                dot += a * b; a2 += a * a; b2 += b * b;
            }
            values[lag] = dot / Math.max(1e-12, Math.sqrt(a2 * b2));
            best = Math.max(best, values[lag]);
        }
        // Earliest strong local peak avoids choosing arbitrary lower octaves.
        for (lag = minLag; lag <= maxLag; lag++) {
            if (values[lag] >= Math.max(0.8, best * 0.96) && values[lag] > values[lag - 1] && values[lag] >= values[lag + 1]) { bestLag = lag; break; }
        }
        if (bestLag) {
            var left = values[bestLag - 1], centre = values[bestLag], right = values[bestLag + 1];
            var correction = 0.5 * (left - right) / (left - 2 * centre + right || 1);
            var hz=rate/(bestLag+clamp(correction,-0.5,0.5));
            if(hz>=69.5&&hz<=1001) {this.pitchConfidence=clamp(centre,0,1);this.pitchHz=hz;}
        }
    };
    Features.prototype.update = function (wave, dbBins, time) {
        var dt = this.lastTime === null ? 0.05 : time - this.lastTime;
        if (!isFinite(dt) || dt <= 0 || dt > 0.5) { this.reset(); dt = 0.05; }
        this.lastTime = time;
        if (this.startedAt === null) this.startedAt = time;
        var sum = 0, peak = 0, crossings = 0, i;
        for (i = 0; i < wave.length; i++) {
            var value = isFinite(wave[i]) ? wave[i] : 0;
            sum += value * value; peak = Math.max(peak, Math.abs(value));
            if (i && (value >= 0) !== (wave[i - 1] >= 0)) crossings++;
        }
        var rms = Math.sqrt(sum / Math.max(1, wave.length)), silent = rms < 0.003;
        this.silentFor = silent ? this.silentFor + dt : 0;
        this.fast = smooth(this.fast, rms, dt, 0.25); this.slow = smooth(this.slow, rms, dt, 5);
        var bands = [0,0,0,0,0,0,0,0], chroma = [0,0,0,0,0,0,0,0,0,0,0,0];
        var magnitudeSum = 0, powerSum = 0, weighted = 0, logSum = 0, count = 0, flux = 0, dominant = 0, maxMagnitude = 0;
        for (i = 1; i < this.previous.length; i++) {
            var db = dbBins[i], magnitude = isFinite(db) ? Math.pow(10, clamp(db, -140, 20) / 20) : 0;
            var power = magnitude * magnitude, hz = i * this.sampleRate / this.fftSize;
            if (hz >= 20 && hz <= 20000) {
                magnitudeSum += magnitude; powerSum += power; weighted += magnitude * hz;
                logSum += Math.log(Math.max(1e-12, magnitude)); count++;
                flux += Math.max(0, magnitude - this.previous[i]);
                if (magnitude > maxMagnitude) { maxMagnitude = magnitude; dominant = hz; }
            }
            var band = this.binBands[i], note = this.binChroma[i];
            if (band >= 0) bands[band] += power;
            if (note >= 0) chroma[note] += power;
            this.previous[i] = magnitude;
        }
        // Relative band powers are independent of listener volume and bounded 0..1.
        for (i = 0; i < bands.length; i++) bands[i] = silent ? 0 : bands[i] / Math.max(1e-12, powerSum);
        var centroid = silent ? 0 : weighted / Math.max(1e-12, magnitudeSum);
        var flatness = silent ? 0 : clamp(Math.exp(logSum / Math.max(1,count)) / Math.max(1e-12,magnitudeSum / Math.max(1,count)),0,1);
        var accumulated = 0, rolloff = 0;
        for (i = 1; i < this.previous.length; i++) {
            var binHz = i * this.sampleRate / this.fftSize;
            if (binHz < 20 || binHz > 20000) continue;
            accumulated += this.previous[i] * this.previous[i];
            if (accumulated >= powerSum * 0.85) { rolloff = binHz; break; }
        }
        var threshold = Math.max(0.015, this.fluxMean + 2 * this.fluxDeviation);
        var onset = silent || time-this.startedAt<0.2 ? 0 : clamp((flux - threshold) / Math.max(0.03,threshold),0,1);
        var beat = onset > 0.2 && time - this.lastBeat >= 0.22;
        if (beat) { this.lastBeat = time; this.beatTime = time; this.beatId++; }
        this.fluxDeviation = smooth(this.fluxDeviation,Math.abs(flux-this.fluxMean),dt,1);
        this.fluxMean = smooth(this.fluxMean,flux,dt,1);
        this.history.push({t:time,v:beat ? onset : 0});
        while (this.history.length && (time-this.history[0].t>10 || this.history.length>220)) this.history.shift();
        if (this.silentFor > 1) { this.bpm = null; this.tempoConfidence = 0; this.beatTime = null; }
        else if (time >= this.nextTempo) { this.tempo(time); this.nextTempo = time + 1; }
        if(time-this.lastBeat>2){this.bpm=null;this.tempoConfidence=0;}
        if (time >= this.nextPitch) { this.pitch(wave,rms,dominant); this.nextPitch = time + 0.25; }
        if (silent) { this.pitchHz = null; this.pitchConfidence = 0; }
        var chromaSum = 0;
        for (i = 0; i < 12; i++) { this.chroma[i] = smooth(this.chroma[i], silent ? 0 : chroma[i], dt, 1); chromaSum += this.chroma[i]; }
        for (i = 0; i < 12; i++) chroma[i] = silent ? 0 : this.chroma[i] / Math.max(1e-12,chromaSum);
        var result = {
            rms:rms, peak:peak, db:Math.max(-120,20*Math.log(Math.max(1e-6,rms))/Math.LN10),
            energy:clamp(rms / Math.max(0.05,this.slow*2),0,1),
            bass:bands[0]+bands[1], mid:bands[2]+bands[3]+bands[4], treble:bands[5]+bands[6]+bands[7],
            bands:bands, centroid:centroid, brightness:clamp(Math.log(1+centroid/100)/Math.log(201),0,1),
            rolloff:silent?0:rolloff, flatness:flatness, flux:flux, onset:onset,
            beat:beat, beatId:this.beatId, beatTime:this.beatTime,
            bpm:this.bpm, tempoConfidence:this.tempoConfidence,
            beatPhase:this.bpm && this.beatTime!==null ? ((time-this.beatTime)*this.bpm/60)%1 : null,
            pitchHz:this.pitchHz, pitchConfidence:this.pitchConfidence, dominantHz:silent?null:dominant,
            chroma:chroma, trend:clamp((this.fast-this.slow)/Math.max(0.02,this.slow),-1,1),
            crest:clamp(peak/Math.max(1e-6,rms),0,20), zcr:crossings/Math.max(1,wave.length), silent:silent,
            stereo:null
        };
        Object.keys(result).forEach(function(key) {
            if (typeof result[key] === 'number') result[key]=rounded(result[key]);
            else if (Array.isArray(result[key])) result[key]=result[key].map(rounded);
        });
        return result;
    };
    return Features;
}));
