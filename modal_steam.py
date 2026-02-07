"""
Cloud Gaming on Modal.com

Tu dong cai dat Tailscale + Sunshine + Steam de choi game tren Modal.
Dung Modal Sandbox (interactive GPU container, toi da 24 tieng).

Yeu cau:
- Modal account (https://modal.com) da set up billing
- pip install modal && modal setup
- Tailscale account (https://tailscale.com)
- Moonlight client (https://moonlight-stream.org)

Cach dung:
    pip install modal
    modal setup
    python modal_steam.py              # Mac dinh: GPU T4
    python modal_steam.py --gpu L4     # Dung GPU L4
    python modal_steam.py --gpu A10G   # Dung GPU A10G
    python modal_steam.py --gpu L40S   # Dung GPU L40S

GPU duoc ho tro va chi phi uoc tinh:
    T4   : ~$0.59/h  | 16 GB VRAM | Re nhat, choi game nhe
    L4   : ~$0.80/h  | 24 GB VRAM | Tot hon T4, hieu qua
    A10G : ~$1.10/h  | 24 GB VRAM | Manh, co RT cores
    L40S : ~$1.95/h  | 48 GB VRAM | Rat manh, game nang
    A100 : ~$3.73/h  | 40/80 GB   | Cuc manh (thuong dung AI)
    H100 : ~$4.98/h  | 80 GB      | Manh nhat
"""

import modal
import sys
import signal
import time
import argparse

GPU_OPTIONS = {
    "T4":   {"price": "~$0.59/h", "vram": "16 GB"},
    "L4":   {"price": "~$0.80/h", "vram": "24 GB"},
    "A10G": {"price": "~$1.10/h", "vram": "24 GB"},
    "L40S": {"price": "~$1.95/h", "vram": "48 GB"},
    "A100": {"price": "~$3.73/h", "vram": "40/80 GB"},
    "H100": {"price": "~$4.98/h", "vram": "80 GB"},
}

DEFAULT_GPU = "T4"
TIMEOUT_SECONDS = 14400       # 4 tieng toi da
IDLE_TIMEOUT_SECONDS = 1800   # 30 phut khong hoat dong -> tu dong tat

image = (
    modal.Image.from_registry("ubuntu:22.04")
    .apt_install(
        "wget", "curl", "sudo", "gnupg2", "lsb-release",
        "xvfb", "xfce4", "xfce4-terminal", "dbus-x11",
        "x11-utils", "x11-xserver-utils", "xdg-utils",
        "libvulkan1", "mesa-vulkan-drivers", "vulkan-tools",
        "libgl1-mesa-dri", "libgl1-mesa-glx", "libegl1-mesa",
        "libgbm1", "libgles2-mesa", "libnss3",
        "libatk1.0-0", "libatk-bridge2.0-0", "libcups2", "libdrm2",
        "libxkbcommon0", "libxcomposite1", "libxdamage1", "libxrandr2",
        "libpango-1.0-0", "libcairo2", "libasound2",
        "libpulse0", "pulseaudio",
        "ca-certificates", "locales", "software-properties-common",
        "kmod", "iproute2", "iptables", "net-tools",
        "lib32gcc-s1", "lib32stdc++6",
        "libxcb1", "libxcb-xfixes0", "libxcb-shape0",
        "libxcb-shm0", "libxcb-randr0", "libxcb-image0",
    )
    .run_commands(
        "locale-gen en_US.UTF-8",
        "update-locale LANG=en_US.UTF-8",
    )
    .run_commands(
        "curl -fsSL https://tailscale.com/install.sh | sh",
    )
    .run_commands(
        "dpkg --add-architecture i386",
        "apt-get update -qq",
    )
    .run_commands(
        "wget -q https://github.com/LizardByte/Sunshine/releases/latest/download/sunshine-ubuntu-22.04-amd64.deb -O /tmp/sunshine.deb",
        "apt-get install -y -f /tmp/sunshine.deb || true",
        "rm -f /tmp/sunshine.deb",
    )
    .run_commands(
        "wget -q https://cdn.cloudflare.steamstatic.com/client/installer/steam.deb -O /tmp/steam.deb",
        "dpkg -i /tmp/steam.deb || true",
        "apt-get install -y -f || true",
        "rm -f /tmp/steam.deb",
    )
)

volume = modal.Volume.from_name("cloud-gaming-data", create_if_missing=True)

