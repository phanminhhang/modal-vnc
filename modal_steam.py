"""
Cloud Gaming - Modal Notebooks

Script nay chay TRUC TIEP tren Modal Notebooks (khong can tao Sandbox).
Neu ban dang dung Modal Notebooks voi GPU, chi can chay file nay.

Cach dung:
    1. Mo Modal Notebook voi GPU (L4, A10G, L40S,...)
    2. Upload file nay vao notebook
    3. Chay: !python modal_notebook_steam.py

Yeu cau:
    - Modal Notebook da co GPU
    - Tailscale account (https://tailscale.com)
    - Moonlight client (https://moonlight-stream.org)
"""

import subprocess
import os
import sys
import time

TAILSCALE_AUTHKEY = "__TAILSCALE_AUTHKEY__"


def run(cmd, check=False, silent=False):
    if silent:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    else:
        r = subprocess.run(cmd, shell=True)
    if check and r.returncode != 0:
        print(f"[LOI] Lenh that bai: {cmd}")
        sys.exit(1)
    return r


def main():
    os.environ["DEBIAN_FRONTEND"] = "noninteractive"
    os.environ["DEBCONF_NONINTERACTIVE_SEEN"] = "true"
    os.environ["DISPLAY"] = ":0"
    os.environ["LANG"] = "en_US.UTF-8"
    os.environ["LC_ALL"] = "en_US.UTF-8"

    print("=" * 60)
    print("  Cloud Gaming - Modal Notebooks")
    print("=" * 60)
    print()

    print("[1/6] Kiem tra GPU...")
    gpu = run("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader", silent=True)
    if gpu.returncode == 0:
        print(f"  GPU: {gpu.stdout.strip()}")
    else:
        print("  [CANH BAO] Khong thay GPU!")
    print()

    print("[2/6] Cai dat packages...")
    run("echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections", silent=True)
    run("echo 'keyboard-configuration keyboard-configuration/layout select English (US)' | debconf-set-selections", silent=True)
    run("echo 'keyboard-configuration keyboard-configuration/layoutcode select us' | debconf-set-selections", silent=True)
    run("echo 'keyboard-configuration keyboard-configuration/variant select English (US)' | debconf-set-selections", silent=True)
    run("echo 'tzdata tzdata/Areas select Etc' | debconf-set-selections", silent=True)
    run("echo 'tzdata tzdata/Zones/Etc select UTC' | debconf-set-selections", silent=True)

    run("dpkg --add-architecture i386", silent=True)
    run("apt-get update -qq", silent=True)

    packages = " ".join([
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
        "kmod", "iproute2", "net-tools",
        "lib32gcc-s1", "lib32stdc++6",
        "libxcb1", "libxcb-xfixes0", "libxcb-shape0",
        "libxcb-shm0", "libxcb-randr0", "libxcb-image0",
    ])
    run(f"DEBIAN_FRONTEND=noninteractive apt-get install -y -qq {packages} > /dev/null 2>&1")
    run("locale-gen en_US.UTF-8 > /dev/null 2>&1", silent=True)

    print("  [OK] Packages da cai xong.")
    print()

    print("[3/6] Cai dat Tailscale...")
    run("curl -fsSL https://tailscale.com/install.sh | sh > /dev/null 2>&1")
    subprocess.Popen(
        ["tailscaled", "--tun=userspace-networking", "--socks5-server=localhost:1055", "--outbound-http-proxy-listen=localhost:1055"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(3)

    ts_key = TAILSCALE_AUTHKEY
    if ts_key and ts_key != "__TAILSCALE_AUTHKEY__":
        print("  Dang ket noi Tailscale tu dong...")
        run(f"tailscale up --authkey {ts_key}")
    else:
        print("  Dang nhap Tailscale (click link ben duoi):")
        run("tailscale up")

    ip_r = run("tailscale ip -4", silent=True)
    ts_ip = ip_r.stdout.strip() if ip_r.returncode == 0 else "<khong co>"
    print(f"  [OK] Tailscale IP: {ts_ip}")
    print()

    print("[4/6] Cai dat Sunshine...")
    run("wget -q https://github.com/LizardByte/Sunshine/releases/latest/download/sunshine-ubuntu-22.04-amd64.deb -O /tmp/sunshine.deb", silent=True)
    run("DEBIAN_FRONTEND=noninteractive apt-get install -y -f /tmp/sunshine.deb > /dev/null 2>&1 || true")
    run("rm -f /tmp/sunshine.deb", silent=True)

    os.makedirs(os.path.expanduser("~/.config/sunshine"), exist_ok=True)
    with open(os.path.expanduser("~/.config/sunshine/sunshine.conf"), "w") as f:
        f.write("origin_web_ui_allowed = wan\n")
        f.write("address_family = both\n")
        f.write("encoder = nvenc\n")
        f.write("min_log_level = info\n")
        f.write("channels = 2\n")
    print("  [OK] Sunshine da cai va cau hinh.")
    print()

    print("[5/6] Cai dat Steam...")
    run("echo 'steam steam/question select I AGREE' | debconf-set-selections", silent=True)
    run("echo 'steam steam/license note ' | debconf-set-selections", silent=True)
    run("wget -q https://cdn.cloudflare.steamstatic.com/client/installer/steam.deb -O /tmp/steam.deb", silent=True)
    run("dpkg -i /tmp/steam.deb > /dev/null 2>&1 || true", silent=True)
    run("DEBIAN_FRONTEND=noninteractive apt-get install -y -f > /dev/null 2>&1 || true")
    run("rm -f /tmp/steam.deb", silent=True)
    print("  [OK] Steam da cai.")
    print()

    print("[6/6] Khoi dong man hinh ao + Sunshine...")
    run("pkill -9 Xvfb 2>/dev/null || true", silent=True)
    time.sleep(1)
    subprocess.Popen(
        ["Xvfb", ":0", "-screen", "0", "1920x1080x24", "+extension", "GLX", "+render", "-noreset"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    subprocess.Popen(["startxfce4"], env={**os.environ}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    subprocess.Popen(["pulseaudio", "--start", "--daemonize=yes"], env={**os.environ},
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)

    print()
    print("=" * 60)
    print("  SETUP HOAN TAT!")
    print()
    print(f"  Sunshine Web UI: https://{ts_ip}:47990")
    print(f"  (Lan dau truy cap -> tao username/password)")
    print()
    print(f"  Moonlight: ket noi den {ts_ip}")
    print()
    print("  Dang chay Sunshine... (Ctrl+C de dung)")
    print("=" * 60)
    print()

    try:
        os.execvp("sunshine", ["sunshine"])
    except KeyboardInterrupt:
        print("\n[INFO] Da dung Sunshine.")


if __name__ == "__main__":
    main()
