const video = document.querySelector('#camera-preview');
const canvas = document.querySelector('#camera-canvas');
const captureButton = document.querySelector('#capture-button');
const status = document.querySelector('#camera-status');

async function startCamera() {
    if (!window.isSecureContext && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
        captureButton.disabled = true;
        status.textContent = 'Open this page via HTTPS or localhost to enable the camera on your phone.';
        return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        captureButton.disabled = true;
        status.textContent = 'This browser does not support camera access.';
        return;
    }

    try {
        video.srcObject = await navigator.mediaDevices.getUserMedia({ video: true });
        status.textContent = 'Camera ready.';
    } catch (error) {
        captureButton.disabled = true;
        status.textContent = 'Camera access was not available. Allow camera permission or use HTTPS.';
    }
}

captureButton.addEventListener('click', async () => {
    if (!video.srcObject) {
        status.textContent = 'Camera is not ready yet. Please wait a moment.';
        return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.92));
    const form = new FormData();
    form.append('file', blob, 'camera_capture.jpg');
    const response = await fetch('/capture', { method: 'POST', body: form });
    if (response.ok) window.location.href = '/vault';
    else status.textContent = 'Capture failed. Please try again.';
});

startCamera();