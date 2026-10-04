from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, session
import os
import socket
import uuid
import base64
import json
from datetime import datetime, timezone
from io import BytesIO
import qrcode
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STORAGE_DIR = os.path.abspath(os.environ.get('STORAGE_DIR', BASE_DIR))
UPLOAD_DIR = os.path.join(STORAGE_DIR, 'uploads')
TEMP_UPLOAD_DIR = os.path.join(STORAGE_DIR, 'temp_uploads')
APP_DATA_DIR = os.path.join(STORAGE_DIR, 'vault_app_data')
APP_ITEMS_FILE = os.path.join(APP_DATA_DIR, 'items.json')
APP_UPLOAD_DIR = os.path.join(APP_DATA_DIR, 'files')
IS_PRODUCTION = os.environ.get('APP_ENV') == 'production'
VAULT_PIN = os.environ.get('VAULT_PIN', '1234' if not IS_PRODUCTION else '')
APPROVAL_REQUESTS = {}
APP_LAUNCHES = {
    'legal-docs': {
        'name': 'Legal Docs',
        'description': 'Contracts, wills, and legal records',
    },
    'banking': {
        'name': 'Banking Portal',
        'description': 'Private banking and account records',
    },
    'health-records': {
        'name': 'Health Records',
        'description': 'Medical documents and care history',
    },
}


