#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import web
import shlex
import subprocess
import json
import platform
import chardet

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
        # 获得参数cmd
        cmd = i.cmd
        output = ''
        error = ''
        returncode = 0
        try:
            if platform.system().lower() == 'windows':
                print('cmd: {}'.format(cmd))
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            else:
                # 将命令字符串转换为数组
                args = shlex.split(cmd)
                print('args: {}'.format(args))
                process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
            output, error = process.communicate()
            returncode = process.returncode
        except Exception as exp:
            output = ''
            error = str(exp)
            returncode = 404
        '''
            解决中文乱码问题：
            python2:
            1. output 和 error为str类型，首先检测编码，需要注意当字符串长度为0时检测到的编码为None
            2. 调用str的decode方法，将str转换为unicode，避免中文导致的乱码

            python3:
            1. output 和 error为bytes类型，首先检测编码，需要注意当bytes长度为0时检测到的编码为None
            2. 调用bytes的decode方法，将bytes转换为字符串，避免中文导致的乱码
        '''
        encoding = chardet.detect(output)['encoding']
        encoding = encoding if encoding else 'utf-8'
        encoding = encoding.replace('GB2312', 'GBK')
        output = output.decode(encoding)

        encoding = chardet.detect(error)['encoding']
        encoding = encoding if encoding else 'utf-8'
        encoding = encoding.replace('GB2312', 'GBK')
        error = error.decode(encoding)
                
        result = {'output': output, 'error': error, 'returncode': returncode}
        web.header('Content-Type', 'application/json; charset=utf-8', unique=True)
        return json.dumps(result, ensure_ascii=False)


app = web.application(urls, locals())


if __name__ == "__main__":
    app.run()
