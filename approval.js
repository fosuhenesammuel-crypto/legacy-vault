document.addEventListener('DOMContentLoaded', () => {
    const startApprovalButton = document.querySelector('#start-approval');
    const qrImage = document.querySelector('#approval-qr');
    const statusText = document.querySelector('#approval-status');
    const approvalBox = document.querySelector('#approval-box');
    const tokenInput = document.querySelector('#approval-token');

    const handleApprovalState = (token, targetUrl, onApproved, onPendingMessage) => {
        const poll = () => {
            fetch(`/approval-status/${token}`)
                .then((response) => response.json())
                .then((result) => {
                    if (result.status === 'approved') {
                        onApproved();
                        return;
                    }

                    if (onPendingMessage) {
                        onPendingMessage();
                    }
                    setTimeout(poll, 2000);
                })
                .catch(() => {
                    if (statusText) {
                        statusText.textContent = 'Approval request expired. Please try again.';
                    }
                });
        };

        poll();
    };

    if (startApprovalButton && qrImage && statusText && approvalBox && tokenInput) {
        const beginApproval = () => {
            fetch('/begin_phone_approval')
                .then((response) => response.json())
                .then((data) => {
                    tokenInput.value = data.token;
                    qrImage.src = data.qr_code;
                    approvalBox.hidden = false;
                    statusText.textContent = 'Scan with your phone and tap “Yes, it’s me”.';

                    handleApprovalState(
                        data.token,
                        '/vault',
                        () => {
                            statusText.textContent = 'Approved on your phone. Unlocking…';
                            fetch(`/unlock-with-token/${data.token}`, { method: 'POST' })
                                .then((res) => res.json())
                                .then((payload) => {
                                    if (payload.redirect) {
                                        window.location.href = payload.redirect;
                                    }
                                });
                        },
                        () => {
                            statusText.textContent = 'Waiting for approval on your phone…';
                        }
                    );
                })
                .catch(() => {
                    statusText.textContent = 'Could not start phone approval. Please try again.';
                });
        };

        startApprovalButton.addEventListener('click', beginApproval);
    }

    const launchButtons = document.querySelectorAll('.launch-app-btn');
    const launchPanel = document.querySelector('#launch-approval-panel');
    const launchQr = document.querySelector('#launch-qr');
    const launchStatus = document.querySelector('#launch-status');

    if (launchButtons.length && launchPanel && launchQr && launchStatus) {
        launchButtons.forEach((button) => {
            button.addEventListener('click', () => {
                const params = new URLSearchParams({
                    app: button.dataset.app || ''
                });

                fetch(`/begin_app_launch?${params.toString()}`)
                    .then((response) => {
                        if (!response.ok) {
                            throw new Error('Could not start app approval');
                        }
                        return response.json();
                    })
                    .then((data) => {
                        launchPanel.hidden = false;
                        launchQr.src = data.qr_code;
                        launchStatus.textContent = `Scan this code on your phone to approve opening ${data.app_name}.`;

                        handleApprovalState(
                            data.token,
                            data.target_url,
                            () => {
                                launchStatus.textContent = 'Approved. Opening the app…';
                                window.location.assign(data.target_url);
                            },
                            () => {
                                launchStatus.textContent = `Waiting for approval on your phone to open ${data.app_name}...`;
                            }
                        );
                    })
                    .catch(() => {
                        launchStatus.textContent = 'Could not start approval for this app.';
                    });
            });
        });
    }
});
