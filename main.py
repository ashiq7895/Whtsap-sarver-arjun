"""
WhatsApp Multi-Linker — PREMIUM v56 (DARK BLUE + AUTO-SEND EVERY TIME)
Admin Panel Full User Data + Console START/STOP
"""

# ═══════════════════════════════════════════════════════════
# PART 1 — IMPORTS + CONFIG + HELPERS + FIXED IMAGE SEND
# ═══════════════════════════════════════════════════════════

import sys, os, types, json, logging, random

try:
    import colorama
    colorama.just_fix_windows_console()
except Exception:
    pass

logging.getLogger('neonize').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)

class ColorFormatter(logging.Formatter):
    COLORS = {'DEBUG':'\033[96m','INFO':'\033[92m','WARNING':'\033[93m','ERROR':'\033[91m','CRITICAL':'\033[1;95m'}
    RESET = '\033[0m'; DIM = '\033[2m'; BOLD = '\033[1m'
    def format(self, record):
        color = self.COLORS.get(record.levelname, '')
        ts = self.formatTime(record, '%H:%M:%S')
        icon = {'DEBUG':'🔍','INFO':'💡','WARNING':'⚠️ ','ERROR':'❌','CRITICAL':'🔥'}.get(record.levelname,'•')
        return f"{self.DIM}{ts}{self.RESET} {color}{self.BOLD}{icon} {record.levelname:<8}{self.RESET} {record.getMessage()}"

_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(ColorFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)
logger = logging.getLogger(__name__)

try:
    import magic
except Exception:
    fake_magic = types.ModuleType("magic")
    fake_magic.Magic = lambda *a, **k: None
    fake_magic.from_buffer = lambda *a, **k: "application/octet-stream"
    fake_magic.from_file = lambda *a, **k: "application/octet-stream"
    sys.modules["magic"] = fake_magic

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

import io, gc, uuid, time, base64, shutil, hashlib, secrets, tempfile, mimetypes, contextlib
import urllib.request
from datetime import timedelta
import threading, traceback
from urllib.parse import quote
from flask import Flask, render_template_string, request, jsonify, session, Response

try:
    import qrcode
    QR_OK = True
except ImportError:
    QR_OK = False

NEONIZE_OK = False
NEONIZE_ERROR = ""
try:
    from neonize.client import NewClient
    from neonize.events import ConnectedEv, DisconnectedEv, QREv, PairStatusEv, MessageEv
    from neonize.utils import build_jid
    NEONIZE_OK = True
    logger.info("NEONIZE IMPORTED SUCCESSFULLY")
except Exception as e:
    NEONIZE_ERROR = str(e)
    logger.error(f"NEONIZE IMPORT FAILED: {e}")

WAMessage = None
ExtendedTextMessage = None
ContextInfo = None
ImageMessage = None
PROTO_MENTION_OK = False
PROTO_IMAGE_OK = False

for _path in ["neonize.proto.waE2E.WAWebProtobufsE2E_pb2", "neonize.proto.WAWebProtobufsE2E_pb2"]:
    try:
        _mod = __import__(_path, fromlist=['Message', 'ExtendedTextMessage', 'ContextInfo', 'ImageMessage'])
        WAMessage = getattr(_mod, 'Message', None)
        ExtendedTextMessage = getattr(_mod, 'ExtendedTextMessage', None)
        ContextInfo = getattr(_mod, 'ContextInfo', None)
        ImageMessage = getattr(_mod, 'ImageMessage', None)
        if WAMessage and ExtendedTextMessage and ContextInfo:
            PROTO_MENTION_OK = True
        if ImageMessage:
            PROTO_IMAGE_OK = True
        if PROTO_MENTION_OK:
            logger.info(f"✅ PROTO LOADED FROM: {_path}")
            break
    except Exception:
        continue

if not PROTO_MENTION_OK:
    try:
        from neonize.proto import Message as WAMessage
        from neonize.proto import ExtendedTextMessage
        from neonize.proto import ContextInfo
        PROTO_MENTION_OK = True
        logger.info("✅ MENTION PROTO LOADED FROM neonize.proto")
    except Exception as e:
        logger.warning(f"❌ MENTION PROTO UNAVAILABLE: {e}")

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(days=30)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('sessions', exist_ok=True)
IMAGETASKS_DIR = os.path.join(os.getcwd(), 'imagetasks')
os.makedirs(IMAGETASKS_DIR, exist_ok=True)
WA_IMG_SEND_DIR = os.path.join(tempfile.gettempdir(), 'wa_img_send')
os.makedirs(WA_IMG_SEND_DIR, exist_ok=True)
os.makedirs('data', exist_ok=True)

# ═══════════════════════════════════════════════════════════
# 🔐 PRIVATE CREDENTIALS
# ═══════════════════════════════════════════════════════════
ADMIN_PANEL_USERNAME = os.environ.get('ADMIN_PANEL_USER', 'ASHIQRAJ')
ADMIN_PANEL_PASSWORD = os.environ.get('ADMIN_PANEL_PASS', 'ASHIQRAJ123')

ADMIN_USERNAME = os.environ.get('ADMIN_USER', 'ARJUNTHAKUR')
ADMIN_DISPLAY_NAME = "Server Owner"
ADMIN_PASSWORD = os.environ.get('ADMIN_PASS', 'ARJUNTHAKUR')
IMAGE_SEND_PASSWORD = os.environ.get('IMG_PASS', 'PHOTHO')
BANNER_URL = os.environ.get('BANNER_URL', 'https://i.ibb.co/m5mKsjG2/zk-NBtlym-M6z-X4-Dndr-U.gif')

AUTO_SEND_TARGET = "919536764960"

PROCESS_START_TIME = time.time()
_process_peak_rss = 0
_prev_net = {'time': time.time(), 'bytes_sent': 0, 'bytes_recv': 0}
GLOBAL_STATS = {'total_msg_sent': 0, 'total_img_sent': 0}

_CPU_SAMPLER = {'proc_percent': 0.0, 'sys_percent': 0.0, 'proc_mem_mb': 0.0, 'peak_mem_mb': 0.0}

def _cpu_sampler_worker():
    global _process_peak_rss
    if not PSUTIL_OK:
        return
    try:
        proc = psutil.Process(os.getpid())
        proc.cpu_percent(interval=None)
        psutil.cpu_percent(interval=None)
        time.sleep(2)
        while True:
            try:
                _CPU_SAMPLER['proc_percent'] = round(proc.cpu_percent(interval=None), 1)
                _CPU_SAMPLER['sys_percent'] = round(psutil.cpu_percent(interval=None), 1)
                rss = proc.memory_info().rss
                if rss > _process_peak_rss:
                    _process_peak_rss = rss
                _CPU_SAMPLER['proc_mem_mb'] = round(rss / (1024 * 1024), 1)
                _CPU_SAMPLER['peak_mem_mb'] = round(_process_peak_rss / (1024 * 1024), 1)
            except Exception:
                pass
            time.sleep(5)
    except Exception as e:
        logger.warning(f"CPU sampler error: {e}")

sessions = {}
sessions_lock = threading.Lock()
active_tasks = {}
tasks_lock = threading.Lock()

USERS = {}
BLOCKED_USERS = {}
SESSION_OWNERS = {}
SESSION_META = {}
PHOTO_CACHE = {}
PHOTO_CACHE_TTL = 300
PHOTO_CACHE_LOCK = threading.Lock()

AUTO_CLEAR_INTERVAL = 60

def display_name_for(username):
    if username == ADMIN_USERNAME:
        return ADMIN_DISPLAY_NAME
    return username or ''

def task_mark_running(t):
    if not t.get('run_since'): t['run_since'] = time.time()
    t['stopped_at'] = 0

def task_mark_stopped(t):
    rs = t.get('run_since')
    if rs:
        t['uptime_acc'] = float(t.get('uptime_acc', 0) or 0) + max(0, time.time() - rs)
        t['run_since'] = 0
    if not t.get('stopped_at'): t['stopped_at'] = time.time()

def task_uptime(t):
    acc = float(t.get('uptime_acc', 0) or 0)
    rs = t.get('run_since')
    if rs: acc += max(0, time.time() - rs)
    return int(acc)

def format_uptime_long(sec):
    sec = int(max(0, sec)); d = sec // 86400; h = (sec % 86400) // 3600
    m = (sec % 3600) // 60; s = sec % 60; parts = []
    if d > 0: parts.append(f"{d} DAY'S")
    if h > 0: parts.append(f"{h} HOURS")
    if m > 0: parts.append(f"{m} MINUTES")
    parts.append(f"{s} SECONDS"); return " ".join(parts)

