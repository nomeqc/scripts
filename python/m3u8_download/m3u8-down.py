#!/usr/bin/env python
#coding: utf-8

import m3u8
import grequests
import requests
from requests.adapters import HTTPAdapter
import sys
from sys import version_info
if version_info.major == 3:
    pass
elif version_info.major == 2:
    try:
        input = raw_input
    except NameError:
        pass
else:
    print ("Unknown python version - input function not safe")

import os
import math
import shlex
import subprocess
import tempfile
import shutil
import time

class Downloader:
    def __init__(self, pool_size, retry=3):
        self.pool_size = pool_size
        self.session = self._get_http_session(pool_size, pool_size, retry)
        self.retry = retry
        self.retry_count = 0
        self.m3u8_obj = None
        self.tsurl_list = []
        self.ts_total = 0
        self.dest_filepath = ""
        self.tmp_dir = ""
        self.tmp_filepath = ""
        self.key_map = {}
        self.succed = {}
        self.failed = []

    def _get_http_session(self, pool_connections, pool_maxsize, max_retries):
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(pool_connections=pool_connections, pool_maxsize=pool_maxsize, max_retries=max_retries)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            return session

    def _runcmd(self, cmd):
        #将命令字符串转换为数组
        args = shlex.split(cmd)
        #执行命令，获得输出，错误
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output,error = p.communicate()
        exit_code = p.returncode
        # 为了兼容 python2 和 python3
        if 'bytes' in str(type(output)):
            output = output.decode('utf-8')
            error = error.decode('utf-8')
        return output, error, exit_code

    def _make_path_unique(self, path, isfile=True):
        unique_path = path
        num = 1
        while os.path.exists(unique_path):
            if isfile:
                parts = os.path.splitext(path)
                unique_path = '{} ({}){}'.format(parts[0], num, parts[1])
            else:
                unique_path = '{} ({})'.format(path, num)
            num += 1
        return unique_path

    def run(self, m3u8_url="", dest_filepath=""):
        if not m3u8_url:
            print('m3u8_url不能为空')
            sys.exit()
        if not dest_filepath:
            print('dest_filepath不能为空')
            sys.exit()
        m3u8_obj = m3u8.load(m3u8_url)
        self.ts_total = len(m3u8_obj.segments)
        self.m3u8_obj = m3u8_obj
        if self.ts_total == 0:
            print('没有任何片段')
            sys.exit()
        if not os.path.isdir(os.path.dirname(dest_filepath)):
            os.makedirs(os.path.dirname(dest_filepath))
        self.dest_filepath = dest_filepath if os.path.basename(dest_filepath) else os.path.join(os.path.dirname(dest_filepath), os.path.basename(m3u8_url))    
        self.tmp_dir = tempfile.mkdtemp(dir=os.path.dirname(self.dest_filepath))
        self.tsurl_list = [seg.uri for seg in self.m3u8_obj.segments]
        self._download(self.tsurl_list)
        self._merge_file()
        self._convertFormat()
        print('已保存到 {}\n'.format(self.dest_filepath))

    def _download(self, tsurl_list):
        # 如果有加密，先下载首个片段的key
        seg = self.m3u8_obj.segments[0]
        if seg.key.uri:
            self._get_key_content(seg)

        reqs = (grequests.get(url, timeout=5) for url in tsurl_list)
        for response in grequests.imap(reqs, size=self.pool_size, exception_handler=self.exception_handler):
            self.response_handler(response)

        if self.failed:
            if self.retry_count >= self.retry:
                print('\n经过{}次尝试，还有{}个片段下载失败'.format(self.retry_count, len(self.failed)))
                return
            self.retry_count += 1
            print('\n有{}个片段下载失败，3秒后尝试第{}次重新下载..'.format(len(self.failed), self.retry_count))
            tsurl_list = self.failed
            self.failed = []
            time.sleep(3)
            self._download(tsurl_list)
        print('')

    def exception_handler(self, request, exception):
        print("\nRequest failed: " + request.url + str(exception))
        self.failed.append(request.url)

    def response_handler(self, r, *args, **kwargs):
        url = r.url
        index = self.tsurl_list.index(url)
        if r.ok:
            seg = self.m3u8_obj.segments[index]
            file_path = os.path.join(self.tmp_dir, os.path.basename(url))
            with open(file_path, 'wb') as f:
                f.write(r.content)
            is_enc = bool(seg.key.uri)
            if is_enc:
                iv = ''
                if seg.key.iv:
                    iv = '{:032x}'.format(int(str(seg.key.iv), 16))
                else:
                    iv = '{:032x}'.format(int(str(index), 16))
                key_content = self._get_key_content(seg)
                self._decrypt(file_path, file_path + '.dec', iv, key_content)
                os.remove(file_path)
                file_path = file_path + '.dec'
            self.succed[index] = file_path
            # 更新进度条
            progress = int(math.floor(len(self.succed) / float(self.ts_total) * 100))
            progress_step = 2.5
            total_step = int(math.ceil(100.0 / progress_step))
            current_step = int(total_step * (progress/100.0))
            s = "\r已下载 %d%% |%s%s| [%d/%d]"%(progress,"█"*current_step, " "*(total_step - current_step), len(self.succed), self.ts_total)   #\r表示回车但是不换行，利用这个原理进行百分比的刷新
            sys.stdout.write(s)       #向标准输出终端写内容
            sys.stdout.flush()        #立即将缓存的内容刷新到标准输出
        else:
            print("\nnot ok: " + url)
            self.failed.append(url)
        
    def _get_key_content(self, seg):
        key_uri = seg.key.uri
        key_content = self.key_map.get(key_uri, '')
        if not key_content:
            resp = self.session.get(key_uri, timeout=5)
            key_content = resp.content.hex() if 'bytes' in str(type(resp.content)) else resp.content.encode('hex')
            self.key_map[key_uri] = key_content
        return key_content

    def _decrypt(self, infile, outfile, iv, key):
        cmd = 'openssl aes-128-cbc -d -in "{}" -out "{}" -nosalt -iv {} -K {}'.format(infile, outfile, iv, key)
        _,error,exit_code = self._runcmd(cmd)
        if  exit_code:
            print('❌解密失败：' + error)
            sys.exit()
            
    def _merge_file(self):
        index = 0
        outfile = None
        file_num = 0
        while index < self.ts_total:
            infile_path = self.succed.get(index, '')
            if infile_path:
                if not outfile:
                    self.tmp_filepath = self._make_path_unique(self.dest_filepath + '.tmp')
                    outfile = open(self.tmp_filepath, 'wb')
                infile = open(infile_path, 'rb')
                outfile.write(infile.read())
                infile.close()
                os.remove(infile_path)

                file_num += 1
                s = "\r视频合并中 [{}/{}]".format(file_num, len(self.succed))
                sys.stdout.write(s)       
                sys.stdout.flush()
            index += 1
        if outfile:
            outfile.close()
        self.dest_filepath = self._make_path_unique(self.dest_filepath)
        os.rename(self.tmp_filepath, self.dest_filepath)
        shutil.rmtree(self.tmp_dir)
    
    def _convertFormat(self):
        _,_,exit_code = self._runcmd('ffmpeg -version')
        # 退出码不为0 表示"ffmpeg -version"命令执行失败，判断为没有安装ffmpeg
        if exit_code:
            return False
        output_filepath = self._make_path_unique(os.path.splitext(self.dest_filepath)[0] + '.mp4')
        print('\n正在转换成mp4格式...')
        _,error,exit_code = self._runcmd('ffmpeg -i "{}" -c copy "{}"'.format(self.dest_filepath, output_filepath))
        if not exit_code:
            os.remove(self.dest_filepath)
            if self.dest_filepath.endswith('.mp4'):
                os.rename(output_filepath, self.dest_filepath)
                output_filepath = self.dest_filepath
            self.dest_filepath = output_filepath
            return True
        else:
            print('❌转换失败:\n{}'.format(error))
            return False

if __name__ == '__main__':

    m3u8_url = sys.argv[1] if len(sys.argv) > 1 else input("请输入m3u8 url：")
    dest_filepath = sys.argv[2] if len(sys.argv) > 2 else input("请输入保存的路径(如: /home/video/exp.mp4)： ")
    
    if not m3u8_url.strip():
        print('❌m3u8_url不能为空')
        print('格式：./m3u8-down.py [m3u8_url] [dest_filepath]')
        print('示例：./m3u8-down.py http://example.com/exp.m3u8 /home/video/exp.mp4')
        sys.exit()
    if not dest_filepath.strip():
        print('❌dest_filepath不能为空')
        print('格式：./m3u8-down.py [m3u8_url] [dest_filepath]')
        print('示例：./m3u8-down.py http://example.com/exp.m3u8 /home/video/exp.mp4')
        sys.exit()
    downloader = Downloader(10)
    downloader.run(m3u8_url, dest_filepath)
