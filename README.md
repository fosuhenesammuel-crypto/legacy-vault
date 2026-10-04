# Legacy Vault

A lightweight Flask-based vault app with PIN unlock, file uploads, and camera capture support.

## Local run

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask --app app run
```

## Add it to a phone

The app can be installed as a home-screen web app; this does not publish it to
the App Store or Google Play. The site must be available over HTTPS for phone
installation. The local `127.0.0.1` address refers to the device opening it, and
the LAN address only works while the computer is running the app on the same
Wi-Fi network. Plain HTTP on that LAN address is not enough for installation.

- Android: open the HTTPS site in Chrome and choose **Install app** (or use the
	browser menu's install option).
- iPhone: open the HTTPS site in Safari, tap **Share**, then **Add to Home
	Screen**.

The home-screen icon opens the hosted app in an app-style window. Vault data and
uploads remain on the server; they are not copied to the phone, and the app
needs the server to be reachable to use the vault.

Do not expose this app publicly yet. It currently has a hard-coded PIN and a
development fallback for its Flask session secret, and its local file storage
needs a durable, protected backup strategy before hosting private documents.

## Deploy

This repo includes a Render Blueprint in `render.yaml`. It defines a paid Starter
web service and a 1 GB persistent disk so uploaded files and vault records
survive restarts. In Render, connect this repository, set `VAULT_PIN` to a
private value of at least 8 characters when prompted, then deploy. Render
generates the session secret and provides the HTTPS URL.

The generated configuration protects session cookies with HTTPS and refuses to
start in production if the PIN or secret key is missing. Keep the deployment
URL private and set `VAULT_PIN` only in Render's environment settings.