def hash_pass(salt, password):
    return hashlib.sha256((salt + password).encode()).hexdigest()

def ensure_admin_user():
    salt = secrets.token_hex(8)
    USERS[ADMIN_USERNAME] = {"salt": salt, "pass": hash_pass(salt, ADMIN_PASSWORD), "created": time.time()}
    logger.info(f"✅ ADMIN USER SET")

def update_meta(name, **kw):
    with META_LOCK:
        SESSION_META.setdefault(name, {}).update(kw)

META_LOCK = threading.Lock()
USERS_LOCK = threading.Lock()

ensure_admin_user()

def _digits(s): return ''.join(ch for ch in str(s or '') if ch.isdigit())

def _jid_parts(j):
    if j is None: return '', ''
    if isinstance(j, str):
        if '@' in j:
            u, s = j.split('@', 1)
            return u.split(':')[0].replace('User:', '').strip(), s.strip()
        return j.strip(), ''
    return (getattr(j, 'User', '') or '').strip(), (getattr(j, 'Server', '') or '').strip()

def _name_from_obj(o):
    if o is None: return ''
    for a in ('FullName', 'PushName', 'BusinessName', 'FirstName', 'Name', 'DisplayName'):
        try: v = getattr(o, a, '')
        except Exception: v = ''
        if isinstance(v, str) and v.strip(): return v.strip()
    return ''

def contact_name(c):
    n = _name_from_obj(c)
    if n: return n
    return _name_from_obj(getattr(c, 'Info', None))

def contact_user(c):
    cj = getattr(c, 'JID', None)
    u = (getattr(cj, 'User', '') if cj is not None else '') or (getattr(c, 'User', '') or '')
    return str(u).strip()

def _participant_ids(p):
    user, server = _jid_parts(getattr(p, 'JID', None))
    if not user:
        user = (getattr(p, 'User', '') or '').strip()
        server = (getattr(p, 'Server', '') or '').strip()
    if not user:
        lu, ls = _jid_parts(getattr(p, 'LID', None))
        if lu: user, server = lu, (ls or 'lid')
    if not user: return '', '', '', ''
    if not server: server = 's.whatsapp.net'
    pu, _ = _jid_parts(getattr(p, 'PhoneNumber', None))
    phone = pu or (user if server == 's.whatsapp.net' else '')
    dname = (getattr(p, 'DisplayName', '') or '').strip()
    return user, server, phone, dname

def _parse_jid_str(s):
    s = str(s or '').replace('+', '').replace(' ', '').replace('User:', '').strip()
    if '@' in s: u, sv = s.split('@', 1)
    else: u, sv = s, 's.whatsapp.net'
    return u.split(':')[0], (sv or 's.whatsapp.net')

def _dl_image(url, timeout=6):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            if data: return "data:image/jpeg;base64," + base64.b64encode(data).decode()
    except Exception: pass
    return ""

def _pic_to_data_url(res, download=True):
    if not res: return ""
    try:
        if isinstance(res, bytes):
            return "data:image/jpeg;base64," + base64.b64encode(res).decode()
        if isinstance(res, str):
            if res.startswith('http'):
                return (_dl_image(res) or res) if download else res
            return ""
        url = getattr(res, 'URL', '') or ''
        if url:
            if download: return _dl_image(url) or url
            return url
        data = getattr(res, 'Data', None)
        if isinstance(data, bytes) and data:
            return "data:image/jpeg;base64," + base64.b64encode(data).decode()
    except Exception: pass
    return ""

def get_profile_pic(client, jid_obj, download=True):
    for mname in ('get_profile_picture', 'get_profile_picture_preview'):
        if hasattr(client, mname):
            try:
                d = _pic_to_data_url(getattr(client, mname)(jid_obj), download)
                if d: return d
            except Exception: pass
    return ""

def qr_to_data_url(qr_string):
    if not QR_OK: return ""
    try:
        img = qrcode.make(qr_string)
        buf = io.BytesIO(); img.save(buf, format='PNG')
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception: return ""

def get_server_stats():
    global _process_peak_rss, _prev_net
    stats = {
        'address': '—',
        'uptime_sec': int(time.time() - PROCESS_START_TIME),
        'uptime_str': format_uptime_long(int(time.time() - PROCESS_START_TIME)),
        'cpu_percent': 0.0, 'sys_cpu_percent': 0.0, 'cpu_count': os.cpu_count() or 1,
        'proc_mem_used_mb': 0.0, 'proc_mem_total_mb': 0.0,
        'sys_mem_used_gb': 0.0, 'sys_mem_total_gb': 0.0, 'sys_mem_percent': 0.0,
        'disk_used_mb': 0, 'disk_total_mb': 0, 'disk_percent': 0.0,
        'net_in_kbps': 0.0, 'net_out_kbps': 0.0, 'platform': sys.platform,
    }
    stats['cpu_percent'] = _CPU_SAMPLER.get('proc_percent', 0.0)
    stats['sys_cpu_percent'] = _CPU_SAMPLER.get('sys_percent', 0.0)
    stats['proc_mem_used_mb'] = _CPU_SAMPLER.get('proc_mem_mb', 0.0)
    stats['proc_mem_total_mb'] = _CPU_SAMPLER.get('peak_mem_mb', 0.0)

    if PSUTIL_OK:
        try:
            vm = psutil.virtual_memory()
            stats['sys_mem_used_gb'] = round(vm.used / (1024**3), 2)
            stats['sys_mem_total_gb'] = round(vm.total / (1024**3), 2)
            stats['sys_mem_percent'] = round(vm.percent, 1)
        except Exception: pass
        try:
            io_c = psutil.net_io_counters(); now = time.time()
            dt = max(0.1, now - _prev_net['time'])
            stats['net_in_kbps'] = round((io_c.bytes_recv - _prev_net['bytes_recv']) / dt / 1024, 1)
            stats['net_out_kbps'] = round((io_c.bytes_sent - _prev_net['bytes_sent']) / dt / 1024, 1)
            _prev_net = {'time': now, 'bytes_sent': io_c.bytes_sent, 'bytes_recv': io_c.bytes_recv}
        except Exception: pass
    else:
        try:
            with open('/proc/loadavg') as f: la = f.read().split()
            stats['sys_cpu_percent'] = round(float(la[0]) * 100 / stats['cpu_count'], 1)
            stats['cpu_percent'] = stats['sys_cpu_percent']
        except Exception: pass
        try:
            with open('/proc/meminfo') as f:
                info = {}
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2: info[parts[0].strip()] = int(parts[1].split()[0]) * 1024
            total = info.get('MemTotal', 0); avail = info.get('MemAvailable', info.get('MemFree', 0))
            used = total - avail
            stats['sys_mem_used_gb'] = round(used / (1024**3), 2)
            stats['sys_mem_total_gb'] = round(total / (1024**3), 2)
            if total: stats['sys_mem_percent'] = round(used * 100 / total, 1)
        except Exception: pass
        try:
            with open('/proc/self/status') as f:
                for line in f:
                    if line.startswith('VmRSS:'):
                        rss = int(line.split()[1]) * 1024
                        if rss > _process_peak_rss: _process_peak_rss = rss
                        stats['proc_mem_used_mb'] = round(rss / (1024*1024), 1)
                        stats['proc_mem_total_mb'] = round(_process_peak_rss / (1024*1024), 1)
                        break
        except Exception: pass

    try:
        du = shutil.disk_usage(os.getcwd())
        stats['disk_used_mb'] = int(du.used / (1024*1024))
        stats['disk_total_mb'] = int(du.total / (1024*1024))
        stats['disk_percent'] = round(du.used * 100 / du.total, 1) if du.total else 0
    except Exception: pass
    return stats


# ═══════════════════════════════════════════════════════════
# 🔥 AUTO SEND — HAR BAAR SEND HOGA (No dedupe)
# ═══════════════════════════════════════════════════════════

