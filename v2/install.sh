#!/bin/bash

wget -O go.sh https://install.direct/go.sh && sh go.sh
(curl -L -s  https://raw.githubusercontent.com/Nomeqc/scripts/master/v2/config.json)>/etc/v2ray/config.json
service v2ray restart

echo "在网站的nginx配置文件中加入以下配置："
cat << EOF
 location /v2 {
        proxy_redirect off;
        proxy_pass http://127.0.0.1:44222;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$http_host;
    }
EOF

echo "修改nginx配置，开启拦截反向代理错误，在http{}中插入："
cat << EOF
 proxy_intercept_errors on;
 
EOF

echo "在网站nginx配置文件中加入400错误处理："
cat << EOF
 error_page 400 /index.php;
 
EOF

