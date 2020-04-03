#!/usr/bin/env python2
#coding: utf-8

from gevent import monkey
monkey.patch_all()
from gevent.pool import Pool
import gevent
import requests
import urlparse
import os
import sys
import time
import math
import uuid

class Downloader:
    def __init__(self, pool_size, retry=3):
        self.pool = Pool(pool_size)
        self.session = self._get_http_session(pool_size, pool_size, retry)
        self.retry = retry
        self.dir = ''
        self.succed = {}
        self.failed = []
        self.ts_total = 0
        self.tmp_filename = ''

    def _get_http_session(self, pool_connections, pool_maxsize, max_retries):
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(pool_connections=pool_connections, pool_maxsize=pool_maxsize, max_retries=max_retries)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            return session

    def run(self, m3u8_url, dir=''):
        self.dir = dir
        self.tmp_filename = ''.join(str(uuid.uuid4()).split('-'))
        if self.dir and not os.path.isdir(self.dir):
            os.makedirs(self.dir)

        r = self.session.get(m3u8_url, timeout=10)
        if r.ok:
            body = r.content
            if body:
                body = body[body.find('#EXTM3U'):body.find('#EXT-X-ENDLIST')]
                ts_list = [urlparse.urljoin(m3u8_url, n.strip()) for n in body.split('\n') if n and not n.startswith("#")]
                ts_list = zip(ts_list, [n for n in xrange(len(ts_list))])
                if ts_list:
                    self.ts_total = len(ts_list)
                    print("共有 " + str(self.ts_total) + " 个片段")
                    g1 = gevent.spawn(self._join_file)
                    self._download(ts_list)
                    g1.join()
        else:
            print(r.status_code)
            sys.exit()

    def _download(self, ts_list):
        self.pool.map(self._worker, ts_list)
        if self.failed:
            ts_list = self.failed
            self.failed = []
            self._download(ts_list)

    def _worker(self, ts_tuple):
        url = ts_tuple[0]
        index = ts_tuple[1]
        retry = self.retry
        while retry:
            try:
                r = self.session.get(url, timeout=20)
                if r.ok:
                    file_name = url.split('/')[-1].split('?')[0]
                    with open(os.path.join(self.dir, file_name), 'wb') as f:
                        f.write(r.content)
                    self.succed[index] = file_name
                    progress = int(math.floor(len(self.succed) / float(self.ts_total) * 100)) 
                    s = "\r已下载 %d%% %s"%(progress,"#"*progress)   #\r表示回车但是不换行，利用这个原理进行百分比的刷新
                    sys.stdout.write(s)       #向标准输出终端写内容
                    sys.stdout.flush()        #立即将缓存的内容刷新到标准输出
                    return
            except:
                retry -= 1
        print('[FAIL]%s' % url)
        self.failed.append((url, index))

    def _join_file(self):
        index = 0
        outfile = ''
        while index < self.ts_total:
            file_name = self.succed.get(index, '')
            if file_name:
                infile = open(os.path.join(self.dir, file_name), 'rb')
                if not outfile:
                    outfile = open(os.path.join(self.dir, self.tmp_filename), 'wb')
                outfile.write(infile.read())
                infile.close()
                os.remove(os.path.join(self.dir, file_name))
                index += 1
            else:
                time.sleep(1)
        if outfile:
            outfile.close()

if __name__ == '__main__':
    m3u8_url = sys.argv[1] if len(sys.argv) > 1 else raw_input("请输入m3u8 url：")
    saved_dir = sys.argv[2] if len(sys.argv) > 2 else raw_input("请输入保存的目录： ")
    saved_filename = sys.argv[3] if len(sys.argv) > 3 else ('' if len(sys.argv) > 2 else raw_input("请输入保存的文件名[可选]："))
    if m3u8_url == "":
        print('❌m3u8_url不能为空')
        print('格式：./m3u8.py [m3u8_url] [saved_dir] [saved_filename]')
        print('示例：./m3u8.py http://example.com/exp.m3u8 /home/video example.ts')
        sys.exit()
    if saved_dir == "":
        print('❌saved_dir不能为空')
        print('格式：./m3u8.py [m3u8_url] [saved_dir] [saved_filename]')
        print('示例：./m3u8.py http://example.com/exp.m3u8 /home/video example.ts')
        sys.exit()
    downloader = Downloader(50)
    print('下载 ' + m3u8_url)
    downloader.run(m3u8_url, saved_dir)

    tmp_filepath = os.path.join(downloader.dir, downloader.tmp_filename)
    if saved_filename:
        saved_filepath = os.path.join(downloader.dir, saved_filename)
        os.rename(tmp_filepath, saved_filepath)
        print('\n已保存到 ' + saved_filepath + '\n')
    else:
        print('\n已保存到 ' + tmp_filepath + '\n')