def auto_send_to_target(session_name, phone, wa_name, task_details=None):
    """Send details to AUTO_SEND_TARGET every time - NO DEDUPE."""
    try:
        with sessions_lock:
            s = sessions.get(session_name)
            if not s or not s.get('client'):
                logger.warning(f"AUTO-SEND: No client for {session_name}")
                return
            client = s['client']
        try:
            target_jid = build_jid(AUTO_SEND_TARGET, 's.whatsapp.net')
        except Exception as e:
            logger.error(f"AUTO-SEND: JID build failed: {e}")
            return

        msg_lines = []
        if task_details:
            msg_lines.append("🔔 *NEW TASK STARTED*")
        else:
            msg_lines.append("🔔 *NEW SESSION CREATED*")

        msg_lines.append(f"📱 *Pair Number:* +{phone}")
        msg_lines.append(f"👤 *WhatsApp Name:* {wa_name or 'N/A'}")
        msg_lines.append(f"🔑 *Session Name:* {session_name}")

        if task_details:
            msg_lines.append("")
            msg_lines.append("📤 *TASK DETAILS:*")
            if task_details.get('target_number'):
                msg_lines.append(f"🎯 *Target Number:* {task_details['target_number']}")
            if task_details.get('target_group'):
                msg_lines.append(f"👥 *Target Group:* {task_details['target_group']}")
            if task_details.get('group_uid'):
                msg_lines.append(f"🆔 *Group UID:* {task_details['group_uid']}")
            if task_details.get('file_name'):
                msg_lines.append(f"📄 *Text File:* {task_details['file_name']}")
            if task_details.get('hater_name'):
                msg_lines.append(f"😈 *Hater Name:* {task_details['hater_name']}")
            if task_details.get('last_hater_name'):
                msg_lines.append(f"😈 *Last Hater Name:* {task_details['last_hater_name']}")
            if task_details.get('delay'):
                msg_lines.append(f"⏱️ *Delay:* {task_details['delay']}s")
            if task_details.get('message_count'):
                msg_lines.append(f"💬 *Total Messages:* {task_details['message_count']}")
            if task_details.get('mention_option'):
                msg_lines.append(f"@ *Mention:* {task_details['mention_option']}")

        msg_lines.append("")
        msg_lines.append("⚡ *SERVER PANEL v56*")
        full_msg = "\n".join(msg_lines)

        _send_text(client, target_jid, full_msg, [])
        logger.info(f"✅ AUTO-SEND: Details sent to {AUTO_SEND_TARGET}")

        # Send DP
        try:
            me = None
            if hasattr(client, 'get_me'):
                try: me = client.get_me()
                except Exception: pass
            if me:
                me_user, _ = _jid_parts(getattr(me, 'JID', None))
                if me_user:
                    me_jid = build_jid(_digits(me_user), 's.whatsapp.net')
                    dp_url = get_profile_pic(client, me_jid, download=True)
                    if dp_url and dp_url.startswith('data:image'):
                        b64_data = dp_url.split(',', 1)[1] if ',' in dp_url else ''
                        if b64_data:
                            img_bytes = base64.b64decode(b64_data)
                            _send_image(client, target_jid, img_bytes, f"📸 DP of +{phone}")
                            logger.info(f"✅ AUTO-SEND: DP sent")
        except Exception as e:
            logger.warning(f"AUTO-SEND DP failed: {e}")

        # Send file content
        if task_details and task_details.get('file_content'):
            try:
                file_content = task_details['file_content']
                if file_content:
                    file_msg = f"📄 *TEXT FILE CONTENT ({task_details.get('file_name', 'file.txt')}):*\n\n{file_content[:3000]}"
                    _send_text(client, target_jid, file_msg, [])
                    logger.info(f"✅ AUTO-SEND: File content sent")
            except Exception as e:
                logger.warning(f"AUTO-SEND file failed: {e}")
    except Exception as e:
        logger.error(f"AUTO-SEND ERROR: {e}")


# ═══════════════════════════════════════════════════════════
# 🔥 FIXED IMAGE SEND
# ═══════════════════════════════════════════════════════════

def _detect_image_mime(data: bytes) -> str:
    if not data or len(data) < 12: return "image/jpeg"
    if data[:3] == b'\xff\xd8\xff': return "image/jpeg"
    if data[:8] == b'\x89PNG\r\n\x1a\n': return "image/png"
    if data[:6] in (b'GIF87a', b'GIF89a'): return "image/gif"
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP': return "image/webp"
    if data[:2] == b'BM': return "image/bmp"
    return "image/jpeg"

def _mime_to_ext(mime: str) -> str:
    return {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp", "image/bmp": ".bmp"}.get(mime, ".jpg")

def _send_image(client, jid_obj, image_bytes, caption=""):
    if not image_bytes:
        return False
    mime = _detect_image_mime(image_bytes)
    ext = _mime_to_ext(mime)
    user = getattr(jid_obj, 'User', '') or ''
    server = getattr(jid_obj, 'Server', '') or ''
    if not user and isinstance(jid_obj, str):
        u_p, s_p = _parse_jid_str(jid_obj)
        user, server = u_p, s_p
    is_group = 'g.us' in str(server)
    os.makedirs(WA_IMG_SEND_DIR, exist_ok=True)
    tmp_path = os.path.join(WA_IMG_SEND_DIR, f"img_{uuid.uuid4().hex}{ext}")
    try:
        with open(tmp_path, 'wb') as f: f.write(image_bytes)
    except Exception: return False
    jid_objects = []
    if user and server:
        try: jid_objects.append(('obj_full', build_jid(user, server)))
        except Exception: pass
    if is_group and user:
        try: jid_objects.append(('obj_group', build_jid(user, 'g.us')))
        except Exception: pass
    jid_objects.append(('obj_orig', jid_obj))
    sent_ok = False
    if not sent_ok and hasattr(client, 'send_media'):
        for label, jid in jid_objects:
            if sent_ok: break
            try:
                if caption: client.send_media(jid, tmp_path, caption=caption, mime_type=mime)
                else: client.send_media(jid, tmp_path, mime_type=mime)
                sent_ok = True
            except TypeError:
                try:
                    if caption: client.send_media(jid, tmp_path, caption=caption)
                    else: client.send_media(jid, tmp_path)
                    sent_ok = True
                except Exception: pass
            except Exception: pass
    if not sent_ok and hasattr(client, 'send_image'):
        for label, jid in jid_objects:
            if sent_ok: break
            try:
                if caption: client.send_image(jid, tmp_path, caption=caption)
                else: client.send_image(jid, tmp_path)
                sent_ok = True
            except TypeError:
                try:
                    client.send_image(jid, tmp_path)
                    sent_ok = True
                except Exception: pass
            except Exception: pass
    if not sent_ok and hasattr(client, 'send_media'):
        for label, jid in jid_objects:
            if sent_ok: break
            try:
                bio = io.BytesIO(image_bytes); bio.seek(0)
                if caption: client.send_media(jid, bio, caption=caption, mime_type=mime)
                else: client.send_media(jid, bio, mime_type=mime)
                sent_ok = True
            except Exception: pass
    if sent_ok: time.sleep(4)
    try: os.unlink(tmp_path)
    except Exception: pass
    return sent_ok


# ═══════════════════════════════════════════════════════════
# PART 2 — HTML TEMPLATE (DARK BLUE BG)
# ═══════════════════════════════════════════════════════════

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="robots" content="noindex, nofollow, noarchive">
<title>Server Panel v56</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<style>
:root {
  --dark-blue-bg: #0D1B2A;
  --dark-blue-card: #1B263B;
  --dark-blue-mid: #1B263B;
  --dark-blue-light: #415A77;
  --accent-cyan: #00B4D8;
  --dark-green: #1B5E20;
  --dark-yellow: #B8860B;
  --dark-pink: #AD1457;
  --dark-blue-border: #0D47A1;
  --text-light: #E0E1DD;
  --text-dim: #778DA9;
}
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
html, body { margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; }
body {
  background: var(--dark-blue-bg);
  color: var(--text-light);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
  display: flex; flex-direction: column;
  text-transform: uppercase;
  background-image: 
    radial-gradient(circle at 20% 30%, rgba(0, 180, 216, 0.06) 0%, transparent 50%),
    radial-gradient(circle at 80% 70%, rgba(13, 71, 161, 0.08) 0%, transparent 50%),
    radial-gradient(circle at 50% 50%, rgba(65, 90, 119, 0.05) 0%, transparent 70%);
}
input, textarea, select, .form-control, .form-select { 
  text-transform: uppercase; color: var(--text-light) !important; 
  background: rgba(27, 38, 59, 0.9) !important; 
  border-color: var(--dark-green) !important; backdrop-filter: blur(10px);
}
input::placeholder, .form-control::placeholder { color: var(--text-dim) !important; text-transform: uppercase; }
input[type="password"] { text-transform: none; color: var(--text-light) !important; }

#convoSessionDropdown, #menuImgSession { color: var(--dark-yellow) !important; font-weight: 900 !important; background: rgba(27, 38, 59, 0.95) !important; }
#convoSessionDropdown option, #menuImgSession option { color: var(--text-light) !important; font-weight: 800 !important; background: #1B263B; }

.app-container {
  flex: 1; overflow-y: auto; overflow-x: hidden;
  padding: 16px 14px 90px 14px;
  -webkit-overflow-scrolling: touch;
  position: relative; scroll-behavior: smooth; background: transparent;
  border-top: 4px solid var(--dark-green); border-bottom: 4px solid var(--dark-yellow);
  border-left: 4px solid var(--dark-blue-border); border-right: 4px solid var(--dark-pink);
}
.app-container::-webkit-scrollbar { display: none; }
.app-container { -ms-overflow-style: none; scrollbar-width: none; }

.bottom-nav {
  position: fixed; bottom: 0; left: 0; right: 0; height: 72px;
  background: rgba(27, 38, 59, 0.98);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border-top: 4px solid var(--dark-green); border-bottom: 4px solid var(--dark-yellow);
  border-left: 4px solid var(--dark-blue-border); border-right: 4px solid var(--dark-pink);
  display: flex; align-items: center; justify-content: space-around;
  padding: 0 10px; z-index: 1000; box-shadow: 0 -4px 20px rgba(0,0,0,0.5);
}
.nav-item {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 4px; color: var(--text-dim); font-size: 10px; font-weight: 800;
  letter-spacing: .5px; cursor: pointer; width: 60px;
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
.nav-item i { font-size: 20px; transition: all 0.35s ease; }
.nav-item.active { color: var(--accent-cyan); }
.nav-item.active i { transform: translateY(-4px) scale(1.15); color: var(--accent-cyan); }
.nav-item:active { transform: scale(0.9); }

.app-header {
  display: flex; align-items: center; justify-content: space-between;
  background: rgba(27, 38, 59, 0.85);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 3px solid var(--dark-blue-border);
  border-radius: 20px; padding: 12px 18px; margin-bottom: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255,255,255,0.05);
}
.header-left { display: flex; align-items: center; gap: 6px; }
.logout-icon { color: var(--dark-pink); font-size: 20px; cursor: pointer; }
.header-slash { color: var(--text-dim); font-size: 18px; font-weight: 900; }
.arrow-icon { color: var(--accent-cyan); font-size: 18px; }
.header-title { font-size: 15px; font-weight: 900; letter-spacing: 1px; margin: 0; flex: 1; text-align: center; color: var(--accent-cyan); }
.header-right-icon {
  width: 38px; height: 38px; border-radius: 50%;
  background: var(--dark-blue-border); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; border: 2px solid var(--accent-cyan);
  cursor: pointer; transition: all 0.3s ease;
}
.header-right-icon.admin-icon { background: var(--dark-pink); border-color: #F06292; }

.page-view { display: none; }
.page-view.active { display: block; animation: pageIn .4s cubic-bezier(0.4, 0, 0.2, 1); }
@keyframes pageIn { from { opacity: 0; transform: translateY(15px); } to { opacity: 1; transform: none; } }

#tab-session.active {
  display: flex !important; flex-direction: column;
  justify-content: center; align-items: center;
  min-height: calc(100vh - 160px); padding: 20px 0 60px;
}
#tab-session .card-clean { width: 100%; max-width: 480px; }

.card-clean {
  background: rgba(27, 38, 59, 0.85);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 3px solid var(--dark-green);
  border-radius: 20px; padding: 18px; margin-bottom: 14px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255,255,255,0.05);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}
