#!/usr/bin/env python2
#coding: utf-8

import m3u8
import grequests
import requests
import platform
import chardet
import re
import imghdr
import binascii

import sys
from sys import version_info
if version_info.major == 3:
    pass
elif version_info.major == 2:
    reload(sys)
    sys.setdefaultencoding('UTF8')
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
import hashlib

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
        if platform.system().lower() == 'windows':
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        else:
            # 将命令字符串转换为数组
            args = shlex.split(cmd)
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        
        output, error = process.communicate()
        returncode = process.returncode

        # 防止乱码
        encoding = chardet.detect(output)['encoding']
        encoding = encoding if encoding else 'utf-8'
        encoding = 'GBK' if encoding == 'GB2312' else encoding
        output = output.decode(encoding)

        encoding = chardet.detect(error)['encoding']
        encoding = encoding if encoding else 'utf-8'
        encoding = 'GBK' if encoding == 'GB2312' else encoding
        error = error.decode(encoding)

        return output, error, returncode

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
        if m3u8_url.startswith('http://') or m3u8_url.startswith('https://'):
            m3u8_content = self._get_m3u8_content(m3u8_url)
            m3u8_obj = m3u8.loads(m3u8_content)
        else:
            m3u8_obj = m3u8.load(m3u8_url)
        
        # 有的m3u8文件里的片段url是相对路径，补全为绝对路径
        base_uri = os.path.dirname(m3u8_url)
        for seg in m3u8_obj.segments:
            if not seg.uri.startswith('http://') and not seg.uri.startswith('https://'):
                seg.uri = '/'.join(os.path.join(base_uri, seg.uri).split('\\'))

        self.ts_total = len(m3u8_obj.segments)
        self.m3u8_obj = m3u8_obj
        if self.ts_total == 0:
            print('没有任何片段')
            sys.exit()
        if not os.path.isdir(os.path.dirname(dest_filepath)):
            os.makedirs(os.path.dirname(dest_filepath))
        self.dest_filepath = dest_filepath if os.path.basename(dest_filepath) else os.path.join(os.path.dirname(dest_filepath), os.path.basename(m3u8_url))    
        self.dest_filepath = os.path.realpath(self.dest_filepath)

        self.tmp_dir = tempfile.mkdtemp(dir=os.path.dirname(self.dest_filepath))
        self.tsurl_list = [seg.uri for seg in self.m3u8_obj.segments]

        self._download(self.tsurl_list)
        self._merge_file()
        self._convertFormat()

        print('已保存到 {}\n'.format(self.dest_filepath))

    def _get_m3u8_content(self, m3u8_url):
        result = re.search(r'(https?://[^/\n\s]+)', m3u8_url)
        ref = result.group(1) if result else ''
        # 请求头User-Agent设置成移动端， Referer设置成和m3u8_url域名一样以绕过一般的网站限制
        headers = {
            'User-Agent': 'AppleCoreMedia/1.0.0.17D50 (iPhone; U; CPU OS 13_3_1 like Mac OS X; en_us)',
            'Referer': ref
        }
        response = requests.get(url=m3u8_url, headers=headers, verify=False)
        return response.text

    def _download(self, tsurl_list):
        # 如果有加密，先下载首个片段的key
        seg = self.m3u8_obj.segments[0]
        if hasattr(seg.key, 'uri') and seg.key.uri:
            if self._runcmd('openssl version')[-1] > 0:
                print('m3u8片段已加密，需要安装openssl以支持解密')
                sys.exit()
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
        print('\n请求失败: {}  {}'.format(request.url, str(exception)))
        self.failed.append(request.url)

    def response_handler(self, r, *args, **kwargs):
        # 处理重定向导致url变化的情况
        url = r.history[0].url if r.history else r.url
        index = self.tsurl_list.index(url)
        if r.ok:
            seg = self.m3u8_obj.segments[index]
            m = hashlib.md5()
            m.update(url if sys.version_info.major == 2 else url.encode('utf-8'))
            url_md5 = m.hexdigest()
            file_path = os.path.join(self.tmp_dir, url_md5)
            with open(file_path, 'wb') as f:
                f.write(r.content)
            is_enc = hasattr(seg.key, 'uri') and seg.key.uri
            if is_enc:
                if seg.key.iv:
                    iv = '{:032x}'.format(int(str(seg.key.iv), 16))
                else:
                    iv = '{:032x}'.format(int(str(index), 16))
                key_content = self._get_key_content(seg)
                self._decrypt(file_path, file_path + '.dec', iv, key_content)
                os.remove(file_path)
                file_path = file_path + '.dec'
            
            self._discard_fake(file_path)

            self.succed[index] = file_path

            # 更新进度条
            progress = int(math.floor(len(self.succed) / float(self.ts_total) * 100))
            progress_step = 2.5
            total_step = int(math.ceil(100.0 / progress_step))
            current_step = int(total_step * (progress / 100.0))
            s = "\r已下载 %d%% |%s%s| [%d/%d]" % (progress, "█" * current_step, " " * (total_step - current_step), len(self.succed), self.ts_total)   #\r表示回车但是不换行，利用这个原理进行百分比的刷新
            sys.stdout.write(s)       # 向标准输出终端写内容
            sys.stdout.flush()        # 立即将缓存的内容刷新到标准输出
        else:
            print("\n下载失败: " + url)
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
        _, error, returncode = self._runcmd(cmd)
        if returncode != 0:
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
    
    '''
     如果ts文件伪装成图片，将图片数据去除掉
    '''
    def _discard_fake(self, ts_path):
        fmt = imghdr.what(ts_path)
        seps = {
            'png': b'0000000049454E44AE426082',
            'jpeg': b'FFD9'
        }
        sep = seps.get(fmt)
        if sep:
            with open(ts_path, 'rb') as f:
                data = f.read()
                hexstr = binascii.b2a_hex(data).upper()
            realData = hexstr.split(sep, 1)[-1]
            realData = binascii.a2b_hex(realData)
            with open('{}.tmp'.format(ts_path), 'wb') as f:
                f.write(realData)
            os.remove(ts_path)
            os.rename('{}.tmp'.format(ts_path), ts_path)

    def _convertFormat(self):
        # 退出码不为0 表示"ffmpeg -version"命令执行失败，判断为没有安装ffmpeg
        if self._runcmd('ffmpeg -version')[-1] != 0:
            return False
        output_filepath = self._make_path_unique(os.path.splitext(self.dest_filepath)[0] + '.mp4')
        print('\n正在转换成mp4格式...')
        _, error, returncode = self._runcmd('ffmpeg -i "{}" -c copy -bsf:a aac_adtstoasc "{}"'.format(self.dest_filepath, output_filepath))
        if returncode == 0:
            os.remove(self.dest_filepath)
            if self.dest_filepath.endswith('.mp4'):
                os.rename(output_filepath, self.dest_filepath)
                output_filepath = self.dest_filepath
            self.dest_filepath = output_filepath
            return True
        else:
            print('❌转换失败:\n{}'.format(error))
            os.remove(output_filepath)
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
    
    downloader = Downloader(20)
    print('下载 ' + m3u8_url)
    downloader.run(m3u8_url, dest_filepath)
