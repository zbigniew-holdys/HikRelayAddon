#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hikvision Relay HTTP API Server — Home Assistant Add-on

Controls alarm outputs on a Hikvision DS-KH6320-WTE1 indoor panel via the
Hikvision binary SDK protocol (port 8000).  Configuration is read from
/data/options.json (injected by HA Supervisor) with fallback to environment
variables.

Endpoints
---------
GET  /              List configured relays (JSON)
GET  /api/relay     Same as above
POST /api/relay/0   Trigger relay 0
POST /api/relay/1   Trigger relay 1

Optional POST body (JSON)
-------------------------
  {"pulse": true, "duration": 1.5}
  pulse=true  — open relay, wait <duration> seconds, then close it
  pulse=false — open relay and leave it open (default)
"""
import ctypes
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---- Configuration: /data/options.json (HA Supervisor) or environment variables ----

_HA_OPTIONS = '/data/options.json'
_opts: dict = {}
if os.path.exists(_HA_OPTIONS):
    try:
        with open(_HA_OPTIONS, encoding='utf-8') as _f:
            _opts = json.load(_f)
    except (OSError, json.JSONDecodeError):
        pass

RELAY_HOST   = _opts.get('relay_host',   os.environ.get('RELAY_HOST',   '192.168.1.100'))
RELAY_PORT   = int(_opts.get('relay_port',   os.environ.get('RELAY_PORT',   '8000')))
RELAY_USER   = _opts.get('relay_user',   os.environ.get('RELAY_USER',   'admin'))
RELAY_PASS   = _opts.get('relay_pass',   os.environ.get('RELAY_PASS',   ''))
RELAY_0_NAME = _opts.get('relay_0_name', os.environ.get('RELAY_0_NAME', 'Gate'))
RELAY_1_NAME = _opts.get('relay_1_name', os.environ.get('RELAY_1_NAME', 'Garage'))
HTTP_PORT    = int(_opts.get('http_port',    os.environ.get('HTTP_PORT',    '8765')))
SDK_DIR      = '/opt/hik-sdk'

RELAY_NAMES  = {0: RELAY_0_NAME, 1: RELAY_1_NAME}

# ---- ctypes: SDK type aliases ----

_BOOL  = ctypes.c_bool
_WORD  = ctypes.c_ushort
_DWORD = ctypes.c_ulong if ctypes.sizeof(ctypes.c_ulong) == 4 else ctypes.c_uint
_LONG  = ctypes.c_long
_BYTE  = ctypes.c_byte


class _DVRInfo(ctypes.Structure):
    _fields_ = [
        ("sSerialNumber",        _BYTE * 48), ("byAlarmInPortNum",     _BYTE),
        ("byAlarmOutPortNum",    _BYTE),      ("byDiskNum",            _BYTE),
        ("byDVRType",            _BYTE),      ("byChanNum",            _BYTE),
        ("byStartChan",          _BYTE),      ("byAudioChanNum",       _BYTE),
        ("byIPChanNum",          _BYTE),      ("byZeroChanNum",        _BYTE),
        ("byMainProto",          _BYTE),      ("bySubProto",           _BYTE),
        ("bySupport",            _BYTE),      ("bySupport1",           _BYTE),
        ("bySupport2",           _BYTE),      ("wDevType",             _WORD),
        ("bySupport3",           _BYTE),      ("byMultiStreamProto",   _BYTE),
        ("byStartDChan",         _BYTE),      ("byStartDTalkChan",     _BYTE),
        ("byHighDChanNum",       _BYTE),      ("bySupport4",           _BYTE),
        ("byLanguageType",       _BYTE),      ("byVoiceInChanNum",     _BYTE),
        ("byStartVoiceInChanNo", _BYTE),      ("byRes3",               _BYTE * 2),
        ("byMirrorChanNum",      _BYTE),      ("wStartMirrorChanNo",   _WORD),
    ]


class _XMLIn(ctypes.Structure):
    _fields_ = [
        ("dwSize",          _DWORD), ("lpRequestUrl",    ctypes.c_void_p),
        ("dwRequestUrlLen", _DWORD), ("lpInBuffer",      ctypes.c_void_p),
        ("dwInBufferSize",  _DWORD), ("dwRecvTimeOut",   _DWORD),
        ("byForceEncrpt",   _BYTE),  ("byRes",           _BYTE * 31),
    ]


class _XMLOut(ctypes.Structure):
    _fields_ = [
        ("dwSize",             _DWORD), ("lpOutBuffer",       ctypes.c_void_p),
        ("dwOutBufferSize",    _DWORD), ("dwReturnedXMLSize", _DWORD),
        ("lpStatusBuffer",     ctypes.c_void_p), ("dwStatusSize", _DWORD),
        ("byRes",              _BYTE * 31),
    ]


# ---- SDK initialisation ----

_relay_sdk:  object  = None
_relay_lock: threading.Lock = threading.Lock()


def _get_sdk():
    global _relay_sdk
    if _relay_sdk is not None:
        return _relay_sdk
    if not os.path.isdir(SDK_DIR):
        raise RuntimeError(f"SDK directory not found: {SDK_DIR}")
    for dep in ("libuuid.so.1", "libhpr.so", "libcrypto.so", "libssl.so", "libHCCore.so"):
        p = os.path.join(SDK_DIR, dep)
        if os.path.exists(p):
            try:
                ctypes.CDLL(p, mode=ctypes.RTLD_GLOBAL)
            except OSError:
                pass
    sdk = ctypes.cdll.LoadLibrary(os.path.join(SDK_DIR, "libhcnetsdk.so"))
    sdk.NET_DVR_Init()
    sdk.NET_DVR_Login_V30.argtypes = [
        ctypes.c_char_p, _WORD, ctypes.c_char_p, ctypes.c_char_p,
        ctypes.POINTER(_DVRInfo),
    ]
    sdk.NET_DVR_Login_V30.restype    = _LONG
    sdk.NET_DVR_Logout_V30.argtypes  = [_LONG]
    sdk.NET_DVR_Logout_V30.restype   = _BOOL
    sdk.NET_DVR_GetLastError.restype = _DWORD
    sdk.NET_DVR_STDXMLConfig.argtypes = [
        _LONG, ctypes.POINTER(_XMLIn), ctypes.POINTER(_XMLOut),
    ]
    sdk.NET_DVR_STDXMLConfig.restype = _BOOL
    _relay_sdk = sdk
    return sdk


def _isapi_call(sdk, uid, method: str, url: str, body: str = ""):
    in_url = f"{method} {url}".encode("ascii")
    body_b = body.encode("ascii")
    inp = _XMLIn()
    inp.dwSize          = ctypes.sizeof(_XMLIn)
    inp.lpRequestUrl    = ctypes.cast(ctypes.c_char_p(in_url), ctypes.c_void_p)
    inp.dwRequestUrlLen = len(in_url)
    inp.lpInBuffer      = ctypes.cast(ctypes.c_char_p(body_b), ctypes.c_void_p)
    inp.dwInBufferSize  = len(body_b)
    BUF = 65536
    out = _XMLOut()
    out.dwSize          = ctypes.sizeof(_XMLOut)
    ob = (ctypes.c_char * BUF)()
    sb = (ctypes.c_char * BUF)()
    out.lpOutBuffer     = ctypes.cast(ob, ctypes.c_void_p)
    out.dwOutBufferSize = BUF
    out.lpStatusBuffer  = ctypes.cast(sb, ctypes.c_void_p)
    out.dwStatusSize    = BUF
    if not sdk.NET_DVR_STDXMLConfig(uid, ctypes.byref(inp), ctypes.byref(out)):
        raise RuntimeError(
            f"SDK error {sdk.NET_DVR_GetLastError()}: {sb.value.decode('utf-8', 'replace')}"
        )


def trigger_relay(relay_id: int, pulse: bool = False, duration: float = 1.0) -> dict:
    name = RELAY_NAMES.get(relay_id, f"relay_{relay_id}")
    try:
        sdk = _get_sdk()
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}
    with _relay_lock:
        dev = _DVRInfo()
        uid = sdk.NET_DVR_Login_V30(
            RELAY_HOST.encode(), RELAY_PORT,
            RELAY_USER.encode(), RELAY_PASS.encode(),
            ctypes.byref(dev),
        )
        if uid < 0:
            return {"ok": False, "error": f"Login SDK failed: {sdk.NET_DVR_GetLastError()}"}
        try:
            url = f"/ISAPI/SecurityCP/control/outputs/{relay_id}?format=json"
            _isapi_call(sdk, uid, "PUT", url, '{"OutputsCtrl":{"switch":"open"}}')
            if pulse:
                time.sleep(max(0.1, duration))
                _isapi_call(sdk, uid, "PUT", url, '{"OutputsCtrl":{"switch":"close"}}')
            print(f"[relay] {relay_id} ({name}) OK  pulse={pulse}", flush=True)
            return {"ok": True, "relay": relay_id, "name": name}
        except RuntimeError as e:
            print(f"[relay] {relay_id} ({name}) ERROR: {e}", flush=True)
            return {"ok": False, "relay": relay_id, "error": str(e)}
        finally:
            sdk.NET_DVR_Logout_V30(uid)


# ---- HTTP request handler ----

class RelayHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[http] {self.address_string()} {fmt % args}", flush=True)

    def do_GET(self):
        if self.path in ('/', '/api/relay'):
            self._json(200, {'relays': {str(k): v for k, v in RELAY_NAMES.items()}})
        else:
            self._json(404, {'error': 'not found'})

    def do_POST(self):
        if not self.path.startswith('/api/relay/'):
            self._json(404, {'error': 'not found'})
            return
        try:
            relay_id = int(self.path.rsplit('/', 1)[-1])
        except ValueError:
            self._json(400, {'error': 'bad relay id'})
            return
        if relay_id not in RELAY_NAMES:
            self._json(404, {'error': 'unknown relay'})
            return
        pulse    = False
        duration = 1.0
        length = int(self.headers.get('Content-Length', 0))
        if length:
            try:
                body = json.loads(self.rfile.read(min(length, 1024)))
                pulse    = bool(body.get('pulse', False))
                duration = float(body.get('duration', 1.0))
            except (json.JSONDecodeError, ValueError):
                pass
        result = trigger_relay(relay_id, pulse=pulse, duration=duration)
        self._json(200 if result['ok'] else 500, result)

    def _json(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    print(f"[start] Hikvision Relay Server  port={HTTP_PORT}", flush=True)
    print(f"[start] Relay host: {RELAY_HOST}:{RELAY_PORT}  user={RELAY_USER}", flush=True)
    print(f"[start] Relays: {RELAY_NAMES}", flush=True)
    print(f"[start] SDK dir: {SDK_DIR}", flush=True)
    server = ThreadingHTTPServer(('0.0.0.0', HTTP_PORT), RelayHandler)
    server.serve_forever()
