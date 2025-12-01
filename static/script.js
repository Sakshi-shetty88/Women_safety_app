// ---------------- AI / ML-LIKE THREAT DETECTION ----------------
// Simple shake-based detection using DeviceMotion as an AI proxy.

if (window.DeviceMotionEvent) {
    let lastShakeTime = 0;

    window.addEventListener('devicemotion', (event) => {
        const ax = event.accelerationIncludingGravity.x || 0;
        const ay = event.accelerationIncludingGravity.y || 0;
        const az = event.accelerationIncludingGravity.z || 0;

        const magnitude = Math.sqrt(ax * ax + ay * ay + az * az);
        const now = Date.now();

        if (magnitude > 12 && (now - lastShakeTime) > 5000) {
            lastShakeTime = now;
            try {
                aiDetectedThreat();
            } catch (e) {
                console.error('aiDetectedThreat not available', e);
            }
        }
    });
}
