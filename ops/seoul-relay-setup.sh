#!/usr/bin/env bash
# Run as root on a fresh Ubuntu 24.04 Seoul relay after instance approval.
# TLS remains on the Mac; this host relays encrypted TLS bytes only.
set -euo pipefail
: "${TUNNEL_PUBLIC_KEY:?Set the dedicated Mac tunnel SSH public key}"
[[ "$TUNNEL_PUBLIC_KEY" == ssh-ed25519\ * ]] || { echo 'Expected an Ed25519 public key'; exit 1; }
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y nginx libnginx-mod-stream
id sushitunnel >/dev/null 2>&1 || useradd --create-home --shell /bin/bash sushitunnel
install -d -m 700 -o sushitunnel -g sushitunnel /home/sushitunnel/.ssh
printf 'restrict,port-forwarding,permitlisten="127.0.0.1:18443" %s\n' "$TUNNEL_PUBLIC_KEY" > /home/sushitunnel/.ssh/authorized_keys
chmod 600 /home/sushitunnel/.ssh/authorized_keys
chown sushitunnel:sushitunnel /home/sushitunnel/.ssh/authorized_keys
cat > /etc/ssh/sshd_config.d/sushisite-tunnel.conf <<'EOF'
Match User sushitunnel
    AuthenticationMethods publickey
    PasswordAuthentication no
    AllowTcpForwarding remote
    PermitListen 127.0.0.1:18443
    GatewayPorts no
    AllowAgentForwarding no
    X11Forwarding no
    PermitTTY no
    ForceCommand /bin/false
Match all
EOF
sshd -t
systemctl reload ssh
install -d /etc/nginx/stream.d
# nginx.conf must load stream configuration at the top level, once.
if ! grep -q 'include /etc/nginx/stream.d/\*.conf;' /etc/nginx/nginx.conf; then
    printf '\ninclude /etc/nginx/stream.d/*.conf;\n' >> /etc/nginx/nginx.conf
fi
cat > /etc/nginx/stream.d/sushisite.conf <<'EOF'
stream {
    server {
        listen 443;
        proxy_pass 127.0.0.1:18443;
        proxy_connect_timeout 5s;
        proxy_timeout 1h;
        proxy_socket_keepalive on;
    }
}
EOF
nginx -t
systemctl enable nginx
systemctl restart nginx
echo 'Relay ready. Allow TCP 443 publicly and restrict TCP 22 to the Mac uplink/admin IP.'
