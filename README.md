# Hikvision Relay — Home Assistant Add-on

A Home Assistant Supervisor add-on that controls alarm outputs (relay outputs) on **Hikvision DS-KH6320-WTE1** indoor LCD panels directly via the Hikvision binary SDK protocol (port 8000), without needing any intermediate server or cloud tunnel.

## How it works

```
Home Assistant                 Docker container (this add-on)
─────────────────────          ────────────────────────────────────────
rest_command / script ─POST──► :8099/api/relay/0
                                       │
                                       │  Hikvision SDK binary protocol
                                       │  NET_DVR_Login_V30
                                       │  NET_DVR_STDXMLConfig
                                       │  PUT /ISAPI/SecurityCP/control/outputs/0
                                       ▼
                                192.168.x.x:8000 (DS-KH6320-WTE1)
                                       │
                                       ▼
                                  relay coil closes / opens
```

The add-on runs a lightweight Python HTTP server inside a Docker container.
On each trigger call it:
1. Connects to the panel on TCP port 8000 using the Hikvision SDK (`libhcnetsdk.so`)
2. Logs in (`NET_DVR_Login_V30`)
3. Sends an ISAPI `PUT` command via `NET_DVR_STDXMLConfig`
4. Logs out immediately

No persistent session is held — each trigger is a fresh login/logout cycle.

## Why port 8000 and not port 80?

Hikvision indoor panels like DS-KH6320-WTE1 have **port 80 closed** on the network interface.
Port 8000 is the proprietary binary SDK port — the only way to interact with the device programmatically.

## Supported hardware

| Device | Role | Tested |
|--------|------|--------|
| DS-KH6320-WTE1 | Indoor panel (alarmOutNum=2) | ✅ |
| DS-KH8350-WTE1 | Indoor panel | should work |
| Other DS-KH series | Indoor panels | may work |

> This add-on uses the `SecurityCP` ISAPI endpoint for relay control — intended for indoor panels.
> Outdoor door stations (DS-KV series) use a different endpoint (`AccessControl/RemoteControl/door`).

## Supported architectures

| Architecture | Platform |
|---|---|
| `aarch64` | Raspberry Pi 4, Odroid, etc. |
| `amd64` | Generic x86-64 (Intel NUC, VM, etc.) |

The Hikvision SDK binaries for both architectures are bundled inside the add-on image.

## API reference

### `GET /api/relay`

Returns the configured relay names.

```json
{"relays": {"0": "Gate", "1": "Garage"}}
```

### `POST /api/relay/{id}`

Triggers relay `id` (0 or 1).

**Request body** (optional JSON):

| Field | Type | Default | Description |
|---|---|---|---|
| `pulse` | bool | `false` | If true: open → wait → close (one-shot pulse) |
| `duration` | float | `1.0` | Pulse duration in seconds |

**Response — success:**
```json
{"ok": true, "relay": 0, "name": "Gate"}
```

**Response — error:**
```json
{"ok": false, "relay": 0, "error": "Login SDK failed: 7"}
```

## Configuration options

| Option | Type | Description |
|---|---|---|
| `relay_host` | string | IP address of the Hikvision panel |
| `relay_port` | int | SDK port (default: `8000`) |
| `relay_user` | string | Device username (default: `admin`) |
| `relay_pass` | string | Device password |
| `relay_0_name` | string | Label for relay 0 (default: `Gate`) |
| `relay_1_name` | string | Label for relay 1 (default: `Garage`) |

## Home Assistant integration

After installing and starting the add-on, add to `configuration.yaml`:

```yaml
rest_command:
  trigger_gate:
    url: "http://localhost:8765/api/relay/0"
    method: post
    timeout: 10
  trigger_garage:
    url: "http://localhost:8765/api/relay/1"
    method: post
    timeout: 10
```

Optionally create scripts (`scripts.yaml`) for dashboard buttons:

```yaml
open_gate:
  alias: "Gate"
  icon: mdi:gate
  sequence:
    - action: rest_command.trigger_gate
  mode: single

open_garage:
  alias: "Garage"
  icon: mdi:garage-open
  sequence:
    - action: rest_command.trigger_garage
  mode: single
```

See [INSTALL.md](INSTALL.md) for the full step-by-step setup guide.

## Repository structure

```
HikRelayAddon/
├── repository.json              # HA custom repository descriptor
├── setup-sdk.sh                 # Helper to refresh SDK libs from source
└── hikvision-relay/
    ├── config.yaml              # Add-on manifest (name, options, schema, ports)
    ├── build.yaml               # Multi-arch base image selection
    ├── Dockerfile               # Container build instructions
    ├── run.sh                   # Container entrypoint
    ├── relay_server.py          # HTTP API server + SDK wrapper
    └── sdk/
        ├── aarch64/             # Hikvision SDK libs for ARM64
        └── amd64/               # Hikvision SDK libs for x86-64
```

## License

MIT — see [LICENSE](LICENSE).
Hikvision SDK libraries are copyright Hikvision and subject to their own license terms.
