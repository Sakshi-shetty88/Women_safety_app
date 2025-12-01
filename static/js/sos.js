// static/js/sos.js

// ---------- NETWORK STATUS ----------
let isOnline = navigator.onLine;
const ALERT_QUEUE_KEY = 'sos_alert_queue';

window.addEventListener('online', () => {
    isOnline = true;
    autoSendQueuedAlerts();
});

window.addEventListener('offline', () => {
    isOnline = false;
});

// ---------- LOCATION ----------
function getLocation() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject('Geolocation not supported');
            return;
        }
        navigator.geolocation.getCurrentPosition(
            pos => resolve(pos),
            err => reject(err.message || 'Location error'),
            { enableHighAccuracy: true, timeout: 10000 }
        );
    });
}

// ---------- MAIN SOS (CALLED FROM UI OR AI) ----------
async function triggerSOS(manual = true) {
    const statusEl = document.getElementById('status');

    try {
        if (statusEl) statusEl.textContent = 'Getting location...';
        const pos = await getLocation();

        const payload = {
            location: {
                lat: pos.coords.latitude,
                lon: pos.coords.longitude,
            },
            source: manual ? 'manual' : 'ai',
            timestamp: new Date().toISOString(),
        };

        // Local vibration + siren (works even offline)
        if (navigator.vibrate) {
            navigator.vibrate([300, 200, 300, 200, 500]);
        }
        try {
            const audio = new Audio('/static/siren.mp3');
            audio.play().catch(() => {});
        } catch (e) {
            console.log('Audio error', e);
        }

        if (isOnline) {
            if (statusEl) statusEl.textContent = 'Sending SOS alert...';
            await sendToBackend(payload);
            if (statusEl) statusEl.textContent = 'SOS alert sent successfully!';
        } else {
            queueAlert(payload);
            if (statusEl) statusEl.textContent =
                'No internet. SOS saved and will auto-send when you are online.';
            smsFallbackBasic();
        }
    } catch (e) {
        console.error(e);
        alert('Error in SOS: ' + e);
        if (statusEl) statusEl.textContent = 'Error in SOS: ' + e;
    }
}

// ---------- BACKEND CALL ----------
async function sendToBackend(data) {
    const res = await fetch('/api/sos-offline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    if (!res.ok) {
        throw new Error('Backend error: ' + res.status);
    }
    return res.json();
}

// ---------- QUEUE HANDLING ----------
function queueAlert(data) {
    const q = JSON.parse(localStorage.getItem(ALERT_QUEUE_KEY) || '[]');
    q.push(data);
    localStorage.setItem(ALERT_QUEUE_KEY, JSON.stringify(q));
}

async function autoSendQueuedAlerts() {
    const q = JSON.parse(localStorage.getItem(ALERT_QUEUE_KEY) || '[]');
    if (!q.length) return;

    const remaining = [];
    for (const item of q) {
        try {
            await sendToBackend(item);
        } catch (e) {
            console.error('Failed to send queued SOS', e);
            remaining.push(item);
        }
    }
    localStorage.setItem(ALERT_QUEUE_KEY, JSON.stringify(remaining));
}

// ---------- SIMPLE SMS FALLBACK ----------
function smsFallbackBasic() {
    const phone = '100'; // demo primary number
    const body = encodeURIComponent('EMERGENCY! I need help. Unable to send internet SOS.');
    window.location.href = `sms:${phone}?body=${body}`;
}

// ---------- AI/ML HOOK ----------
function aiDetectedThreat() {
    alert('AI detected abnormal movement – auto SOS');  // debug
    triggerSOS(false);
}

