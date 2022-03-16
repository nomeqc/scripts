#!/usr/bin/env python3
#coding: utf-8

import argparse
import asyncio
import hashlib
import locale
import math
import os
import re
import shutil
import sys
from pathlib import Path
from urllib import parse

import aiohttp
import m3u8
from Crypto.Cipher import AES


def read_file(filepath):
    codecs = ['utf-8', locale.getpreferredencoding(False)]
    for i, codec in enumerate(codecs):
        try:
            text = Path(filepath).read_text(encoding=codec)
        except UnicodeDecodeError:
            if i == len(codecs) - 1:
                print(f'文件：\'{filepath}\' 解码失败。只支持文件编码：{"、".join(codecs)}')
    return text


def calculate_md5(s):
    data = s.encode('utf-8') if type(s) == str else s
    return hashlib.md5(data).hexdigest()


def ensure_path_unique(path, isfile=True):
    unique_path = path
    n = 1
    while os.path.exists(unique_path):
        if isfile:
            part = os.path.splitext(path)
            unique_path = '{} ({}){}'.format(part[0], n, part[1])
        else:
            unique_path = '{} ({})'.format(path, n)
        n += 1
    return unique_path


def runcmd(cmd, shell=False):
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


class Downloader:

    def __init__(self, pool_size=10, headers={}, max_retries=3, proxy=None):
        self.pool_size = max(1, pool_size)
        self.headers = headers
        self.max_retries = max(0, max_retries)
        self.retries = 0
        if proxy and not proxy.startswith('http://') and not proxy.startswith('https://'):
            proxy = f'http://{proxy}'
        self.proxy = proxy
        self.m3u8_obj = None
        self.ts_total = 0
        self.m3u8_url = ''
        self.output_dir = ''
        self.output_mp4 = ''
        self.output_ts = ''
        self.key_map = {}
        self.succed = {}

    async def load_m3u8(self, url):

        def resove(m3u8_obj):
            base_uri = os.path.dirname(url)
            for seg in m3u8_obj.segments:
                if not seg.uri.startswith('http://') and not seg.uri.startswith('https://'):
                    seg.uri = '/'.join(os.path.join(base_uri, seg.uri).split('\\'))

        if not url.startswith('http://') and not url.startswith('https://'):
            if not Path(url).is_file():
                raise Exception(f'找不到文件：\'{url}\'')
            text = read_file(url)
            self.m3u8_md5 = calculate_md5(text)
            self.m3u8_obj = m3u8.loads(text)
            self.ts_total = len(self.m3u8_obj.segments)
            resove(self.m3u8_obj)
            return
        result = re.search(r'(https?://[^/\n\s]+)', url)
        referer = result.group(1) if result else ''
        # 请求头User-Agent设置成移动端， Referer设置成和m3u8_url域名一样以绕过一般的网站限制
        headers = {
            'user-agent': 'AppleCoreMedia/1.0.0.17D50 (iPhone; U; CPU OS 13_3_1 like Mac OS X; en_us)',
            'referer': referer
        }
        headers.update(self.headers)
        async with self.session.get(url, headers=headers, proxy=self.proxy) as resp:
            text = await resp.text()
            self.m3u8_md5 = calculate_md5(text)
            self.m3u8_obj = m3u8.loads(text)
            self.ts_total = len(self.m3u8_obj.segments)
            resove(self.m3u8_obj)

    async def _fetch_key(self, key_uri):
        key_uri = parse.urljoin(self.m3u8_obj.base_uri, key_uri)
        key_content = self.key_map.get(key_uri)
        if not key_content:
            async with self.session.get(key_uri) as resp:
                if resp.ok:
                    key_content = await resp.read()
                    self.key_map[key_uri] = key_content
                else:
                    print(f'无法下载key：{key_uri}')
                    sys.exit()
        return key_content

    async def _fetch_segment(self, seg, index):
        url = seg.uri

        async def process(data):
            filepath = Path(self.output_dir, calculate_md5(url))
            filepath.write_bytes(data)
            filepath_str = str(filepath)
            is_enc = hasattr(seg.key, 'uri') and seg.key.uri
            if is_enc:
                if seg.key.iv:
                    iv = '{:032x}'.format(int(str(seg.key.iv), 16))
                else:
                    iv = '{:032x}'.format(int(str(index), 16))
                iv = bytes.fromhex(iv)
                key_content = await self._fetch_key(seg.key.uri)
                self._decrypt(filepath_str, filepath_str + '.dec', iv, key_content)
                filepath.unlink()
                Path(filepath_str + '.dec').rename(filepath_str)
            self.extract_valid_data(filepath_str)
            self.succed[index] = filepath_str
            # 更新进度条
            progress = math.floor(len(self.succed) / float(self.ts_total) * 100)
            progress_step = 2.5
            total_step = math.ceil(100.0 / progress_step)
            current_step = int(total_step * (progress / 100.0))
            s = "\r已下载 %d%% |%s%s| [%d/%d] " % (
                progress, "█" * current_step, " " * (total_step - current_step), len(self.succed), self.ts_total
            )
            sys.stdout.write(s)
            sys.stdout.flush()

        if not url.startswith('http://') and not url.startswith('https://'):
            data = Path(url).read_bytes()
        else:
            try:
                async with self.session.get(url, headers=self.headers, proxy=self.proxy) as resp:
                    if resp.ok:
                        data = await resp.read()
                    else:
                        print(f"\n下载失败: {url}")
            except Exception as e:
                print(f'\'{url}\'下载失败。错误：{e}')
        await process(data)

    async def _download_segments(self):
        # 统计下载成功的片段
        self.succed = {}
        for index, seg in enumerate(self.m3u8_obj.segments):
            ts_path = os.path.join(self.output_dir, calculate_md5(seg.uri))
            if os.path.isfile(ts_path):
                self.succed[index] = ts_path
        if len(self.succed) == len(self.m3u8_obj.segments):
            return
        first_segment = self.m3u8_obj.segments[0]
        if hasattr(first_segment.key, 'uri') and first_segment.key.uri:
            await self._fetch_key(first_segment.key.uri)
        while len(self.succed) < len(self.m3u8_obj.segments):
            tasks = []
            for index, seg in enumerate(self.m3u8_obj.segments):
                if not self.succed.get(index):
                    tasks.append(asyncio.create_task(self._fetch_segment(seg, index)))
            await asyncio.wait(tasks)
            failed_count = len(self.m3u8_obj.segments) - len(self.succed)
            if failed_count > 0:
                if self.retries >= self.max_retries:
                    if self.retries > 0:
                        print(f'\n经过{self.retries}次尝试，还有{failed_count}个片段下载失败')
                    else:
                        print(f'\n还有{failed_count}个片段下载失败')
                    break
                self.retries += 1
                print(f'\n有{failed_count}个片段下载失败，3秒后开始第{self.retries}次重试..')
                await asyncio.sleep(3)
            else:
                print('')

    def _decrypt(self, in_filepath, out_filepath, iv, key):
        chunk_size = AES.block_size * 1024
        cipher = AES.new(key, AES.MODE_CBC, iv)
        with open(in_filepath, 'rb') as infile:
            with open(out_filepath, 'wb') as outfile:
                for chunk in iter(lambda: infile.read(chunk_size), b''):
                    try:
                        outfile.write(cipher.decrypt(chunk))
                    except Exception as e:
                        print(f'❌解密失败：{str(e)}')
                        sys.exit()

    def _merge_file(self):
        self.output_ts = os.path.join(self.output_dir, os.path.splitext(os.path.basename(self.output_mp4))[0] + '.ts')
        with open(self.output_ts, 'wb') as outfile:
            for i in list(range(self.ts_total)):
                infile_path = self.succed.get(i, '')
                with open(infile_path, 'rb') as infile:
                    outfile.write(infile.read())
                os.remove(infile_path)
                s = f"\r合并视频片段 [{i+1}/{len(self.succed)}] "
                sys.stdout.write(s)
                sys.stdout.flush()

    def extract_valid_data(self, ts_path):
        '''
        有的TS伪装成图片，下载到本地不能直接播放。根据TS文件格式特点，提取有效数据。
        '''
        with open(ts_path, "r+b") as fp:
            data = fp.read()
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
                    right = end_index
                    start_index += MP2T_PACKET_LENGTH
                    end_index += MP2T_PACKET_LENGTH
                    continue
                start_index += 1
                end_index += 1
            if left == -1:
                raise Exception(f'非法的TS文件\n')
            # 如果最后一个package是完整的 要加上它的长度
            if right + MP2T_PACKET_LENGTH <= len(b_list):
                right += MP2T_PACKET_LENGTH
            fp.truncate(0)
            fp.seek(0)
            fp.write(data[left:right])

    def _convert_to_mp4(self):
        if runcmd('ffmpeg -version')[-1] != 0:
            print('检测到未安装ffmpeg，将跳过格式转换')
            return False
        if runcmd('ffprobe -version')[-1] != 0:
            print('检测到未安装ffprobe，将跳过格式转换')
            return False
        cmd = f'ffprobe "{self.output_ts}"'
        output, returncode = runcmd(cmd)
        if returncode != 0:
            raise Exception(f'❌检测编码失败：\n{output}')
        bit_stream_filter = '-bsf:a aac_adtstoasc' if 'Audio: aac' in output else ''
        if not self.output_mp4.endswith('.mp4'):
            self.output_mp4 = self.output_mp4 + '.mp4'
        self.output_mp4 = ensure_path_unique(self.output_mp4)
        print('\n正在转换成mp4格式...')
        cmd = f'ffmpeg -i "{self.output_ts}" -c copy {bit_stream_filter} "{self.output_mp4}"'
        output, returncode = runcmd(cmd)
        if returncode != 0:
            print(f'❌"{self.output_ts}" 转换成mp4格式失败')
            return False
        return True

    async def main(self):
        conn = aiohttp.TCPConnector(limit=self.pool_size)
        timeout = aiohttp.ClientTimeout(total=None, connect=None, sock_connect=15, sock_read=15)
        async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
            self.session = session
            await self.load_m3u8(self.m3u8_url)
            if self.ts_total == 0:
                print('没有任何片段')
                sys.exit()

            self.output_dir = os.path.join(os.path.dirname(self.output_mp4), self.m3u8_md5)
            if not Path(self.output_dir).exists():
                Path(self.output_dir).mkdir()
            elif Path(self.output_dir).is_file():
                output_dir_path = Path(ensure_path_unique(self.output_dir, isfile=False))
                output_dir_path.mkdir()
                self.output_dir = str(output_dir_path)
            await self._download_segments()
        self._merge_file()
        if self._convert_to_mp4():
            shutil.rmtree(self.output_dir)
        print('已保存到：{}\n'.format(self.output_mp4))

    def run(self, m3u8_url="", output_file=""):
        if not m3u8_url:
            print('m3u8_url不能为空')
            sys.exit()
        if not output_file:
            print('output_file不能为空')
            sys.exit()
        self.m3u8_url = m3u8_url
        self.output_mp4 = os.path.realpath(output_file)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(loop.create_task(self.main()))


def parse_headers(header=[]):
    headers = {}
    for item in header:
        if ':' in item:
            part = item.split(':', 1)
            name = part[0].strip().lower()
            value = part[1].strip()
            headers[name] = value
    return headers


def parse_inputs():
    parser = argparse.ArgumentParser(description='可用参数如下：')
    parser.add_argument('input', help='本地文件路径或远程URL')
    parser.add_argument('output', help='输出文件的路径')
    parser.add_argument('--header', action='append', help='添加请求头。例如：--header="pragma: no-cache"')
    parser.add_argument('-x', '--proxy', help='设置代理。例如：-x 127.0.0.1:8888 或 --proxy 127.0.0.1:8888')
    args = parser.parse_args()

    input_url = args.input
    output = args.output
    header = args.header if args.header else []
    proxy = args.proxy
    downloader = Downloader(pool_size=10, headers=parse_headers(header), proxy=proxy)
    print('下载 ' + input_url)
    downloader.run(input_url, output)


if __name__ == '__main__':
    parse_inputs()
