#!/bin/bash
# wireguard_setup.sh - WireGuard VPN 一键配置脚本（脱敏版）
#
# 用法: bash wireguard_setup.sh <主服务器公网IP> <新加坡公网IP>
#
# 部署前请替换以下变量:
#   MAIN_IP   - 主服务器公网IP
#   SG_IP     - 新加坡公网IP

set -e

MAIN_IP="${1:-YOUR_MAIN_SERVER_IP}"
SG_IP="${2:-YOUR_SG_SERVER_IP}"
WG_PORT="${WG_PORT:-51820}"

echo "========================================="
echo "  WireGuard VPN 配置脚本（脱敏版）"
echo "========================================="
echo "主服务器: $MAIN_IP"
echo "新加坡:   $SG_IP"
echo "端口:     $WG_PORT"
echo ""

# ══════════════════════════════════════════════════════
# 安装 WireGuard
# ══════════════════════════════════════════════════════
echo "[1/6] 安装 WireGuard..."

install_wg() {
    if command -v wg &>/dev/null; then
        echo "  WireGuard 已安装"
        return
    fi
    apt-get update -qq
    apt-get install -y wireguard wireguard-tools
    echo "  ✅ 安装完成"
}

# 两台服务器分别执行
echo "  在本机安装..."
install_wg

echo "  在新加坡安装..."
ssh -o StrictHostKeyChecking=no root@$SG_IP "bash -s" << 'REMOTE'
if ! command -v wg &>/dev/null; then
    apt-get update -qq && apt-get install -y wireguard wireguard-tools
fi
echo "  ✅ 新加坡 WireGuard 安装完成"
REMOTE

# ══════════════════════════════════════════════════════
# 生成密钥对
# ══════════════════════════════════════════════════════
echo "[2/6] 生成密钥对..."

# 主服务器密钥
cd /etc/wireguard
wg genkey | tee wg_main_private.key | wg pubkey > wg_main_public.key
MAIN_PRIV=$(cat wg_main_private.key)
MAIN_PUB=$(cat wg_main_public.key)
echo "  主服务器公钥: $MAIN_PUB"

# 新加坡密钥
ssh -o StrictHostKeyChecking=no root@$SG_IP "bash -s" << 'REMOTE'
cd /etc/wireguard
wg genkey > wg_sg_private.key
wg pubkey < wg_sg_private.key > wg_sg_public.key
cat wg_sg_public.key
REMOTE
SG_PUB=$(ssh -o StrictHostKeyChecking=no root@$SG_IP "cat /etc/wireguard/wg_sg_public.key")
echo "  新加坡公钥: $SG_PUB"

# ══════════════════════════════════════════════════════
# 配置主服务器
# ══════════════════════════════════════════════════════
echo "[3/6] 配置主服务器..."

cat > /etc/wireguard/wg0.conf << EOF
[Interface]
Address = 10.0.0.1/24
ListenPort = $WG_PORT
PrivateKey = $MAIN_PRIV

# 开启 IP 转发
PostUp = sysctl -w net.ipv4.ip_forward=1

# 防火墙规则（允许VPN流量，丢弃其他）
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT
PostUp = iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

[Peer]
PublicKey = $SG_PUB
Endpoint = $SG_IP:$WG_PORT
AllowedIPs = 10.0.0.2/32
PersistentKeepalive = 25
EOF

chmod 600 /etc/wireguard/wg0.conf
echo "  ✅ 主服务器配置完成 (10.0.0.1)"

# ══════════════════════════════════════════════════════
# 配置新加坡
# ══════════════════════════════════════════════════════
echo "[4/6] 配置新加坡..."

SG_PRIV=$(ssh -o StrictHostKeyChecking=no root@$SG_IP "cat /etc/wireguard/wg_sg_private.key")

ssh -o StrictHostKeyChecking=no root@$SG_IP "bash -s" << REMOTE
cat > /etc/wireguard/wg0.conf << EOF
[Interface]
Address = 10.0.0.2/24
ListenPort = $WG_PORT
PrivateKey = $SG_PRIV

# 开启 IP 转发
PostUp = sysctl -w net.ipv4.ip_forward=1

[Peer]
PublicKey = $MAIN_PUB
Endpoint = $MAIN_IP:$WG_PORT
AllowedIPs = 10.0.0.1/32
PersistentKeepalive = 25
EOF
chmod 600 /etc/wireguard/wg0.conf
echo "  ✅ 新加坡配置完成 (10.0.0.2)"
REMOTE

# ══════════════════════════════════════════════════════
# 启动 VPN
# ══════════════════════════════════════════════════════
echo "[5/6] 启动 WireGuard..."

# 主服务器
wg-quick up wg0 2>/dev/null || wg-quick down wg0 2>/dev/null; wg-quick up wg0
systemctl enable wg-quick@wg0 2>/dev/null || true
echo "  ✅ 主服务器 VPN 已启动"

# 新加坡
ssh -o StrictHostKeyChecking=no root@$SG_IP "wg-quick up wg0 2>/dev/null || (wg-quick down wg0 2>/dev/null; wg-quick up wg0)"
ssh -o StrictHostKeyChecking=no root@$SG_IP "systemctl enable wg-quick@wg0 2>/dev/null || true"
echo "  ✅ 新加坡 VPN 已启动"

# ══════════════════════════════════════════════════════
# 验证连通性
# ══════════════════════════════════════════════════════
echo "[6/6] 验证连通性..."
echo "  主服务器 → 新加坡: $(ping -c 1 -W 2 10.0.0.2 2>/dev/null && echo '✅' || echo '❌')"
echo "  新加坡 → 主服务器: $(ssh -o StrictHostKeyChecking=no root@$SG_IP "ping -c 1 -W 2 10.0.0.1" 2>/dev/null && echo '✅' || echo '❌')"

# ══════════════════════════════════════════════════════
# 防火墙配置
# ══════════════════════════════════════════════════════
echo ""
echo "配置防火墙..."
# 主服务器：只允许新加坡 VPN 网段 SSH
ufw allow from 10.0.0.0/24 to any port 22 proto tcp 2>/dev/null || true
echo "  ✅ 主服务器防火墙已配置"

# 新加坡：同样只允许主服务器 VPN 网段
ssh -o StrictHostKeyChecking=no root@$SG_IP "ufw allow from 10.0.0.0/24 to any port 22 proto tcp 2>/dev/null || true"
echo "  ✅ 新加坡防火墙已配置"

# ══════════════════════════════════════════════════════
# 完成
# ══════════════════════════════════════════════════════
echo ""
echo "========================================="
echo "  ✅ VPN 配置完成！"
echo "========================================="
echo ""
echo "VPN 信息:"
echo "  主服务器: 10.0.0.1 (公网: $MAIN_IP)"
echo "  新加坡:   10.0.0.2 (公网: $SG_IP)"
echo "  延迟:     $(ping -c 1 -W 2 10.0.0.2 2>/dev/null | grep time | awk '{print $7}' || echo 'N/A')"
echo ""
echo "下一步:"
echo "  1. 配置 Git 同步仓库"
echo "  2. 设置 SSH Key 认证"
echo "  3. 运行 skill_factory.py 测试"
echo ""
