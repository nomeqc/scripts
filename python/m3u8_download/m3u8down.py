#!/usr/bin/env python3
#coding: utf-8

import hashlib
import math
import os
import re
import shutil
import sys
import time

import grequests
import m3u8
import requests
import urllib3


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Downloader:
    def __init__(self, pool_size, max_retries=3):
        self.pool_size = pool_size
        self.session = self._get_http_session(pool_size, pool_size, max_retries)
        self.max_retries = max_retries
        self.retries = 0
        self.m3u8_obj = None
        self.tsurl_list = []
        self.ts_total = 0
        self.output_mp4 = ""
        self.output_dir = ""
        self.output_ts = ''
        self.key_map = {}
        self.succed = {}

    def _get_http_session(self, pool_connections, pool_maxsize, max_retries):
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=pool_connections, pool_maxsize=pool_maxsize, max_retries=max_retries)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def _runcmd(self, cmd, shell=False):
        try:
            import shlex
            import subprocess
            args = cmd if shell else shlex.split(cmd)
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=shell)
            stdout, stderr = process.communicate()
            output = stdout + stderr
            if shell:
                try:
                    import locale
                    output = output.decode(locale.getpreferredencoding(False))
                except Exception:
                    output = output.decode('UTF-8', errors='ignore')
            else:
                output = output.decode('UTF-8', errors='ignore')
            returncode = process.returncode
        except Exception as e:
            output = str(e)
            returncode = 2
        return output, returncode

    def _get_md5(self, s):
        return hashlib.md5(s.encode('utf-8')).hexdigest()

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
            m3u8_content = m3u8_obj.dumps()
        
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
        if os.path.isdir(dest_filepath):
            raise Exception(f'❌错误：无法写入\'{dest_filepath}\'，因为它是目录')
        if not os.path.isdir(os.path.dirname(dest_filepath)):
            os.makedirs(os.path.dirname(dest_filepath))    
        self.output_mp4 = os.path.realpath(dest_filepath)
        self.output_dir = os.path.join(os.path.dirname(self.output_mp4), self._get_md5(m3u8_content))
        if not os.path.isdir(self.output_dir):
            if os.path.isfile(self.output_dir):
                raise Exception(f'❌错误：\'{self.output_dir}\'已存在，但它不是目录')
            os.makedirs(self.output_dir)
        
        self._download()
        self._merge_file()
        if self._convert_to_mp4():
            shutil.rmtree(self.output_dir)
        print('已保存到 {}\n'.format(self.output_mp4))

    def _get_m3u8_content(self, m3u8_url):
        result = re.search(r'(https?://[^/\n\s]+)', m3u8_url)
        ref = result.group(1) if result else ''
        # 请求头User-Agent设置成移动端， Referer设置成和m3u8_url域名一样以绕过一般的网站限制
        headers = {
            'User-Agent': 'AppleCoreMedia/1.0.0.17D50 (iPhone; U; CPU OS 13_3_1 like Mac OS X; en_us)',
            'Referer': ref
        }
        response = requests.get(url=m3u8_url, headers=headers, timeout=6, verify=False)
        return response.text

    def _build_download_request(self, index, url):
        def hook_factory(*factory_args, **factory_kwargs):
            def response_hook(response, *request_args, **request_kwargs):
                response.index = factory_kwargs.get('index')
                return response
            return response_hook
        req = grequests.get(url, timeout=10, callback=hook_factory(index=index), verify=False)
        req.index = index
        return req

    def _download(self):
        # 如果有加密，先下载首个片段的key
        seg = self.m3u8_obj.segments[0]
        if hasattr(seg.key, 'uri') and seg.key.uri:
            if self._runcmd('openssl version')[-1] > 0:
                print('m3u8片段已加密，需要安装openssl以支持解密')
                sys.exit()
            self._get_key_content(seg)
        
        # 统计下载成功的片段
        self.succed = {}
        for index, seg in enumerate(self.m3u8_obj.segments):
            ts_path = os.path.join(self.output_dir, self._get_md5(seg.uri))
            if os.path.isfile(ts_path):
                self.succed[index] = ts_path

        while len(self.succed) < len(self.m3u8_obj.segments):
            tasks = []
            for index, seg in enumerate(self.m3u8_obj.segments):
                if not self.succed.get(index):
                    tasks.append((index, seg.uri))
            reqs = (self._build_download_request(item[0], item[1]) for item in tasks)
            for response in grequests.imap(reqs, size=self.pool_size, exception_handler=self.exception_handler):
                self.response_handler(response)
            
            failed_count = len(self.m3u8_obj.segments) - len(self.succed)
            if failed_count > 0:
                if self.retries >= max(1, self.max_retries):
                    print(f'\n经过{self.retries}次尝试，还有{failed_count}个片段下载失败')
                    break
                self.retries += 1
                print(f'\n有{failed_count}个片段下载失败，3秒后尝试第{self.retries}次重新下载..')
                time.sleep(3)
    
    def exception_handler(self, request, exception):
        print(f'\n请求失败: {request.url}  {str(exception)}')

    def response_handler(self, r, *args, **kwargs):
        # 处理重定向导致url变化的情况
        url = r.history[0].url if r.history else r.url
        index = r.index
        if r.ok:
            seg = self.m3u8_obj.segments[index]
            file_path = os.path.join(self.output_dir, self._get_md5(url))
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
                os.rename(file_path + '.dec', file_path)
            
            self.extract_valid_data(file_path)

            self.succed[index] = file_path

            # 更新进度条
            progress = int(math.floor(len(self.succed) / float(self.ts_total) * 100))
            progress_step = 2.5
            total_step = int(math.ceil(100.0 / progress_step))
            current_step = int(total_step * (progress / 100.0))
            s = "\r已下载 %d%% |%s%s| [%d/%d] " % (progress, "█" * current_step, " " * (total_step - current_step), len(self.succed), self.ts_total)
            sys.stdout.write(s)
            sys.stdout.flush()
        else:
            print(f"\n下载失败: {url}")

    def _get_key_content(self, seg):
        key_uri = seg.key.uri
        key_content = self.key_map.get(key_uri, '')
        if not key_content:
            resp = self.session.get(key_uri, timeout=5, verify=False)
            key_content = resp.content.hex()
            self.key_map[key_uri] = key_content
        return key_content

    def _decrypt(self, infile, outfile, iv, key):
        cmd = f'openssl aes-128-cbc -d -in "{infile}" -out "{outfile}" -nosalt -iv {iv} -K {key}'
        output, returncode = self._runcmd(cmd)
        if returncode != 0:
            print(f'❌解密失败：{output}')
            sys.exit()

    def _merge_file(self):
        self.output_ts = os.path.join(self.output_dir, os.path.splitext(os.path.basename(self.output_mp4))[0] + '.ts')
        with open(self.output_ts, 'wb') as outfile:
            for i in list(range(self.ts_total)):
                infile_path = self.succed.get(i, '')
                with open(infile_path, 'rb') as infile:
                    outfile.write(infile.read())
                os.remove(infile_path)
                s = f"\r视频合并中 [{i+1}/{len(self.succed)}] "
                sys.stdout.write(s)
                sys.stdout.flush()
    
    '''
    有的TS伪装成图片，下载到本地不能直接播放。根据TS文件格式特点，提取有效数据。
    '''
    def extract_valid_data(self, ts_path):
        with open(ts_path, "rb") as f:
            data = f.read()
        b_list = list(data)
        MP2T_PACKET_LENGTH = 188
        SYNC_BYTE = 0x47
        start_index = 0
        end_index = MP2T_PACKET_LENGTH
        left = -1
        right = -1
        while end_index < len(b_list):
            if b_list[start_index] == SYNC_BYTE and b_list[end_index] == SYNC_BYTE:
                if left == -1:
                    left = start_index
                start_index += MP2T_PACKET_LENGTH
                end_index += MP2T_PACKET_LENGTH
                right = end_index if end_index <= len(b_list) else start_index
                continue
            start_index += 1
            end_index += 1
        if left == -1:
            raise Exception(f'非法的TS文件\n')
        tmp_filepath = f'{ts_path}.tmp'
        with open(tmp_filepath, 'wb') as fp:
            fp.write(data[left:right])
        os.remove(ts_path)
        os.rename(tmp_filepath, ts_path)

    def _convert_to_mp4(self):
        # 退出码不为0 表示"ffmpeg -version"命令执行失败，判断为没有安装ffmpeg
        if self._runcmd('ffmpeg -version')[-1] != 0:
            return False
        cmd = f'ffprobe "{self.output_ts}"'
        output, returncode = self._runcmd(cmd)
        if returncode != 0:
            raise Exception(f'检测编码失败\n{output}')
        bit_stream_filter = '-bsf:a aac_adtstoasc' if 'Audio: aac' in output else ''
        if not self.output_mp4.endswith('.mp4'):
            self.output_mp4 = self.output_mp4 + '.mp4'
        self.output_mp4 = self._make_path_unique(self.output_mp4)
        print('\n正在转换成mp4格式...')
        cmd = f'ffmpeg -i "{self.output_ts}" -c copy {bit_stream_filter} "{self.output_mp4}"'
        output, returncode = self._runcmd(cmd)
        if returncode == 0:
            return True
        else:
            print(f'❌"{self.output_ts}" 转换成mp4格式失败')
            return False


if __name__ == '__main__':
    # print(sys.argv)
    m3u8_url = sys.argv[1] if len(sys.argv) > 1 else input("请输入m3u8 url：")
    output_filepath = sys.argv[2] if len(sys.argv) > 2 else input("请输入保存的路径： ")
    if not m3u8_url.strip():
        print('❌m3u8_url不能为空')
        print('格式：./m3u8-down.py [m3u8_url] [output_video]')
        print('示例：./m3u8-down.py http://example.com/exp.m3u8 OUTPUT.mp4')
        sys.exit()
    if not output_filepath.strip():
        print('❌output_video不能为空')
        print('格式：./m3u8-down.py [m3u8_url] [output_video]')
        print('示例：./m3u8-down.py http://example.com/exp.m3u8 OUTPUT.mp4')
        sys.exit()
    downloader = Downloader(20)
    print('下载 ' + m3u8_url)
    downloader.run(m3u8_url, output_filepath)