def generate_qr_data_url(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    image = qr.make_image(fill_color='black', back_color='white')
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(
        buffer.getvalue()).decode('ascii')


def lan_ip():
    configured_ip = os.environ.get('LAN_IP')
    if configured_ip:
        return configured_ip

    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(('8.8.8.8', 80))
        ip_address = probe.getsockname()[0]
        probe.close()
        if ip_address and not ip_address.startswith('127.'):
            return ip_address
    except OSError:
        pass

    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return None


def phone_base_url():
    configured_url = os.environ.get('PUBLIC_BASE_URL')
    if configured_url:
        return configured_url.rstrip('/')

    host = request.host
    hostname = host.rsplit(':', 1)[0]
    port = host.rsplit(':', 1)[1] if ':' in host else None
    if hostname in {'127.0.0.1', 'localhost', '::1', '[::1]'}:
        reachable_ip = lan_ip()
        if reachable_ip:
            host = f'{reachable_ip}:{port}' if port else reachable_ip
    return f'{request.scheme}://{host}'


def ensure_directory(path):
    if os.path.exists(path):
        if os.path.isdir(path):
            return
        os.remove(path)
    os.makedirs(path, exist_ok=True)


def load_app_items():
    ensure_directory(APP_DATA_DIR)
    if not os.path.exists(APP_ITEMS_FILE):
        return {app_id: [] for app_id in APP_LAUNCHES}

    try:
        with open(APP_ITEMS_FILE, 'r', encoding='utf-8') as data_file:
            saved_items = json.load(data_file)
    except (OSError, json.JSONDecodeError):
        saved_items = {}

    return {app_id: saved_items.get(app_id, []) for app_id in APP_LAUNCHES}


def save_app_items(items):
    ensure_directory(APP_DATA_DIR)
    temporary_file = APP_ITEMS_FILE + '.tmp'
    with open(temporary_file, 'w', encoding='utf-8') as data_file:
        json.dump(items, data_file, indent=2)
    os.replace(temporary_file, APP_ITEMS_FILE)


app = Flask(__name__)
secret_key = os.environ.get('SECRET_KEY')
if IS_PRODUCTION and (not secret_key or len(VAULT_PIN) < 8):
    raise RuntimeError(
        'Production requires SECRET_KEY and a VAULT_PIN of at least 8 characters')
app.secret_key = secret_key or 'legacy-vault-development-key'
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION


@app.errorhandler(RequestEntityTooLarge)
def file_too_large(_error):
    if request.path.startswith('/vault-app/'):
        app_id = request.view_args.get('app_id') if request.view_args else None
        if app_id:
            return redirect(url_for('vault_app_page', app_id=app_id, error='too_large'))
    if request.accept_mimetypes.best == 'application/json' or request.headers.get(
            'X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'File is larger than 25 MB'}), 413
    return redirect(url_for('upload_file', error='too_large'))


@app.after_request
def no_cache_for_dynamic_pages(response):
    if request.path in {
            '/', '/unlock', '/vault', '/upload', '/gallery', '/camera'
    }:
        response.headers[
            'Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


@app.route('/style.css')
def style_css():
    return send_from_directory(BASE_DIR, 'style.css', mimetype='text/css')


@app.route('/app.js')
def app_js():
    return send_from_directory(BASE_DIR,
                               'app.js',
                               mimetype='application/javascript')


@app.route('/camera.js')
def camera_js():
    return send_from_directory(BASE_DIR,
                               'camera.js',
                               mimetype='application/javascript')


@app.route('/approval.js')
def approval_js():
    return send_from_directory(BASE_DIR,
                               'approval.js',
                               mimetype='application/javascript')


@app.route('/manifest.json')
def manifest_json():
    return send_from_directory(BASE_DIR,
                               'manifest.json',
                               mimetype='application/manifest+json')


@app.route('/service-worker.js')
def service_worker_js():
    return send_from_directory(BASE_DIR,
                               'service-worker.js',
                               mimetype='application/javascript')


@app.route('/icon.svg')
def icon_svg():
    return send_from_directory(BASE_DIR, 'icon.svg', mimetype='image/svg+xml')


# Ensure the uploads and temp_uploads directories exist
ensure_directory(UPLOAD_DIR)
ensure_directory(TEMP_UPLOAD_DIR)
ensure_directory(APP_DATA_DIR)
ensure_directory(APP_UPLOAD_DIR)


def is_unlocked():
    return session.get('vault_unlocked') is True


@app.route('/')
def index():
    if is_unlocked():
        return redirect(url_for('vault_page'))
    return render_template('index.html')


@app.route('/unlock', methods=['GET', 'POST'])
def unlock_page():
    if request.method == 'POST':
        pin = request.form.get('pin', '')
        if pin == VAULT_PIN:
            session['vault_unlocked'] = True
            return redirect(url_for('vault_page'))
        return render_template('unlock.html', error='Incorrect PIN')
    return render_template('unlock.html', approval_token=None)


@app.route('/begin_phone_approval')
def begin_phone_approval():
    token = uuid.uuid4().hex
    APPROVAL_REQUESTS[token] = {'approved': False}
    verify_url = f'{phone_base_url()}{url_for("verify_phone_approval", token=token)}'
    qr_data_url = generate_qr_data_url(verify_url)

    return jsonify({
        'token': token,
        'verify_url': verify_url,
        'qr_code': qr_data_url,
    })


@app.route('/verify/<token>')
def verify_phone_approval(token):
    approval = APPROVAL_REQUESTS.get(token)
    if not approval:
        return render_template(
            'verify.html',
            token=token,
            error='This approval request is no longer valid.'), 404
    return render_template(
        'verify.html',
        token=token,
        approved=approval.get('approved', False),
        app_name=approval.get('app_name'),
    )


@app.route('/approve/<token>', methods=['POST', 'GET'])
def approve_phone_request(token):
    approval = APPROVAL_REQUESTS.get(token)
    if not approval:
        return jsonify({'error': 'Approval request not found'}), 404

    approval['approved'] = True

    if request.method == 'POST':
        return render_template(
            'verify.html',
            token=token,
            approved=True,
            app_name=approval.get('app_name'),
        )

    return jsonify({
        'status': 'approved',
        'message': 'Approval confirmed. The laptop can now unlock.',
    })


@app.route('/approval-status/<token>')
def approval_status(token):
    approval = APPROVAL_REQUESTS.get(token)
    if not approval:
        return jsonify({'status': 'expired'}), 404
    return jsonify(
        {'status': 'approved' if approval.get('approved') else 'pending'})


@app.route('/unlock-with-token/<token>', methods=['POST'])
def unlock_with_token(token):
    approval = APPROVAL_REQUESTS.get(token)
    if not approval or not approval.get('approved'):
        return jsonify({'error': 'Approval has not been confirmed yet'}), 400

    session['vault_unlocked'] = True
    return jsonify({'status': 'unlocked', 'redirect': url_for('vault_page')})


@app.route('/begin_app_launch')
def begin_app_launch():
    app_id = request.args.get('app', '')
    selected_app = APP_LAUNCHES.get(app_id)
    if not selected_app:
        return jsonify({'error': 'Unknown vault app'}), 400

    token = uuid.uuid4().hex

    APPROVAL_REQUESTS[token] = {
        'approved': False,
        'type': 'app_launch',
        'app_name': selected_app['name'],
        'target_url': url_for('vault_app_page', app_id=app_id),
    }

    verify_url = f'{phone_base_url()}{url_for("verify_phone_approval", token=token)}'
    return jsonify({
        'token': token,
        'verify_url': verify_url,
        'app_name': selected_app['name'],
        'target_url': APPROVAL_REQUESTS[token]['target_url'],
        'qr_code': generate_qr_data_url(verify_url),
    })


@app.route('/launch-app/<token>')
def launch_app(token):
    approval = APPROVAL_REQUESTS.get(token)
    if not approval:
        return jsonify({'error': 'Approval request not found'}), 404
    if not approval.get('approved'):
        return jsonify({'status': 'pending'}), 202

    target_url = approval.get('target_url')
    if not target_url:
        return jsonify({'error': 'No target URL'}), 400
    return jsonify({'status': 'approved', 'target_url': target_url})


@app.route('/vault')
def vault_page():
    if not is_unlocked():
        return redirect(url_for('unlock_page'))

    files = []
    if os.path.isdir(UPLOAD_DIR):
        files = sorted(os.listdir(UPLOAD_DIR))
    return render_template('vault.html', files=files, phone_url=phone_base_url())


@app.route('/vault-app/<app_id>')
def vault_app_page(app_id):
    if not is_unlocked():
        return redirect(url_for('unlock_page'))

    selected_app = APP_LAUNCHES.get(app_id)
    if not selected_app:
        return 'Vault app not found', 404
    items = load_app_items()[app_id]
    app_file_dir = os.path.join(APP_UPLOAD_DIR, app_id)
    ensure_directory(app_file_dir)
    files = sorted(os.listdir(app_file_dir))
    return render_template(
        'vault_app.html',
        app_id=app_id,
        items=items,
        files=files,
        **selected_app,
    )


@app.route('/vault-app/<app_id>/uploads', methods=['POST'])
def upload_vault_app_file(app_id):
    if not is_unlocked():
        return redirect(url_for('unlock_page'))
    if app_id not in APP_LAUNCHES:
        return 'Vault app not found', 404

    uploaded_file = request.files.get('file')
    if not uploaded_file or not uploaded_file.filename:
        return redirect(url_for('vault_app_page', app_id=app_id, error='file'))

    safe_name = secure_filename(uploaded_file.filename)
    if not safe_name:
        return redirect(url_for('vault_app_page', app_id=app_id, error='file'))

    app_file_dir = os.path.join(APP_UPLOAD_DIR, app_id)
    ensure_directory(app_file_dir)
    unique_name = f'{uuid.uuid4().hex[:10]}_{safe_name}'
    try:
        uploaded_file.save(os.path.join(app_file_dir, unique_name))
    except OSError:
        return redirect(url_for('vault_app_page', app_id=app_id, error='save'))
    return redirect(url_for('vault_app_page', app_id=app_id))


@app.route('/vault-app/<app_id>/uploads/<path:filename>')
def download_vault_app_file(app_id, filename):
    if not is_unlocked():
        return redirect(url_for('unlock_page'))
    if app_id not in APP_LAUNCHES:
        return 'Vault app not found', 404
    return send_from_directory(os.path.join(APP_UPLOAD_DIR, app_id), filename)


@app.route('/vault-app/<app_id>/uploads/<path:filename>/delete',
           methods=['POST'])
def delete_vault_app_file(app_id, filename):
    if not is_unlocked():
        return redirect(url_for('unlock_page'))
    if app_id not in APP_LAUNCHES:
        return 'Vault app not found', 404

    safe_name = os.path.basename(filename)
    file_path = os.path.join(APP_UPLOAD_DIR, app_id, safe_name)
    if os.path.isfile(file_path):
        os.remove(file_path)
    return redirect(url_for('vault_app_page', app_id=app_id))


@app.route('/vault-app/<app_id>/items', methods=['POST'])
def add_vault_app_item(app_id):
    if not is_unlocked():
        return redirect(url_for('unlock_page'))

    selected_app = APP_LAUNCHES.get(app_id)
    if not selected_app:
        return 'Vault app not found', 404

    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    if not title or not content:
        return redirect(
            url_for('vault_app_page', app_id=app_id, error='missing'))

    items = load_app_items()
    items[app_id].insert(
        0, {
            'id': uuid.uuid4().hex,
            'title': title,
            'content': content,
            'saved_at': datetime.now(
                timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        })
    save_app_items(items)
    return redirect(url_for('vault_app_page', app_id=app_id))


@app.route('/vault-app/<app_id>/items/<item_id>/delete', methods=['POST'])
def delete_vault_app_item(app_id, item_id):
    if not is_unlocked():
        return redirect(url_for('unlock_page'))
    if app_id not in APP_LAUNCHES:
        return 'Vault app not found', 404

    items = load_app_items()
    items[app_id] = [
        item for item in items[app_id] if item.get('id') != item_id
    ]
    save_app_items(items)
    return redirect(url_for('vault_app_page', app_id=app_id))


@app.route('/logout')
def logout():
    session.pop('vault_unlocked', None)
    return redirect(url_for('unlock_page'))


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if not is_unlocked():
        return redirect(url_for('unlock_page'))

    if request.method == 'GET':
        return render_template('upload.html', error=request.args.get('error'))

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    safe_name = secure_filename(os.path.basename(file.filename))
    if not safe_name:
        return jsonify({'error': 'Invalid file name'}), 400
    ensure_directory(UPLOAD_DIR)
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    try:
        file.save(file_path)
    except OSError:
        return jsonify({'error': 'Could not save file on the server'}), 500
    result = {
        'message': 'File uploaded successfully',
        'file_path': os.path.relpath(file_path, BASE_DIR)
    }
    if not request.headers.get('Accept') or request.headers.get(
            'X-Requested-With'
    ) == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json':
        return jsonify(result), 200
    return redirect(url_for('gallery_page'))


@app.route('/gallery')
def gallery_page():
    if not is_unlocked():
        return redirect(url_for('unlock_page'))

    files = []
    if os.path.isdir(UPLOAD_DIR):
        files = sorted(os.listdir(UPLOAD_DIR))
    return render_template('gallery.html', files=files)


@app.route('/delete/<path:filename>', methods=['POST'])
def delete_file(filename):
    if not is_unlocked():
        return redirect(url_for('unlock_page'))

    file_path = os.path.join(UPLOAD_DIR, os.path.basename(filename))
    if os.path.exists(file_path):
        os.remove(file_path)
    return redirect(url_for('gallery_page'))


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    if not is_unlocked():
        return redirect(url_for('unlock_page'))
    return send_from_directory(UPLOAD_DIR, filename)


@app.route('/camera')
def camera_page():
    if not is_unlocked():
        return redirect(url_for('unlock_page'))
    return render_template('camera.html')


@app.route('/capture', methods=['POST'])
def capture_image():
    if not is_unlocked():
        return redirect(url_for('unlock_page'))

    if 'file' not in request.files:
        return jsonify({'error': 'No captured image'}), 400

    captured_file = request.files['file']
    if captured_file.filename == '':
        return jsonify({'error': 'No captured image'}), 400

    captured_file.save(os.path.join(UPLOAD_DIR, 'camera_capture.jpg'))
    return jsonify({
        'message': 'Image captured successfully',
        'filename': 'camera_capture.jpg'
    }), 200


if __name__ == '__main__':
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    reachable_ip = lan_ip() or '127.0.0.1'
    print(f'Legacy Vault local:  http://127.0.0.1:{port}')
    print(f'Legacy Vault phone:  http://{reachable_ip}:{port}')
    app.run(
        host=host,
        port=port,
        debug=os.environ.get('FLASK_DEBUG') == '1',
    )
