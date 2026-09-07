const state = {
    currentBookId: null,
    extractedText: "",
    progressTimer: null,
    waveTimer: null,
};

const dom = {};

document.addEventListener("DOMContentLoaded", () => {
    bindDom();
    bindEvents();
    updateMetrics("");
});

function bindDom() {
    dom.fileInput = document.getElementById("fileInput");
    dom.browseFileBtn = document.getElementById("browseFileBtn");
    dom.uploadDropZone = document.getElementById("uploadDropZone");
    dom.uploadTitle = document.getElementById("uploadTitle");
    dom.uploadHint = document.getElementById("uploadHint");
    dom.uploadStatus = document.getElementById("uploadStatus");
    dom.textInput = document.getElementById("textInput");
    dom.manualTitle = document.getElementById("manualTitle");
    dom.wordCount = document.getElementById("wordCount");
    dom.charCount = document.getElementById("charCount");
    dom.listenEstimate = document.getElementById("listenEstimate");
    dom.voiceSelect = document.getElementById("voiceSelect");
    dom.speedRange = document.getElementById("speedRange");
    dom.speedValue = document.getElementById("speedValue");
    dom.convertBtn = document.getElementById("convertBtn");
    dom.convertProgressWrap = document.getElementById("convertProgressWrap");
    dom.convertProgressBar = document.getElementById("convertProgressBar");
    dom.convertPercent = document.getElementById("convertPercent");
    dom.convertStepLabel = document.getElementById("convertStepLabel");
    dom.audioPanel = document.getElementById("audioPanel");
    dom.audioPlayer = document.getElementById("audioPlayer");
    dom.downloadLink = document.getElementById("downloadLink");
    dom.waveBars = document.querySelectorAll(".wave-bar");
}

function bindEvents() {
    dom.browseFileBtn.addEventListener("click", () => dom.fileInput.click());

    dom.fileInput.addEventListener("change", () => {
        if (dom.fileInput.files.length) {
            uploadPdf(dom.fileInput.files[0]);
        }
    });

    ["dragenter", "dragover"].forEach((eventName) => {
        dom.uploadDropZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            dom.uploadDropZone.classList.add("drag-over");
        });
    });

    ["dragleave", "drop"].forEach((eventName) => {
        dom.uploadDropZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            dom.uploadDropZone.classList.remove("drag-over");
        });
    });

    dom.uploadDropZone.addEventListener("drop", (event) => {
        const [file] = event.dataTransfer.files;
        if (file) {
            uploadPdf(file);
        }
    });

    dom.speedRange.addEventListener("input", () => {
        dom.speedValue.textContent = `${Number(dom.speedRange.value).toFixed(2)}x`;
    });

    dom.convertBtn.addEventListener("click", convertPdf);
    dom.audioPlayer.addEventListener("play", startWaveform);
    dom.audioPlayer.addEventListener("pause", stopWaveform);
    dom.audioPlayer.addEventListener("ended", stopWaveform);
}

async function uploadPdf(file) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
        showStatus("Please choose a PDF file.", "error");
        return;
    }

    if (file.size > 25 * 1024 * 1024) {
        showStatus("PDF must be smaller than 25MB.", "error");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);
    resetAudio();
    setLoading(true, "Reading PDF...");

    try {
        const response = await fetch("/upload", {
            method: "POST",
            body: formData,
        });
        const payload = await response.json();

        if (!response.ok || !payload.success) {
            throw new Error(payload.error || "Upload failed.");
        }

        state.currentBookId = payload.book.id;
        state.extractedText = payload.text;
        dom.textInput.value = payload.text;
        dom.manualTitle.value = payload.book.title;
        dom.uploadTitle.textContent = payload.book.title;
        dom.uploadHint.textContent = `${payload.book.word_count.toLocaleString()} words extracted from PDF.`;
        dom.convertBtn.disabled = false;
        updateMetrics(payload.text);
        showStatus("PDF is ready to convert.", "success");
    } catch (error) {
        state.currentBookId = null;
        state.extractedText = "";
        dom.convertBtn.disabled = true;
        updateMetrics("");
        showStatus(error.message, "error");
    } finally {
        setLoading(false);
    }
}

