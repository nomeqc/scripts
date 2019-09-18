#!/bin/bash

#######color code########
RED="31m"      # Error message
GREEN="32m"    # Success message
YELLOW="33m"   # Warning message
BLUE="36m"     # Info message

colorEcho(){
    COLOR=$1
    echo -e "\033[${COLOR}${@:2}\033[0m"
}

wget -O go.sh https://install.direct/go.sh && sh go.sh
(curl -L -s https://raw.githubusercontent.com/Nomeqc/scripts/master/v2ray/config.json)>/etc/v2ray/config.json
service v2ray restart

echo -e "\n在网站的nginx配置文件中加入以下配置："
conf=`cat << EOF
 location /v2 {
        proxy_redirect off;
        proxy_pass http://127.0.0.1:44222;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \\$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \\$http_host;
        proxy_intercept_errors on;
        error_page 400 /index.html;
    }
EOF`
colorEcho ${BLUE} "${conf}\n"

echo -e "v2ray客户端配置："
echo -n "端口(port)："
colorEcho ${BLUE} "443"

echo -n "用户ID(id)："
colorEcho ${BLUE} "2d2f5648-2646-4722-b31f-fd1369023e37"

echo -n "额外ID(alertId)："
colorEcho ${BLUE} "32"

echo -n "加密方式(security)："
colorEcho ${BLUE} "auto"

echo -n "传输协议(network)："
colorEcho ${BLUE} "ws"

echo -n "路径(path)："
colorEcho ${BLUE} "v2"

echo -n "底层传输安全："
colorEcho ${BLUE} "tls\n"
