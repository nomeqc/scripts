#!/usr/bin/python
# -*- coding: UTF-8 -*-

import web
import shlex
import subprocess
import json

'''
使用方式：
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
        #执行命令，获得输出，错误
        output,error = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        output = output.decode('utf-8')
        error = error.decode('utf-8')
        result_json = {}
        if len(error) > 0:
        	result_json['errcode'] = 10086
        	result_json['message'] = error
        else:
        	result_json['errcode'] = 0
        	result_json['message'] = output
        web.header('Content-Type', 'application/json; charset=utf-8', unique=True)
        return json.dumps(result_json, ensure_ascii=False)

app = web.application(urls, locals())

if __name__ == "__main__":
    app.run()
    