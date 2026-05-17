# Remote Access via Tailscale

The gallery and API run on your local machine. Tailscale lets you reach them from any device — phone, tablet, laptop — without configuring port forwarding or exposing anything to the public internet.

---

## Install Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

Or follow the official docs: https://tailscale.com/download/linux

---

## Connect to your Tailscale network

```bash
sudo tailscale up
```

This opens a browser to authenticate. Sign in with your Tailscale account (Google, GitHub, or Microsoft). After auth the machine appears in your Tailscale admin console.

---

## Find your Tailscale IP

```bash
tailscale ip -4
```

Example output: `100.107.100.63`

This IP is stable — it does not change between reboots unless you explicitly remove and re-add the machine.

---

## Start the servers

```bash
~/projects/Houdini-PC-pipeline/start.sh
```

Both servers bind to `0.0.0.0`, which means they listen on all interfaces including the Tailscale one.

---

## Access from another device

The other device must also have Tailscale installed and be signed into the same account (or an account in your Tailscale organisation).

| URL | What it opens |
|-----|---------------|
| `http://100.107.100.63:5173` | Web gallery |
| `http://100.107.100.63:8765/api/health` | API health check |
| `http://100.107.100.63:8765/api/publishes` | Raw publish JSON |

Replace `100.107.100.63` with your actual Tailscale IP from `tailscale ip -4`.

---

## Phone and tablet

The gallery is usable in any modern mobile browser. Open `http://<tailscale-ip>:5173` in Safari (iOS) or Chrome (Android).

Recommended browsers:
- Safari 16+ on iOS
- Chrome 110+ on Android

The gallery layout responds to viewport width. On narrow screens the sidebar collapses and the detail panel opens full-width.

---

## Verify connectivity

From the remote device:

```bash
curl http://100.107.100.63:8765/api/health
# expected: {"status": "ok"}
```

From your Linux machine:

```bash
tailscale status         # shows connected peers
ping 100.107.100.63      # should reply from yourself
```

---

## Troubleshooting

### "Connection refused" on port 5173 or 8765

1. Verify the servers are running: `ps aux | grep -E "uvicorn|vite"`
2. Verify the servers are listening on all interfaces: `ss -tlnp | grep -E "5173|8765"` — should show `0.0.0.0` not `127.0.0.1`
3. Check `start.sh` passes `--host 0.0.0.0` to both servers

### "Connection timed out"

1. Check Tailscale is connected: `tailscale status`
2. If the machine shows as offline in `tailscale status`, run `sudo tailscale up` again
3. Confirm the remote device is on the same Tailscale network: `tailscale status` on the remote device

### Firewall blocking connections

Pop!_OS does not have an active firewall by default. If you have `ufw` or `firewalld` enabled:

```bash
# ufw
sudo ufw allow 5173/tcp
sudo ufw allow 8765/tcp

# firewalld
sudo firewall-cmd --add-port=5173/tcp --permanent
sudo firewall-cmd --add-port=8765/tcp --permanent
sudo firewall-cmd --reload
```

### Tailscale not starting on boot

```bash
sudo systemctl enable --now tailscaled
```

### Slow gallery on mobile

The gallery lazy-loads heavy 3D viewers (Three.js). On first load of the **3D Assets** surface there may be a delay while the JS bundle downloads. Subsequent loads use the browser cache.

If thumbnails or videos are slow: the bottleneck is the Tailscale connection speed. On the same LAN this is typically not an issue. Over the internet Tailscale routes directly between peers when possible (DERP relay otherwise).

---

## Security notes

- Tailscale uses WireGuard end-to-end encryption. Traffic between devices is encrypted and authenticated.
- Only devices signed into your Tailscale account can reach your machine's Tailscale IP.
- The pipeline servers have no authentication of their own — anyone on your Tailscale network can read all publish data. For a solo artist this is not a concern.
- The servers are not reachable from the public internet (no port forwarding, no public IP involved).

---

## Using the Gallery Server shelf tool

Inside Houdini, the **Gallery Server** shelf button starts both servers and opens the gallery in your default browser. It also prints the Tailscale URL to the Houdini console if Tailscale is running:

```python
import subprocess
ip = subprocess.check_output(["tailscale", "ip", "-4"]).decode().strip()
print(f"Remote URL: http://{ip}:5173")
```

This saves the step of looking up the IP manually.
