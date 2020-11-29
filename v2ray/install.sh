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

wget -O install-release.sh https://raw.githubusercontent.com/v2fly/fhs-install-v2ray/master/install-release.sh && bash install-release.sh
(curl -L -s https://raw.githubusercontent.com/Nomeqc/scripts/master/v2ray/config.json)>/usr/local/etc/v2ray/config.json
# 设置开机自启动
systemctl enable v2ray
# 重启v2ray
systemctl restart v2ray

#等待2s检测 v2ray服务端口是否开放
colorEcho ${BLUE} "正在检测v2ray服务是否已启动..."
sleep 2s
PID=`lsof -i:44222| grep -v "PID" | awk '{print $2}'`
if [ "$PID" != "" ];
then
	colorEcho ${GREEN} "v2ray服务已启动"
else
	colorEcho ${RED} "v2ray服务启动失败"
	exit
fi


echo -e "\n在网站的nginx配置文件中加入以下配置："
conf=`cat << EOF
 location /v2 {
        if ($http_upgrade != "websocket") { # WebSocket协商失败时返回404
            return 404;
        }
        proxy_redirect off;
        proxy_pass http://127.0.0.1:44222; # 假设WebSocket监听在环回地址的44222端口上
        proxy_http_version 1.1;
        proxy_set_header Upgrade \\$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \\$host;
        # Show real IP in v2ray access.log
        proxy_set_header X-Real-IP \\$remote_addr;
        proxy_set_header X-Forwarded-For \\$proxy_add_x_forwarded_for;
    }
EOF`
colorEcho ${BLUE} "${conf}\n"

echo -e "v2ray客户端配置："
echo -n "端口(port)："
colorEcho ${BLUE} "443"

echo -n "用户ID(id)："
colorEcho ${BLUE} "2d2f5648-2646-4722-b31f-fd1369023e37"

echo -n "额外ID(alertId)："
colorEcho ${BLUE} "0"

echo -n "加密方式(security)："
colorEcho ${BLUE} "none"

echo -n "传输协议(network)："
colorEcho ${BLUE} "ws"

echo -n "路径(path)："
colorEcho ${BLUE} "v2"

echo -n "底层传输安全："
colorEcho ${BLUE} "tls\n"
