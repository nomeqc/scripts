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

class Downloader:
    def __init__(self, pool_size, retry=3):
        self.pool = Pool(pool_size)
        self.session = self._get_http_session(pool_size, pool_size, retry)
        self.retry = retry
        self.dir = ''
        self.succed = {}
        self.failed = []
        self.ts_total = 0

    def _get_http_session(self, pool_connections, pool_maxsize, max_retries):
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(pool_connections=pool_connections, pool_maxsize=pool_maxsize, max_retries=max_retries)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            return session

    def run(self, m3u8_url, dir=''):
        self.dir = dir
        if self.dir and not os.path.isdir(self.dir):
            os.makedirs(self.dir)

        r = self.session.get(m3u8_url, timeout=10)
        if r.ok:
            body = r.content
            if body:
                ts_list = [urlparse.urljoin(m3u8_url, n.strip()) for n in body.split('\n') if n and not n.startswith("#")]
                ts_list = zip(ts_list, [n for n in xrange(len(ts_list))])
                if ts_list:
                    self.ts_total = len(ts_list)
                    print(self.ts_total)
                    g1 = gevent.spawn(self._join_file)
                    self._download(ts_list)
                    g1.join()
        else:
            print(r.status_code)

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
                    print(file_name)
                    with open(os.path.join(self.dir, file_name), 'wb') as f:
                        f.write(r.content)
                    self.succed[index] = file_name
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
                    outfile = open(os.path.join(self.dir, file_name.split('.')[0]+'_all.'+file_name.split('.')[-1]), 'wb')
                outfile.write(infile.read())
                infile.close()
                os.remove(os.path.join(self.dir, file_name))
                index += 1
            else:
                time.sleep(1)
        if outfile:
            outfile.close()

if __name__ == '__main__':
    m3u_url = sys.argv[1] if len(sys.argv) > 1 else ''
    saved_dir = sys.argv[2] if len(sys.argv) > 2 else ''
    saved_filename = sys.argv[3] if len(sys.argv) > 3 else ''
    if m3u_url == "":
        print('缺少参数m3u_url')
        print('示例：./m3u8.py http://down.example.com/exp.m3u8 /home/video example.mp4')
        sys.exit()
    if saved_dir == "":
        print('缺少参数saved_dir')
        print('示例：./m3u8.py http://down.example.com/exp.m3u8 /home/video example.mp4')
        sys.exit()
    downloader = Downloader(50)
    # print(len(downloader.succed))
    # m3u_url = 'http://127.0.0.1:8000/cs255.m3u'
    # saved_dir = '/Users/fallrainy/Home/video'
    # saved_filename = 'xxxx.mp4'
    
    print('下载 ' + m3u_url + ' 到 ' + os.path.join(saved_dir, saved_filename))
    downloader.run(m3u_url, saved_dir)
    if saved_filename:
        file_name = downloader.succed.get(0, '')
        filepath = os.path.join(downloader.dir, file_name.split('.')[0] + '_all.'+file_name.split('.')[-1])
        os.rename(filepath, os.path.join(downloader.dir, saved_filename))
    print('下载完成')
