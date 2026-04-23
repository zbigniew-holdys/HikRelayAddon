# Installation Guide — Hikvision Relay Add-on

## Prerequisites

- Home Assistant OS or Supervised (with Supervisor)
- Home Assistant and your Hikvision panel on the **same local network** (or routable network)
- Panel credentials: IP address, username, password

---

## Step 1 — Add custom repository

1. Open Home Assistant → **Settings** → **Add-ons**
2. Click the **three-dot menu** (⋮) in the top-right corner
3. Select **Repositories**
4. Paste the URL and click **Add**:
   ```
   https://github.com/zbigniew-holdys/HikRelayAddon
   ```
5. Close the dialog — the page will refresh and a new section **"Hikvision Relay Add-on"** will appear in the add-on store

---

## Step 2 — Install the add-on

1. Click on **Hikvision Relay** in the add-on store
2. Click **Install** and wait for the image to build (may take 2–5 minutes on first install)

---

## Step 3 — Configure the add-on

1. Go to the add-on page → **Configuration** tab
2. Fill in your device details:

   | Field | Example | Description |
   |---|---|---|
   | `relay_host` | `192.168.1.11` | IP address of your Hikvision panel |
   | `relay_port` | `8000` | Leave as default |
   | `relay_user` | `admin` | Panel login username |
   | `relay_pass` | `your_password` | Panel login password |
   | `relay_0_name` | `Gate` | Name for relay output 0 |
   | `relay_1_name` | `Garage` | Name for relay output 1 |

3. Click **Save**

---

## Step 4 — Start the add-on

1. Go to the **Info** tab
2. Click **Start**
3. Enable **Start on boot** if desired
4. Check the **Log** tab — you should see:
   ```
   [start] Hikvision Relay Server  port=8099
   [start] Relay host: 192.168.1.11:8000  user=admin
   [start] Relays: {0: 'Gate', 1: 'Garage'}
   ```

---

## Step 5 — Configure Home Assistant

### 5a — Add `rest_command` to `configuration.yaml`

```yaml
rest_command:
  trigger_gate:
    url: "http://localhost:8099/api/relay/0"
    method: post
    timeout: 10
  trigger_garage:
    url: "http://localhost:8099/api/relay/1"
    method: post
    timeout: 10
```

### 5b — Add scripts to `scripts.yaml`

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

### 5c — Restart Home Assistant Core

**Settings** → **System** → **Restart Home Assistant**

---

## Step 6 — Add dashboard buttons

1. Open your dashboard → Edit mode → **Add card** → **Button**
2. Set entity to `script.open_gate` or `script.open_garage`
3. Configure icon, name, and tap action to your preference

Or using **Mushroom Cards** (HACS):

```yaml
type: custom:mushroom-entity-card
entity: script.open_gate
name: Gate
icon: mdi:gate
icon_color: green
tap_action:
  action: toggle
```

---

## Verification

Test the add-on directly from a terminal or browser:

```bash
# From HA terminal or SSH add-on:
curl -X POST http://localhost:8099/api/relay/0
# Expected response:
# {"ok": true, "relay": 0, "name": "Gate"}
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Add-on won't start | Image build failed | Check Supervisor logs |
| `SDK directory not found` | Wrong architecture | Open an issue on GitHub |
| `Login SDK failed: 7` | Wrong credentials or IP | Check `relay_host`, `relay_user`, `relay_pass` in config |
| `Login SDK failed: 23` | Device unreachable on port 8000 | Check network/firewall; port 80 is closed on these panels |
| `{"ok": false}` from HA | rest_command URL wrong | Make sure the add-on is running and URL uses `localhost:8099` |

---

## Updating

When a new version is released:

1. **Settings** → **Add-ons** → **Hikvision Relay**
2. Click **Update** (shown when a new version is available)
