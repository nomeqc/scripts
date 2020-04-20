#!/usr/bin/env python2
#coding: utf-8

from gevent import monkey
monkey.patch_all()

from gevent.pool import Pool
import gevent
import requests
import os
import shutil
import sys
import time
import math
import uuid
import hashlib
import json
import m3u8
import shlex
import subprocess

class Downloader:
    def __init__(self, pool_size, retry=3):
        self.pool = Pool(pool_size)
        self.session = self._get_http_session(pool_size, pool_size, retry)
        self.retry = retry
        self.dir = ''
        self.tmp_dir = ''
        self.tmp_filename = ''
        self.succed = {}
        self.key_map = {}
        self.failed = []
        self.ts_total = 0
        self.m3u8_obj = None

    def _get_http_session(self, pool_connections, pool_maxsize, max_retries):
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(pool_connections=pool_connections, pool_maxsize=pool_maxsize, max_retries=max_retries)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            return session

    def _runcmd(self, cmd):
        #将命令字符串转换为数组
        args = shlex.split(cmd)
        # print(args)
        #执行命令，获得输出，错误
        output,error = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        output = output.decode('utf-8')
        error = error.decode('utf-8')
        # print(error)
        return output,error

    def run(self, m3u8_url, dir=''):
        self.dir = dir
        self.tmp_dir = os.path.join(self.dir, hashlib.md5(m3u8_url).hexdigest())
        self.tmp_filename = ''.join(str(uuid.uuid4()).split('-')) + '.ts'

        m3u8_obj = m3u8.load(m3u8_url)
        self.m3u8_obj = m3u8_obj
        if len(m3u8_obj.segments) > 0:
            if self.dir and not os.path.isdir(self.dir):
                os.makedirs(self.dir)
            #创建临时的文件夹，用于存放片段
            if not os.path.isdir(self.tmp_dir):
                os.makedirs(self.tmp_dir)
            m3u8_obj = zip(m3u8_obj.segments, [n for n in xrange(len(m3u8_obj.segments))])
            self.ts_total = len(m3u8_obj)
            g1 = gevent.spawn(self._join_file)
            self._download(m3u8_obj)
            # 等待 greenlet 结束
            g1.join()
        else:
            print('没有任何片段')
            sys.exit()


    def _download(self, ts_list):
        self.pool.map(self._worker, ts_list)
        if self.failed:
            if self.retry <= 0:
                failed_urls = zip([ts[0].uri for ts in ts_list], [n for n in xrange(len(ts_list))])
                print('❌多次尝试下载失败:' + str(failed_urls))
                sys.exit()
            self.retry -= 1
            ts_list = self.failed
            self.failed = []
            self._download(ts_list)
            
    
    def _decrypt(self, infile, outfile, iv, key):
        cmd = 'openssl aes-128-cbc -d -in "{}" -out "{}" -nosalt -iv {} -K {}'.format(infile, outfile, iv, key)
        error = self._runcmd(cmd)[1]
        if(error):
            print('❌解密失败：' + error)
            sys.exit()

    def _worker(self, ts_tuple):
        url = ts_tuple[0].uri
        index = ts_tuple[1]
        retry = 2

        while retry:
            try:
                # print('下载：' + url)
                r = self.session.get(url, timeout=20)
                if r.ok:
                    file_name = url.split('/')[-1].split('?')[0]
                    with open(os.path.join(self.tmp_dir, file_name), 'wb') as f:
                        f.write(r.content)
                    self.succed[index] = file_name
                    progress = int(math.floor(len(self.succed) / float(self.ts_total) * 100))
                    progress_step = 2.5
                    total_step = int(math.ceil(100.0 / progress_step))
                    current_step = int(total_step * (progress/100.0))
                    s = "\r已下载 %d%% |%s%s| %d/%d"%(progress,"█"*current_step, " "*(total_step - current_step), len(self.succed), self.ts_total)   #\r表示回车但是不换行，利用这个原理进行百分比的刷新
                    sys.stdout.write(s)       #向标准输出终端写内容
                    sys.stdout.flush()        #立即将缓存的内容刷新到标准输出
                    if(len(self.succed) == self.ts_total):
                        print('')
                    return
                else:
                    retry -= 1
                    print('not ok [FAIL] %s' % url)
            except:
                retry -= 1
                print('exception [FAIL] %s' % url)
        # print('append failed:' + str(ts_tuple))
        self.failed.append(ts_tuple)

    def _join_file(self):
        index = 0
        outfile = ''
        while index < self.ts_total:
            # print('join:' + str(index))
            if len(self.succed) == self.ts_total:
                s = "\r视频合并中 [{}/{}]".format(str(index + 1), str(self.ts_total))   #\r表示回车但是不换行，利用这个原理进行百分比的刷新
                sys.stdout.write(s)       #向标准输出终端写内容
                sys.stdout.flush()        #立即将缓存的内容刷新到标准输出
            file_name = self.succed.get(index, '')
            # print "keys : %s" %  self.succed.keys()
            if file_name:
                infile_path = os.path.join(self.tmp_dir, file_name)

                seg = self.m3u8_obj.segments[index]
                # 如果有key则说明片段加密了
                is_enc = bool(seg.key)
                if is_enc:
                    if seg.key.iv:
                        iv = '{:032x}'.format(int(str(seg.key.iv), 16))
                    else:
                        iv = '{:032x}'.format(int(str(index), 16))
                    
                    key_uri = seg.key.uri
                    key_content = self.key_map.get(key_uri, '')
                    if not key_content:
                        resp = self.session.get(key_uri, timeout=15)
                        resp.encoding = 'utf-8'
                        key_content = resp.content.encode('hex')
                        self.key_map[key_uri] = key_content
                    self._decrypt(infile_path, infile_path + '.dec', iv, key_content)
                    infile_path = infile_path + '.dec'
                if not outfile:
                    outfile = open(os.path.join(self.tmp_dir, self.tmp_filename), 'wb')
                infile = open(infile_path, 'rb')
                outfile.write(infile.read())
                infile.close()
                os.remove(os.path.join(self.tmp_dir, file_name))
                if is_enc:
                    os.remove(infile_path)
                index += 1
            else:
                time.sleep(1)
        if outfile:
            outfile.close()