SETUP_SCRIPT = r"""#!/bin/bash
set -e

export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export DISPLAY=:0

echo "========================================"
echo "  Cloud Gaming on Modal.com"
echo "========================================"
echo ""

# 1. Kiem tra GPU
echo "[1/5] Kiem tra GPU..."
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null || echo "[CANH BAO] Khong thay GPU driver"
echo ""

# 2. Khoi dong man hinh ao
echo "[2/5] Khoi dong man hinh ao..."
Xvfb :0 -screen 0 1920x1080x24 +extension GLX +render -noreset &
sleep 2
startxfce4 &
sleep 3
pulseaudio --start --daemonize=yes 2>/dev/null || true
echo "[OK] Desktop + Audio da khoi dong."
echo ""

# 3. Khoi dong Tailscale
echo "[3/5] Khoi dong Tailscale..."
tailscaled --tun=userspace-networking --socks5-server=localhost:1055 --outbound-http-proxy-listen=localhost:1055 &
sleep 3

TSKEY="tskey-auth-kHQ16WcdzQ11CNTRL-rZMxsBXVab5sbgDgwr73b56shzk1fqqXj"
if [ -n "$TSKEY" ] && [ "$TSKEY" != "tskey-auth-kHQ16WcdzQ11CNTRL-rZMxsBXVab5sbgDgwr73b56shzk1fqqXj" ]; then
    echo "Dang ket noi Tailscale tu dong..."
    tailscale up --authkey "$TSKEY"
else
    echo "========================================"
    echo "  DANG NHAP TAILSCALE"
    echo "  Click vao link ben duoi de dang nhap:"
    echo "========================================"
    echo ""
    tailscale up
fi
echo ""
TS_IP=$(tailscale ip -4 2>/dev/null)
echo "========================================"
echo "  TAILSCALE IP: $TS_IP"
echo "========================================"
echo ""

# 4. Tao config Sunshine
echo "[4/5] Cau hinh Sunshine..."
mkdir -p ~/.config/sunshine
cat > ~/.config/sunshine/sunshine.conf << 'SUNCONF'
origin_web_ui_allowed = wan
address_family = both
encoder = nvenc
min_log_level = info
channels = 2
SUNCONF
echo "[OK] Config Sunshine da tao."
echo ""

# 5. Khoi dong Sunshine
echo "[5/5] Khoi dong Sunshine..."
echo ""
echo "========================================"
echo "  SUNSHINE DA KHOI DONG!"
echo ""
echo "  Web UI: https://$TS_IP:47990"
echo "  (Lan dau se tao username/password)"
echo ""
echo "  Moonlight: ket noi den $TS_IP"
echo "========================================"
echo ""

# Chay Sunshine (blocking - giu container song)
exec sunshine
"""


def main():
    parser = argparse.ArgumentParser(description="Cloud Gaming on Modal.com")
    parser.add_argument(
        "--gpu", type=str, default=DEFAULT_GPU,
        choices=list(GPU_OPTIONS.keys()),
        help=f"Loai GPU (mac dinh: {DEFAULT_GPU})"
    )
    parser.add_argument(
        "--timeout", type=int, default=TIMEOUT_SECONDS,
        help=f"Thoi gian toi da (giay, mac dinh: {TIMEOUT_SECONDS})"
    )
    parser.add_argument(
        "--idle-timeout", type=int, default=IDLE_TIMEOUT_SECONDS,
        help=f"Tu dong tat sau bao lau khong hoat dong (giay, mac dinh: {IDLE_TIMEOUT_SECONDS})"
    )
    args = parser.parse_args()

    gpu_type = args.gpu.upper()
    if gpu_type not in GPU_OPTIONS:
        print(f"[LOI] GPU '{gpu_type}' khong ho tro.")
        print(f"GPU ho tro: {', '.join(GPU_OPTIONS.keys())}")
        sys.exit(1)

    gpu_info = GPU_OPTIONS[gpu_type]

    print("=" * 60)
    print("  Cloud Gaming on Modal.com")
    print("=" * 60)
    print()
    print(f"GPU: {gpu_type} ({gpu_info['vram']} VRAM)")
    print(f"Chi phi uoc tinh: {gpu_info['price']}")
    print(f"Phien toi da: {args.timeout // 3600} tieng")
    print(f"Tu dong tat sau: {args.idle_timeout // 60} phut khong hoat dong")
    print()
    print("  Cac GPU khac:")
    for g, info in GPU_OPTIONS.items():
        marker = " <-- dang dung" if g == gpu_type else ""
        print(f"    {g:5s}: {info['price']:10s} | {info['vram']:10s}{marker}")
    print()
    print("Dang tao Sandbox (lan dau co the mat 2-5 phut)...")
    print()

    app = modal.App.lookup("cloud-gaming-steam", create_if_missing=True)

    with modal.enable_output():
        sb = modal.Sandbox.create(
            app=app,
            image=image,
            gpu=gpu_type,
            timeout=args.timeout,
            idle_timeout=args.idle_timeout,
            volumes={"/data": volume},
            cpu=4.0,
            memory=16384,
        )

    sandbox_id = sb.object_id
    print(f"[OK] Sandbox da tao: {sandbox_id}")
    print()

    p = sb.exec(
        "bash", "-c", SETUP_SCRIPT,
        pty=False,
    )

    def cleanup(signum=None, frame=None):
        print("\n[INFO] Dang tat session...")
        try:
            sb.terminate()
        except Exception:
            pass
        print("[INFO] Da tat. Session ket thuc.")
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        for line in p.stdout:
            print(line, end="")
        for line in p.stderr:
            print(line, end="", file=sys.stderr)
    except KeyboardInterrupt:
        cleanup()

    exit_code = p.returncode
    if exit_code != 0:
        print(f"\n[LOI] Script thoat voi ma: {exit_code}")

    cleanup()


if __name__ == "__main__":
    main()