async function convertPdf() {
    if (!state.currentBookId || !state.extractedText.trim()) {
        showStatus("Upload a readable PDF first.", "error");
        return;
    }

    dom.convertBtn.disabled = true;
    startProgress();

    try {
        const response = await fetch("/convert", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                book_id: state.currentBookId,
                language: "en",
                voice: dom.voiceSelect.value,
                speed: Number(dom.speedRange.value),
            }),
        });
        const payload = await response.json();

        if (!response.ok || !payload.success) {
            const detail = payload.retryable ? " Your PDF is still ready; please try again in a moment." : "";
            throw new Error((payload.error || "Conversion failed.") + detail);
        }

        dom.audioPlayer.src = payload.audio.audio_url;
        dom.downloadLink.href = payload.audio.download_url;
        dom.audioPanel.classList.remove("d-none");
        finishProgress("Done.");
        showStatus("MP3 is ready.", "success");
    } catch (error) {
        failProgress(`Could not create MP3`);
        showStatus(error.message, "error");
    } finally {
        dom.convertBtn.disabled = false;
    }
}

function updateMetrics(text) {
    const words = (text.trim().match(/\S+/g) || []).length;
    dom.wordCount.textContent = words.toLocaleString();
    dom.charCount.textContent = text.length.toLocaleString();
    dom.listenEstimate.textContent = (words / 150).toFixed(2);
}

function setLoading(isLoading, message = "") {
    dom.browseFileBtn.disabled = isLoading;
    if (isLoading) {
        showStatus(message, "info");
    }
}

function startProgress() {
    dom.convertProgressWrap.classList.remove("d-none");
    clearInterval(state.progressTimer);
    let progress = 0;
    const steps = ["Preparing PDF text...", "Creating voice...", "Writing MP3..."];
    state.progressTimer = setInterval(() => {
        progress = Math.min(progress + 8, 92);
        dom.convertProgressBar.style.width = `${progress}%`;
        dom.convertPercent.textContent = `${progress}%`;
        dom.convertStepLabel.textContent = steps[Math.min(Math.floor(progress / 34), steps.length - 1)];
    }, 280);
}

function finishProgress(label) {
    clearInterval(state.progressTimer);
    dom.convertStepLabel.textContent = label;
    dom.convertProgressBar.style.width = "100%";
    dom.convertPercent.textContent = "100%";
    setTimeout(() => dom.convertProgressWrap.classList.add("d-none"), 900);
}

function failProgress(label) {
    clearInterval(state.progressTimer);
    dom.convertProgressBar.classList.add("progress-failed");
    dom.convertStepLabel.textContent = label;
    dom.convertPercent.textContent = "Failed";
    setTimeout(() => {
        dom.convertProgressWrap.classList.add("d-none");
        dom.convertProgressBar.classList.remove("progress-failed");
    }, 2200);
}

function resetAudio() {
    dom.audioPlayer.pause();
    dom.audioPlayer.removeAttribute("src");
    dom.downloadLink.removeAttribute("href");
    dom.audioPanel.classList.add("d-none");
    stopWaveform();
}

function startWaveform() {
    clearInterval(state.waveTimer);
    state.waveTimer = setInterval(() => {
        dom.waveBars.forEach((bar) => {
            bar.style.height = `${8 + Math.random() * 34}px`;
            bar.style.opacity = `${0.5 + Math.random() * 0.5}`;
        });
    }, 120);
}

function stopWaveform() {
    clearInterval(state.waveTimer);
    dom.waveBars.forEach((bar) => {
        bar.style.height = "8px";
        bar.style.opacity = "1";
    });
}

function showStatus(message, type) {
    dom.uploadStatus.className = `status-line status-${type}`;
    dom.uploadStatus.textContent = message;
    dom.uploadStatus.classList.remove("d-none");
}
