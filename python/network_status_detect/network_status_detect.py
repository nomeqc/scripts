#!/usr/bin/env python3
#coding: utf-8

import socket
import requests
import time
from plyer import notification


def isNetOK(testserver):
    s = socket.socket()
    s.settimeout(3)
    try:
        status = s.connect_ex(testserver)
        if status == 0:
            s.close()
            return True
        else:
            return False
    except Exception:
        return False


def send_message(msg):
    try:
        requests.post('https://tools.201992.xyz/dingtalk/robot.php', {'message': msg}, timeout=7)
        # response.encoding = 'utf-8'
        # print(' {}'.format(response.text))+
    except Exception:
        pass


if __name__ == '__main__':
    server = ('114.114.114.114', 53)
    is_ok = isNetOK(testserver=server)
    hostname = socket.gethostname()
    msg = '已连接到互联网✅' if is_ok else '互联网连接已断开❌'
    t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print('{} {}'.format(t, msg))
    failed_count = 0
    while True:
        status = isNetOK(testserver=server)
        if status != is_ok:
            if not status:
                failed_count += 1
                if failed_count >= 3:
                    is_ok = status
                    failed_count = 0
            else:
                is_ok = status
            msg = '已连接到互联网✅' if is_ok else '互联网连接已断开❌'
            t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            print('{} {}'.format(t, msg))
            # 发送通知
            notification.notify("网络状态变化", msg)
            if is_ok:
                send_message('「{}」 {}'.format(hostname, msg))
        time.sleep(1)
    
    
