const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function element() {
    const classes = new Set(['hidden']);
    return {
        value: '', disabled: false, innerHTML: '', dataset: {}, handlers: {}, style: {},
        classList: {
            add: (...values) => values.forEach(v => classes.add(v)),
            remove: (...values) => values.forEach(v => classes.delete(v)),
            contains: value => classes.has(value)
        },
        addEventListener(name, fn) { (this.handlers[name] ??= []).push(fn); },
        scrollIntoView() {},
        contains() { return false; }
    };
}

function fixture() {
    const window = {
        settingsManager: { getSettings: () => ({ model: 'gpt-4o' }), apiKeyInputs: {} },
        uiManager: { showToast() {} }
    };
    const context = vm.createContext({
        window, document: { addEventListener() {}, getElementById() { return null; } },
        console: { log() {}, error() {} }, Blob, FormData, AbortController,
        File: class extends Blob { constructor(parts, name, options) { super(parts, options); this.name = name; } },
        setTimeout, clearTimeout, navigator: {},
    });
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/js/main.js'), 'utf8')
        + '\nglobalThis.SnapSolverClass = SnapSolver;', context);
    const app = Object.create(context.SnapSolverClass.prototype);
    for (const key of ['recordBtn', 'asrPanel', 'asrText', 'sendAsrTextBtn',
        'emptyState', 'imagePreview', 'sendExtractedTextBtn', 'responseContent', 'claudePanel']) {
        app[key] = element();
    }
    app.socket = { connected: true, emit() {} };
    app.checkConnectionBeforeAction = () => app.socket.connected;
    app.setElementContent = (el, text) => { el.value = text; };
    app.updateStatusLight = () => {};
    app.showAsrStatus = function (text) {
        this.status = text;
        this.asrPanel.classList.remove('hidden');
        this.emptyState.classList.add('hidden');
    };
    return { app, context };
}

test('inactive recorder resets instead of getting stuck in processing', () => {
    const { app } = fixture();
    app.isRecording = true;
    app.mediaRecorder = { state: 'inactive' };
    app.stopAudioRecording();
    assert.equal(app.isRecording, false);
    assert.equal(app.recordBtn.disabled, false);
    assert.equal(app.recordBtn.classList.contains('processing'), false);
});

test('stop exception restores recording controls', () => {
    const { app } = fixture();
    app.mediaRecorder = { state: 'recording', stop() { throw Error('device removed'); } };
    app.stopAudioRecording();
    assert.equal(app.recordBtn.disabled, false);
    assert.equal(app.mediaRecorder, null);
});

test('transcription shows editable text and does not automatically call AI', async () => {
    const { app, context } = fixture();
    let sends = 0;
    app.socket.emit = () => sends++;
    context.fetch = async () => ({ ok: true, json: async () => ({ text: 'draft transcript' }) });
    await app.transcribeAudioBlob(new Blob(['audio'], { type: 'audio/webm' }));
    assert.equal(app.asrText.value, 'draft transcript');
    assert.equal(app.asrPanel.classList.contains('hidden'), false);
    assert.equal(app.emptyState.classList.contains('hidden'), true);
    assert.equal(app.sendAsrTextBtn.disabled, false);
    assert.equal(sends, 0);
});

test('ASR failure rejects without overwriting the previous transcript', async () => {
    const { app, context } = fixture();
    app.asrText.value = 'previous draft';
    context.fetch = async () => ({ ok: false, json: async () => ({ error: 'ASR unavailable' }) });
    await assert.rejects(app.transcribeAudioBlob(new Blob(['audio'])), /ASR unavailable/);
    assert.equal(app.asrText.value, 'previous draft');
});

test('send handler binds once and sends edited text only once', () => {
    const { app } = fixture();
    app.ensureAsrPanel();
    app.ensureAsrPanel();
    assert.equal(app.sendAsrTextBtn.handlers.click.length, 1);
    app.asrText.value = 'edited transcript';
    const requests = [];
    app.socket.emit = (event, data) => requests.push({ event, data });
    const click = app.sendAsrTextBtn.handlers.click[0];
    click();
    click();
    assert.equal(requests.length, 1);
    assert.equal(requests[0].event, 'analyze_text');
    assert.equal(requests[0].data.text, 'edited transcript');
    assert.equal(app.claudePanel.classList.contains('hidden'), false);
});

test('asynchronous recorder stop keeps its MIME type until upload completes', async () => {
    const { app, context } = fixture();
    let stopped = false;
    class Recorder {
        static isTypeSupported() { return true; }
        constructor() { this.mimeType = 'audio/webm'; this.handlers = {}; this.state = 'inactive'; }
        addEventListener(event, fn) { this.handlers[event] = fn; }
        start() { this.state = 'recording'; }
        stop() { this.state = 'inactive'; }
    }
    context.MediaRecorder = context.window.MediaRecorder = Recorder;
    context.navigator.mediaDevices = {
        getUserMedia: async () => ({ getTracks: () => [{ stop() { stopped = true; } }] })
    };
    let uploaded;
    app.transcribeAudioBlob = async blob => { uploaded = blob; };
    await app.startAudioRecording();
    const recorder = app.mediaRecorder;
    app.stopAudioRecording();
    recorder.handlers.dataavailable({ data: new Blob(['audio']) });
    await recorder.handlers.stop();
    assert.equal(uploaded.type, 'audio/webm');
    assert.equal(uploaded.size, 5);
    assert.equal(stopped, true);
    assert.equal(app.mediaRecorder, null);
    assert.equal(app.recordBtn.disabled, false);
});

test('AI terminal events restore the send button for the next request', () => {
    const { app } = fixture();
    const handlers = {};
    app.socket.on = (name, fn) => { handlers[name] = fn; };
    app.scrollToBottom = () => {};
    app.setupSocketEventHandlers();
    app.asrText.value = 'confirmed transcript';
    for (const status of ['completed', 'error', 'stopped']) {
        app.analysisPending = true;
        app.sendAsrTextBtn.disabled = true;
        handlers.ai_response({ status, content: 'test response', error: 'test failure' });
        assert.equal(app.analysisPending, false);
        assert.equal(app.sendAsrTextBtn.disabled, false);
    }
});