if __name__ == '__main__':

    m3u8_url = sys.argv[1] if len(sys.argv) > 1 else raw_input("请输入m3u8 url：")
    saved_dir = sys.argv[2] if len(sys.argv) > 2 else raw_input("请输入保存的目录： ")
    saved_filename = sys.argv[3] if len(sys.argv) > 3 else ('' if len(sys.argv) > 2 else raw_input("请输入保存的文件名[可选]："))

    if not m3u8_url.strip():
        print('❌m3u8_url不能为空')
        print('格式：./m3u8.py [m3u8_url] [saved_dir] [saved_filename]')
        print('示例：./m3u8.py http://example.com/exp.m3u8 /home/video example.ts')
        sys.exit()
    if not saved_dir.strip():
        print('❌saved_dir不能为空')
        print('格式：./m3u8.py [m3u8_url] [saved_dir] [saved_filename]')
        print('示例：./m3u8.py http://example.com/exp.m3u8 /home/video example.ts')
        sys.exit()
    downloader = Downloader(25)
    print('下载 ' + m3u8_url)
    downloader.run(m3u8_url, saved_dir)

    tmp_filepath = os.path.join(downloader.tmp_dir, downloader.tmp_filename)    
    target_filepath = os.path.join(downloader.dir, saved_filename if saved_filename.strip() else downloader.tmp_filename)
    shutil.move(tmp_filepath, target_filepath)
    print('\n已保存到 ' + target_filepath + '\n')

    # 删除临时目录
    shutil.rmtree(downloader.tmp_dir)