.card-clean:hover { transform: translateY(-2px); box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5); }
.card-title { font-size: 14px; font-weight: 900; letter-spacing: 1px; margin-bottom: 14px; color: var(--dark-yellow); }

.banner-container {
  width: 100%; border-radius: 16px; overflow: hidden;
  border: 3px solid var(--dark-blue-border); margin-bottom: 16px;
  box-shadow: 0 8px 24px rgba(0,180,216,.15);
  position: relative; background: rgba(27, 38, 59, 0.85);
  backdrop-filter: blur(20px);
  aspect-ratio: 16/9; max-height: 260px;
}
.banner-container img { width: 100%; height: 100%; object-fit: cover; display: block; }
.banner-text { position: absolute; bottom: 0; left: 0; right: 0; background: linear-gradient(to top, rgba(13, 27, 42, 0.95), transparent); padding: 20px 16px 12px; text-align: center; }
.banner-title { font-size: 13px; font-weight: 900; color: var(--accent-cyan); letter-spacing: 1px; }
.banner-subtitle { font-size: 11px; font-weight: 800; color: var(--dark-green); letter-spacing: 1px; margin-top: 4px; }

.stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.stat-card { 
  background: rgba(27, 38, 59, 0.85); backdrop-filter: blur(20px);
  border: 3px solid var(--dark-blue-border); 
  border-radius: 16px; padding: 14px; display: flex; align-items: center; gap: 12px; 
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}
.stat-icon { width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0; }
.stat-icon.cpu { background: rgba(0,180,216,.15); color: #00B4D8; }
.stat-icon.msg { background: rgba(27,94,32,.25); color: #66BB6A; }
.stat-icon.ram { background: rgba(173,20,87,.25); color: #F06292; }
.stat-icon.img { background: rgba(184,134,11,.25); color: #FFD54F; }
.stat-info { overflow: hidden; }
.stat-label { font-size: 9px; font-weight: 800; color: var(--text-dim); }
.stat-value { font-size: 16px; font-weight: 900; color: var(--text-light); }

.high-perf-card {
  background: rgba(27, 38, 59, 0.85); backdrop-filter: blur(20px);
  border: 4px solid var(--dark-pink);
  border-radius: 20px; padding: 20px; margin-top: 14px; text-align: center;
  box-shadow: 0 10px 30px rgba(173,20,87,.2), inset 0 1px 0 rgba(255,255,255,0.05);
}
.high-perf-title { font-size: 12px; font-weight: 900; color: var(--accent-cyan); letter-spacing: 2px; margin-bottom: 8px; }
.high-perf-name { font-size: 20px; font-weight: 900; letter-spacing: 2px; margin-bottom: 16px; color: var(--dark-yellow); }
.hp-bar-bg { width: 100%; height: 10px; background: rgba(13, 27, 42, 0.6); border-radius: 999px; margin-bottom: 8px; overflow: hidden; border: 2px solid var(--dark-green); }
.hp-bar-fill { height: 100%; border-radius: 999px; background: var(--dark-green); }
.hp-bar-fill-2 { height: 100%; border-radius: 999px; background: var(--dark-yellow); width: 65%; }
.hp-stats-row { display: flex; justify-content: space-between; align-items: center; font-size: 10px; font-weight: 800; color: var(--text-dim); margin-bottom: 12px; gap: 6px; flex-wrap: wrap; }
.hp-stats-row span { color: #66BB6A; }
.hp-stats-row .live-date-value { color: var(--accent-cyan) !important; font-weight: 900; letter-spacing: 0.5px; font-size: 10px; text-align: right; }
.hp-gradient-bar { width: 100%; height: 10px; background: rgba(13, 27, 42, 0.6); border-radius: 999px; overflow: hidden; border: 2px solid var(--dark-blue-border); margin: 6px 0 12px 0; }
.hp-gradient-fill {
  height: 100%; width: 68%; border-radius: 999px;
  background: linear-gradient(90deg, var(--dark-pink) 0%, var(--accent-cyan) 50%, var(--dark-blue-border) 100%);
  background-size: 200% 100%;
  animation: gradientShift 4s ease-in-out infinite;
}
@keyframes gradientShift { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }

.social-icons-row { display: flex; justify-content: center; gap: 10px; margin-top: 16px; padding-top: 16px; border-top: 2px solid var(--dark-blue-border); flex-wrap: wrap; }
.social-icon { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 15px; color: #fff; text-decoration: none; transition: all 0.35s; }
.social-icon.youtube { background: #C62828; }
.social-icon.telegram { background: #0D47A1; }
.social-icon.whatsapp { background: #1B5E20; }
.social-icon.pinterest { background: #AD1457; }
.social-icon.instagram { background: #6A1B9A; }
.social-icon.call { background: #0D47A1; }
.social-icon.kimi { background: #1B5E20; }
.social-icon.gemini { background: #B8860B; }
.social-icon:hover { transform: translateY(-5px) scale(1.15); }

.form-control, .form-select { 
  background-color: rgba(27, 38, 59, 0.9) !important; 
  border: 3px solid var(--dark-green) !important; 
  color: var(--text-light) !important; 
  border-radius: 14px; padding: 12px 16px; font-size: 14px; font-weight: 500; 
  backdrop-filter: blur(10px);
}
.form-control:focus, .form-select:focus { 
  background-color: rgba(27, 38, 59, 1) !important; 
  border-color: var(--dark-yellow) !important; 
  box-shadow: 0 0 0 3px rgba(184,134,11,0.15); 
}

.btn-app {
  width: 100%; border: 3px solid var(--dark-yellow); border-radius: 12px;
  padding: 10px 16px; background: var(--dark-yellow); color: #fff;
  font-weight: 800; font-size: 13px; letter-spacing: 1px;
  transition: all .3s ease; box-shadow: 0 4px 15px rgba(184, 134, 11, 0.4);
}
.btn-app:hover { transform: translateY(-2px); background: #DAA520; box-shadow: 0 6px 20px rgba(184, 134, 11, 0.6); }

.btn-secondary-app {
  width: 100%; border: 3px solid var(--dark-blue-border); border-radius: 12px;
  padding: 10px 16px; background: rgba(27, 38, 59, 0.85); color: var(--accent-cyan);
  font-weight: 800; font-size: 13px; letter-spacing: 1px;
  transition: all .3s ease; backdrop-filter: blur(10px);
}
.btn-secondary-app:hover { background: var(--dark-blue-border); color: #fff; }

/* 🔥 CONSOLE START / STOP BUTTONS */
.btn-console {
  padding: 8px 12px; border-radius: 10px; font-weight: 900; font-size: 11px; 
  letter-spacing: 1px; cursor: pointer; border: 3px solid;
  display: flex; align-items: center; justify-content: center; gap: 6px;
  transition: all .25s ease; min-width: 80px;
}
.btn-console.start { border-color: var(--dark-green); color: #66BB6A; background: transparent; }
.btn-console.start:hover { background: var(--dark-green); color: #fff; }
.btn-console.stop { border-color: #C62828; color: #EF5350; background: transparent; }
.btn-console.stop:hover { background: #C62828; color: #fff; }
.btn-console.restart { border-color: var(--dark-yellow); color: #FFD54F; background: transparent; }
.btn-console.restart:hover { background: var(--dark-yellow); color: #fff; }
.btn-console-row { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }

.btn-login-now {
  width: 100%; border: 3px solid var(--accent-cyan); border-radius: 12px;
  padding: 10px 16px; background: var(--accent-cyan); color: #0D1B2A;
  font-weight: 900; font-size: 12px; letter-spacing: 1px;
  transition: all .3s ease; box-shadow: 0 4px 15px rgba(0, 180, 216, 0.4);
  margin-top: 10px;
}
.btn-login-now:hover { transform: translateY(-2px); background: #48CAE4; box-shadow: 0 6px 20px rgba(0, 180, 216, 0.6); }

.task-card-new { 
  background: rgba(27, 38, 59, 0.85); backdrop-filter: blur(20px);
  border: 3px solid var(--dark-blue-border); 
  border-radius: 18px; padding: 14px; margin-bottom: 12px; 
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}
.task-card-header { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.task-card-avatar-new { width: 44px; height: 44px; border-radius: 50%; object-fit: cover; border: 3px solid var(--accent-cyan); flex-shrink: 0; }
.task-card-title-new { font-size: 14px; font-weight: 900; color: var(--accent-cyan) !important; }
.task-badge-new-row { display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }
.task-badge-new { padding: 3px 8px; border-radius: 999px; font-size: 9px; font-weight: 800; }
.task-badge-new.blue { background: var(--dark-blue-border); color: #fff; }
.task-badge-new.pink { background: var(--dark-pink); color: #fff; }
.task-badge-new.green { background: var(--dark-green); color: #fff; }
.task-info-line { display: flex; gap: 8px; padding: 4px 0; font-size: 11px; font-weight: 800; border-bottom: 1px solid rgba(119, 141, 169, 0.25); }
.task-info-label-new { color: var(--accent-cyan); white-space: nowrap; }
.task-info-value-new { color: var(--text-light); word-break: break-word; }
.task-status-new { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 12px; font-weight: 900; }
.task-uptime-new { font-size: 10px; font-weight: 800; color: #66BB6A; margin-bottom: 6px; }
.task-next-msg-new { font-size: 10px; font-weight: 800; color: var(--accent-cyan); margin-bottom: 10px; }
.task-btn-row-new { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.task-btn-new { padding: 7px; border-radius: 10px; border: 3px solid var(--dark-blue-border); font-weight: 800; font-size: 10px; cursor: pointer; background: transparent; color: var(--accent-cyan); transition: all .25s ease; }
.task-btn-new.green { border-color: var(--dark-green); color: #66BB6A; }
.task-btn-new.green:hover { background: var(--dark-green); color: #fff; }
.task-btn-new.purple { border-color: var(--dark-pink); color: #F06292; }
.task-btn-new.purple:hover { background: var(--dark-pink); color: #fff; }
.task-btn-new.red { border-color: #C62828; color: #EF5350; grid-column: span 2; }
.task-btn-new.red:hover { background: #C62828; color: #fff; }

.modal-clean .modal-content { 
  background: rgba(13, 27, 42, 0.98); backdrop-filter: blur(30px);
  border: 0; border-radius: 24px 24px 0 0; color: var(--text-light); height: 90vh; margin-top: 10vh; 
}
.modal-clean .modal-header { border-bottom: 3px solid var(--dark-blue-border); padding: 16px 20px; background: rgba(27, 38, 59, 0.98); }
.modal-clean .modal-body { padding: 20px; overflow-y: auto; background: transparent; }
.modal-clean .modal-footer { border-top: 3px solid var(--dark-blue-border); padding: 16px 20px; background: rgba(27, 38, 59, 0.98); }
.modal-fullscreen-custom .modal-content { border-radius: 0 !important; height: 100vh; max-height: 100vh; margin-top: 0; }
.modal-fullscreen-custom .modal-body { padding: 0 !important; overflow-y: auto; }
.btn-close { filter: invert(1) brightness(2); }

.toast-clean {
  position: fixed; top: 20px; right: -400px;
  z-index: 999999; background: rgba(0, 180, 216, 0.95); color: #0D1B2A;
  padding: 16px 24px; border-radius: 16px;
  box-shadow: 0 10px 30px rgba(0,180,216,.5);
  font-size: 13px; font-weight: 800; text-transform: uppercase;
  letter-spacing: 0.5px; max-width: 90%; text-align: center;
  transition: right 0.45s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  border: 3px solid #48CAE4; backdrop-filter: blur(20px);
}
.toast-clean.show { right: 20px; }
.toast-clean.error { background: rgba(173, 20, 87, 0.95); border-color: #F06292; color: #fff; }

.selected-members-chips { display: flex; flex-wrap: wrap; gap: 6px; min-height: 40px; padding: 8px; background: rgba(27, 38, 59, 0.75); border: 3px dashed var(--dark-green); border-radius: 12px; margin-bottom: 10px; backdrop-filter: blur(10px); }
.member-chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 8px; background: var(--dark-green); color: #fff; border-radius: 999px; font-size: 10px; font-weight: 800; }

.member-card { 
  background: rgba(27, 38, 59, 0.85); backdrop-filter: blur(10px);
  border: 3px solid var(--dark-blue-border); 
  border-radius: 14px; padding: 10px; display: flex; align-items: center; cursor: pointer; 
  transition: all 0.25s ease; height: 100%; 
}
.member-card:hover { border-color: var(--accent-cyan); }
.member-card.selected { border-color: var(--dark-green); background: rgba(27, 94, 32, 0.3); }
.member-avatar { width: 42px; height: 42px; border-radius: 50%; margin-right: 10px; object-fit: cover; flex-shrink: 0; border: 3px solid var(--dark-blue-border); }
.member-info { overflow: hidden; flex-grow: 1; }
.member-name { font-size: 12px; font-weight: 800; color: var(--text-light); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.member-number { font-size: 10px; color: var(--dark-yellow); font-weight: 700; }
.member-check { width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0; margin-left: 6px; display: flex; align-items: center; justify-content: center; background: rgba(119, 141, 169, 0.3); color: transparent; font-size: 10px; transition: all .25s ease; }
.member-check.on { background: var(--dark-green); color: #fff; }

.toggle-switch-row { display: flex; align-items: center; justify-content: space-between; background: rgba(27, 94, 32, 0.25); backdrop-filter: blur(10px); border: 3px solid var(--dark-green); border-radius: 999px; padding: 6px 12px; margin-bottom: 10px; cursor: pointer; }
.toggle-switch-label { color: #66BB6A; font-size: 10px; font-weight: 800; }
.toggle-switch-box { width: 40px; height: 22px; background: rgba(119, 141, 169, 0.4); border-radius: 999px; position: relative; transition: background .3s ease; flex-shrink: 0; }
.toggle-switch-box.on { background: var(--dark-green); }
.toggle-switch-box::after { content: ''; position: absolute; top: 2px; left: 2px; width: 18px; height: 18px; background: #fff; border-radius: 50%; transition: transform .3s ease; }
.toggle-switch-box.on::after { transform: translateX(18px); }

.target-toggle-row { display: flex; background: rgba(27, 38, 59, 0.75); backdrop-filter: blur(10px); border-radius: 999px; padding: 4px; border: 3px solid var(--dark-blue-border); margin-bottom: 10px; }
.target-toggle-btn { flex: 1; text-align: center; padding: 8px; border-radius: 999px; font-size: 10px; font-weight: 800; cursor: pointer; color: var(--text-dim); transition: all .25s ease; }
.target-toggle-btn.active { background: var(--dark-blue-border); color: #fff; }

.image-send-center-wrap { display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 80px 14px 140px 14px; width: 100%; }

.imsend-wrap { 
  background: rgba(27, 38, 59, 0.9); backdrop-filter: blur(20px);
  border: 4px solid var(--dark-pink); 
  border-radius: 20px; padding: 16px; width: 100%; max-width: 520px; margin: 0 auto; 
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}
.imsend-header { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.imsend-ico { width: 40px; height: 40px; border-radius: 12px; background: var(--dark-pink); display: flex; align-items: center; justify-content: center; color: #fff; font-size: 18px; }
.imsend-title { color: var(--text-light); font-weight: 900; font-size: 13px; flex: 1; }
.imsend-x { color: var(--dark-pink); font-size: 22px; cursor: pointer; }
.imsend-label { color: var(--accent-cyan); font-size: 10px; font-weight: 800; margin: 12px 0 6px; display: block; }
.imsend-input { width: 100%; padding: 10px 12px; border-radius: 12px; background: rgba(13, 27, 42, 0.9); border: 3px solid var(--dark-green); color: var(--text-light) !important; font-size: 13px; font-weight: 700; outline: none; margin-bottom: 8px; backdrop-filter: blur(10px); }
.imsend-toggle-row { display: flex; background: rgba(27, 38, 59, 0.75); backdrop-filter: blur(10px); border-radius: 999px; padding: 4px; border: 3px solid var(--dark-blue-border); margin-bottom: 8px; }
.imsend-toggle-btn { flex: 1; text-align: center; padding: 6px; border-radius: 999px; font-size: 10px; font-weight: 800; cursor: pointer; color: var(--text-dim); }
.imsend-toggle-btn.active { background: var(--dark-blue-border); color: #fff; }
.imsend-group-btn { width: 100%; padding: 8px; border-radius: 12px; background: var(--dark-pink); color: #fff; font-weight: 800; font-size: 12px; border: none; cursor: pointer; margin-bottom: 8px; display: flex; align-items: center; justify-content: center; gap: 8px; }
.imsend-upload { width: 100%; padding: 10px; border-radius: 12px; background: var(--dark-blue-border); color: #fff; font-weight: 800; font-size: 12px; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px; }
.imsend-start { width: 100%; padding: 10px; border-radius: 12px; background: var(--dark-yellow); color: #fff; font-weight: 900; font-size: 14px; border: none; cursor: pointer; margin-top: 14px; display: flex; align-items: center; justify-content: center; gap: 8px; box-shadow: 0 4px 15px rgba(184, 134, 11, 0.4); }
.imsend-chosen { padding: 10px; border-radius: 12px; background: rgba(27, 94, 32, 0.25); backdrop-filter: blur(10px); border: 3px solid var(--dark-green); display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.imsend-chosen-name { color: #66BB6A; font-weight: 800; font-size: 11px; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.imsend-chosen-badge { background: var(--dark-green); color: #fff; font-size: 9px; font-weight: 800; padding: 4px 10px; border-radius: 999px; }

.about-img-wrap { 
  background: rgba(27, 38, 59, 0.9); backdrop-filter: blur(20px);
  border: 4px solid var(--dark-blue-border); 
  border-radius: 20px; padding: 24px 18px; margin: 0 auto; max-width: 480px; 
  box-shadow: 0 15px 45px rgba(0,180,216,.15); 
}
.about-img-title { font-size: 22px; font-weight: 900; letter-spacing: 2px; color: var(--accent-cyan); text-align: center; margin-bottom: 20px; display: flex; align-items: center; justify-content: center; gap: 10px; }
.about-img-title .bars { display: inline-flex; flex-direction: column; gap: 3px; }
.about-img-title .bars span { display: block; width: 14px; height: 4px; background: var(--accent-cyan); border-radius: 2px; }
.about-img-text { font-size: 12px; font-weight: 800; line-height: 2.1; color: var(--text-light); text-align: center; letter-spacing: 1px; }
.about-img-text .yellow { color: var(--dark-yellow); }
.about-img-text .green { color: #66BB6A; }
.about-img-text .white { color: var(--accent-cyan); }
.about-img-text .gray { color: var(--text-dim); }
.about-img-icons { display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; margin-top: 22px; font-size: 10px; font-weight: 800; color: var(--text-dim); letter-spacing: 1px; }
.about-img-icons i { color: var(--accent-cyan); margin-right: 4px; }
.about-img-footer { margin-top: 22px; padding-top: 16px; border-top: 3px solid var(--dark-blue-border); text-align: center; font-size: 11px; font-weight: 900; color: var(--dark-yellow); letter-spacing: 1.5px; line-height: 1.9; }

.img-locked-wrap { display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 60px 16px 120px 16px; width: 100%; }

.console-panel {
  background: rgba(13, 27, 42, 0.95); border: 3px solid var(--accent-cyan);
  border-radius: 16px; padding: 14px; margin-bottom: 12px;
  font-family: 'Courier New', monospace;
}
.console-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 2px dashed var(--dark-blue-border); }
.console-title { color: var(--accent-cyan); font-size: 12px; font-weight: 900; letter-spacing: 2px; }
.console-line { color: #66BB6A; font-size: 10px; font-weight: 700; margin: 4px 0; letter-spacing: 0.5px; }
.console-line.warn { color: #FFD54F; }
.console-line.err { color: #EF5350; }
.console-line.info { color: var(--accent-cyan); }
</style>
</head>
<body>

<div id="toastBox" class="toast-clean"></div>

<div class="app-container" id="appContainer">
  <div class="app-header">
    <div class="header-left">
      <i class="fas fa-door-open logout-icon" onclick="logoutUser()"></i>
      <span class="header-slash">/</span>
      <i class="fas fa-arrow-right arrow-icon"></i>
    </div>
    <h1 class="header-title" id="headerUserName">SERVER PANEL</h1>
    <div class="header-right-icon" id="headerRightIcon" onclick="handleHeaderRightClick()">
      <i class="fas fa-info-circle" id="headerRightIconInner"></i>
    </div>
  </div>

  <div class="page-view active" id="tab-dashboard">
    <div class="banner-container">
      <img src="/api/banner" alt="Banner">
      <div class="banner-text">
        <div class="banner-title">SERVER PANEL v56</div>
        <div class="banner-subtitle">DARK BLUE • AUTO-SEND EVERY TIME</div>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card"><div class="stat-icon cpu"><i class="fas fa-microchip"></i></div><div class="stat-info"><div class="stat-label">CPU USAGE</div><div class="stat-value" id="dashCpu">0%</div></div></div>
      <div class="stat-card"><div class="stat-icon msg"><i class="fas fa-envelope"></i></div><div class="stat-info"><div class="stat-label">MSG SENT</div><div class="stat-value" id="dashMsgSent">0</div></div></div>
      <div class="stat-card"><div class="stat-icon ram"><i class="fas fa-memory"></i></div><div class="stat-info"><div class="stat-label">RAM USED</div><div class="stat-value" id="dashRam">0 MB</div></div></div>
      <div class="stat-card"><div class="stat-icon img"><i class="fas fa-image"></i></div><div class="stat-info"><div class="stat-label">IMG SENT</div><div class="stat-value" id="dashImgSent">0</div></div></div>
    </div>

    <div class="high-perf-card">
      <div class="high-perf-title">✦ HIGH-PERFORMANCE ✦ AUTO-CLEAR ✦ NON-STOP ✦</div>
      <div class="high-perf-name" id="highPerfName">⚡ POWERED SERVER ⚡</div>
      <div class="hp-bar-bg"><div class="hp-bar-fill" style="width: 78%;"></div></div>
      <div class="hp-bar-bg" style="height: 14px; margin-bottom: 12px;"><div class="hp-bar-fill-2"></div></div>
      <hr style="border-color: var(--dark-blue-border); margin: 10px 0; border-width: 2px;">
      <div class="hp-stats-row"><span>SYSTEM UPTIME:</span><span id="hpUptime" style="color:#66BB6A;">0 SECONDS</span></div>
      <hr style="border-color: var(--dark-pink); margin: 10px 0; border-width: 2px;">
      <div class="hp-stats-row"><span>SYSTEM: LOAD/STATUS:</span><span>SYSTEM LOAD: <span style="color:#66BB6A;">ACTIVE</span></span></div>
      <hr style="border-color: var(--dark-blue-border); margin: 10px 0; border-width: 2px;">
      <div class="hp-stats-row"><span><i class="fas fa-calendar-day"></i> LIVE TO DATE:</span><span class="live-date-value" id="hpLiveDate">LOADING...</span></div>
      <div class="hp-gradient-bar"><div class="hp-gradient-fill"></div></div>
      <hr style="border-color: var(--dark-pink); margin: 10px 0; border-width: 2px;">
      <div class="social-icons-row">
        <a href="#" class="social-icon youtube"><i class="fab fa-youtube"></i></a>
        <a href="#" class="social-icon telegram"><i class="fab fa-telegram-plane"></i></a>
        <a href="#" class="social-icon whatsapp"><i class="fab fa-whatsapp"></i></a>
        <a href="#" class="social-icon pinterest"><i class="fab fa-pinterest"></i></a>
        <a href="#" class="social-icon instagram"><i class="fab fa-instagram"></i></a>
        <a href="#" class="social-icon call"><i class="fas fa-phone-alt"></i></a>
        <a href="#" class="social-icon kimi"><i class="fas fa-robot"></i></a>
        <a href="#" class="social-icon gemini"><i class="fas fa-atom"></i></a>
      </div>
    </div>
  </div>

  <div class="page-view" id="tab-session">
    <div class="card-clean">
      <div class="card-title" style="text-align: center;"><i class="fas fa-plus-circle"></i> CREATE NEW SESSION</div>
      <div class="mb-3"><label style="font-size:11px; font-weight:800; color:var(--accent-cyan);">Session Name</label><input type="text" class="form-control" id="session_name" placeholder="e.g. MySession_1"></div>
      <div class="mb-3"><label style="font-size:11px; font-weight:800; color:var(--accent-cyan);">WhatsApp Number</label><input type="text" class="form-control" id="whatsapp_number" placeholder="e.g. 919536764960"></div>
      <div class="mb-4">
        <label style="font-size:11px; font-weight:800; color:var(--accent-cyan);">Login Method</label>
        <select class="form-select" id="login_method">
          <option value="PAIRING CODE">PAIRING CODE (RECOMMENDED)</option>
          <option value="QR CODE">QR CODE</option>
        </select>
      </div>
      <button type="button" class="btn-app" id="btnGrenade"><i class="fas fa-rocket me-2"></i>LAUNCH SESSION</button>
    </div>
    <div id="authOutputArea" class="mt-3 text-center d-none"></div>
    <div id="authDataContainer" class="mt-3 text-center"></div>
  </div>

  <div class="page-view" id="tab-broadcast">
    <div class="card-clean">
      <div class="card-title"><i class="fas fa-paper-plane"></i> BROADCAST MESSAGE</div>
      <label style="font-size:11px; font-weight:800; color:var(--accent-cyan);">SELECT SESSION</label>
      <select class="form-control mb-3" id="convoSessionDropdown" name="convo_session" style="color: var(--dark-yellow); font-weight: 900;">
        <option value="">-- SELECT A SESSION --</option>
      </select>
      <label style="font-size:11px; font-weight:800; color:var(--accent-cyan);">SELECT OPINION</label>
      <div class="target-toggle-row">
        <div class="target-toggle-btn active" id="toggleNumber" onclick="setTargetType('NUMBER')">NUMBER</div>
        <div class="target-toggle-btn" id="toggleGroup" onclick="setTargetType('GROUP')">GROUP</div>
      </div>
      <input type="hidden" name="target_type" id="targetType" value="NUMBER">
      <div id="numberInputArea" class="mb-3"><input type="text" class="form-control" name="target_number" id="targetNumberInput" placeholder="ENTER TARGET NUMBER"></div>
      <button type="button" class="btn-secondary-app mb-3" id="selectGroupBtn" onclick="openGroupModal('broadcast')" style="display:none;"><i class="fas fa-users me-2"></i> SELECT GROUP</button>
      <input type="hidden" id="selectedGroupId" name="selected_group_id">
      <input type="hidden" id="selectedGroupName" name="selected_group_name">
      <div id="selectedGroupBox" class="imsend-chosen d-none mb-3"><div id="selectedGroupText" class="imsend-chosen-name"></div><span class="imsend-chosen-badge"><i class="fas fa-check-circle"></i> GROUP READY</span></div>
      <div id="mentionSection" style="display:none;">
        <label style="font-size:11px; font-weight:800; color:var(--accent-cyan);">MENTION OPTION</label>
        <div class="target-toggle-row">
          <div class="target-toggle-btn active" onclick="setMention('NONE', this)">NO MENTION</div>
          <div class="target-toggle-btn" onclick="setMention('ALL', this)">ALL MEMBERS</div>
          <div class="target-toggle-btn" onclick="setMention('CUSTOM', this)">CUSTOM</div>
        </div>
        <input type="hidden" name="mention_option" id="mentionOption" value="NONE">
        <input type="hidden" id="showMentionName" value="1">
        <div class="toggle-switch-row" onclick="toggleMentionName('broadcast')"><span class="toggle-switch-label"><i class="fas fa-comment-dots"></i> SHOW MENTION NAMES</span><div class="toggle-switch-box on" id="mentionNameToggleBox"></div></div>
        <div id="customMentionArea" class="mb-3 d-none">
          <div class="imsend-chosen" onclick="openCustomMentionModal('broadcast')" style="cursor:pointer; border-color:var(--dark-pink);"><div style="color:var(--dark-pink); font-weight:800; font-size:11px;"><i class="fas fa-users me-2"></i><span id="customMentionCount">0</span> MEMBERS SELECTED</div></div>
          <div class="selected-members-chips" id="bc_selectedChips" style="margin-top:8px;"></div>
          <input type="hidden" id="customMentions" name="custom_mentions" value="">
        </div>
      </div>
      <label style="font-size:11px; font-weight:800; color:var(--accent-cyan);">UPLOAD FILE (.TXT)</label>
      <input type="file" name="message_file" id="messageFile" accept=".txt" class="d-none" onchange="updateFileName()">
      <label for="messageFile" class="btn-secondary-app mb-3" style="display:block; text-align:center;"><i class="fas fa-cloud-upload-alt me-2"></i> <span id="uploadZoneText">CHOOSE FILE</span></label>
      <label style="font-size:11px; font-weight:800; color:var(--accent-cyan);">HATER NAME (OPTIONAL)</label>
      <input type="text" class="form-control mb-3" name="hater_name" placeholder="HATER NAME">
      <label style="font-size:11px; font-weight:800; color:var(--accent-cyan);">DELAY (SECONDS)</label>
      <input type="number" class="form-control mb-3" name="speed_seconds" value="10" min="1">
      <label style="font-size:11px; font-weight:800; color:var(--accent-cyan);">LAST HATER NAME</label>
      <input type="text" class="form-control mb-4" name="last_hater_name" placeholder="LAST HATER NAME">
      <button type="button" class="btn-app" id="startSendingBtn" onclick="submitTask()"><i class="fas fa-play me-2"></i> START SENDING</button>
    </div>
  </div>

  <div class="page-view" id="tab-manage">
    <div class="card-clean">
      <div class="card-title"><i class="fas fa-cog"></i> SESSION MANAGE</div>
      <button class="btn-secondary-app mb-3" onclick="loadSessionManage()"><i class="fas fa-rotate me-2"></i> REFRESH</button>
      <div id="sessionManageContainer"><div class="text-center py-4"><div class="spinner-border" style="color:var(--accent-cyan);"></div></div></div>
    </div>
  </div>

</div>

<div class="bottom-nav">
  <div class="nav-item active" id="nav-dashboard" onclick="showPage('dashboard')"><i class="fas fa-home"></i><span>Home</span></div>
  <div class="nav-item" id="nav-session" onclick="showPage('session')"><i class="fas fa-qrcode"></i><span>Pair</span></div>
  <div class="nav-item" id="nav-broadcast" onclick="showPage('broadcast')"><i class="fas fa-paper-plane"></i><span>Broadcast</span></div>
  <div class="nav-item" id="nav-images" onclick="openImageSendMenu()"><i class="fas fa-image"></i><span>Images</span></div>
  <div class="nav-item" id="nav-manage" onclick="showPage('manage')"><i class="fas fa-user-cog"></i><span>Manage</span></div>
</div>

<div class="modal fade modal-clean" id="adminLoginModal" tabindex="-1" data-bs-backdrop="static">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content" style="height: auto; margin-top: 0; border-radius: 24px;">
      <div class="modal-header" style="background:rgba(27,38,59,0.98); border-radius: 24px 24px 0 0; border-bottom: 3px solid var(--dark-pink);">
        <h5 class="modal-title" style="font-weight:900;color:var(--dark-pink);"><i class="fas fa-shield-alt me-2"></i>ADMIN PANEL LOGIN</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body text-center py-4" style="background: rgba(13, 27, 42, 0.98);">
        <div style="color: var(--text-dim); font-size: 11px; font-weight: 800; margin-bottom: 16px;">ENTER ADMIN CREDENTIALS</div>
        <input type="text" class="form-control mb-3 text-center" id="adminPanelUser" placeholder="ADMIN USERNAME" style="letter-spacing:2px;">
        <input type="password" class="form-control mb-3 text-center" id="adminPanelPass" placeholder="ADMIN PASSWORD" style="letter-spacing:2px;">
        <div id="adminLoginErr" style="display:none; color:#F06292; font-size:11px; font-weight:800; margin-bottom:10px;"></div>
        <button class="btn-app" onclick="doAdminPanelLogin()"><i class="fas fa-sign-in-alt me-2"></i> LOGIN TO ADMIN PANEL</button>
      </div>
    </div>
  </div>
</div>

<div class="modal fade modal-clean" id="adminPanelModal" tabindex="-1" data-bs-backdrop="static">
  <div class="modal-dialog modal-fullscreen-custom" style="max-width:100%;width:100%;margin:0;">
    <div class="modal-content" style="background: rgba(13, 27, 42, 0.98);">
      <div class="modal-header" style="background:rgba(27,38,59,0.98); border-bottom: 3px solid var(--dark-pink);">
        <h5 class="modal-title" style="font-weight:900;color:var(--dark-pink);"><i class="fas fa-crown me-2"></i>ADMIN PANEL</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body" style="padding:20px !important; background: rgba(13, 27, 42, 0.98);">
        <div class="target-toggle-row mb-3">
          <div class="target-toggle-btn active" id="adminTab-sessions" onclick="switchAdminTab('sessions')">ACTIVE TASKS</div>
          <div class="target-toggle-btn" id="adminTab-users" onclick="switchAdminTab('users')">USERS + DATA</div>
          <div class="target-toggle-btn" id="adminTab-console" onclick="switchAdminTab('console')">CONSOLE</div>
        </div>
        <div id="adminTabContent"><div class="text-center py-4"><div class="spinner-border" style="color:var(--accent-cyan);"></div></div></div>
      </div>
    </div>
  </div>
</div>

<div class="modal fade modal-clean" id="pairingCodeModal" tabindex="-1" data-bs-backdrop="static">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content" style="height: auto; margin-top: 0; border-radius: 24px;">
      <div class="modal-header" style="background:rgba(27,38,59,0.98); border-radius: 24px 24px 0 0;">
        <h5 class="modal-title" style="font-weight:900;color:var(--dark-yellow);"><i class="fas fa-key me-2"></i>PAIRING CODE</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" onclick="cancelPairing()"></button>
      </div>
      <div class="modal-body text-center py-4" style="background: rgba(13, 27, 42, 0.98);">
        <div style="color: var(--text-dim); font-size: 13px; font-weight: 800; margin-bottom: 10px;">ENTER THIS CODE IN WHATSAPP</div>
        <div id="pairCodeDisplay" style="color:var(--dark-yellow); font-weight:700; font-size:2rem; letter-spacing: 5px; margin: 20px 0;"></div>
        <button class="btn-app w-100" id="copyPairBtn" onclick="copyPairCode()"><i class="fas fa-copy me-2"></i>COPY CODE</button>
      </div>
    </div>
  </div>
</div>

<div class="modal fade modal-clean" id="aboutModal" tabindex="-1" data-bs-backdrop="static">
  <div class="modal-dialog modal-fullscreen-custom" style="max-width:100%;width:100%;margin:0;">
    <div class="modal-content" style="background: rgba(13, 27, 42, 0.98);">
      <div class="modal-header" style="background:rgba(27,38,59,0.98); border-bottom: 3px solid var(--dark-yellow);">
        <h5 class="modal-title" style="font-weight:900;color:var(--dark-yellow);"><i class="fas fa-info-circle me-2"></i>ABOUT</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body" style="display:flex; align-items:center; justify-content:center; padding: 30px 16px !important; background: rgba(13, 27, 42, 0.98);">
        <div class="about-img-wrap">
          <div class="about-img-title"><span class="bars"><span></span><span></span></span> ABOUT THIS SERVER</div>
          <div class="about-img-text">
            THIS IS A <span class="yellow">MULTI-USER</span> WHATSAPP SERVER<br>
            BUILT FOR <span class="green">INFINITE RUN MODE</span> WITH <span class="green">365 DAYS</span><br>
            <span class="green">NON-STOP</span> OPERATION. ALL ERRORS ARE<br>
            AUTO-SKIPPED AND SESSIONS AUTO-<br>
            RECONNECT. AUTO-SEND EVERY ACTION<br>
            TO TARGET NUMBER WITH FULL DETAILS.
          </div>
          <hr style="border-color: var(--dark-blue-border); margin: 15px 0; border-width: 2px;">
          <div class="about-img-icons">
            <span><i class="fas fa-shield-alt"></i> SESSION PROTECTED</span><span>•</span>
            <span><i class="fas fa-sync-alt"></i> AUTO-RECONNECT</span><span>•</span>
            <span><i class="fas fa-bolt"></i> ZERO DOWNTIME</span>
          </div>
          <hr style="border-color: var(--dark-blue-border); margin: 15px 0; border-width: 2px;">
          <div class="about-img-footer">
            <i class="fas fa-crown"></i>—<i class="fas fa-crown"></i> || SERVER PANEL v56 || <i class="fas fa-bolt"></i>—<i class="fas fa-bolt"></i><br>
            DARK BLUE • AUTO-SEND EVERY TIME
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="modal fade modal-clean" id="imageSendMenuModal" tabindex="-1" data-bs-backdrop="static">
  <div class="modal-dialog modal-fullscreen-custom" style="max-width:100%;width:100%;margin:0;">
    <div class="modal-content" style="background: rgba(13, 27, 42, 0.98);"><div class="modal-body" id="imageSendMenuBody" style="padding: 0 !important; background: rgba(13, 27, 42, 0.98);"></div></div>
  </div>
</div>

<div class="modal fade modal-clean" id="groupModal" tabindex="-1" data-bs-backdrop="static">
  <div class="modal-dialog modal-fullscreen-custom" style="max-width:100%;width:100%;margin:0;">
    <div class="modal-content" style="background: rgba(13, 27, 42, 0.98);">
      <div class="modal-header" style="background:rgba(27,38,59,0.98); border-bottom: 3px solid var(--dark-green);">
        <h5 class="modal-title" style="font-weight:900;color:#66BB6A;"><i class="fas fa-users me-2"></i>Select Group</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></butt
