#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import web
import shlex
import subprocess
import json

'''
使用方式：

# 默认端口8080
python3 ./runcmd.py

# 或指定 ip:端口
python3 ./runcmd.py 127.0.0.1:7777

'''

urls = (
  '/runcmd', 'runcmd',
  "/(.*)", "default"
)

class default:
    def GET(self, path):
        return "hello world!"
    def POST(self, path):
        return "hello world!"

class runcmd:
    def POST(self):
        i = web.input()
        #获得参数cmd
        cmd = i.cmd
        #将命令字符串转换为数组
        args = shlex.split(cmd)
        print(args)
        output = ''
        error = ''
        returncode = 0
        try:
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = process.communicate()
            returncode = process.returncode
        except Exception as exp:
            output = ''
            error = str(exp)
            returncode = 404
        if 'bytes' in str(type(output)):
            output = output.decode('utf-8')
            error = error.decode('utf-8')
        result = {'output': output, 'error': error, 'returncode': returncode}
        web.header('Content-Type', 'application/json; charset=utf-8', unique=True)
        return json.dumps(result, ensure_ascii=False)

app = web.application(urls, locals())

if __name__ == "__main__":
    app.run()
    
