#!/usr/bin/env python3
#coding: utf-8

import argparse
import asyncio
import hashlib
import math
import os
import re
import shutil
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional, Tuple, Union
from urllib import parse

import aiohttp
import m3u8
from Crypto.Cipher import AES

# See: https://github.com/encode/httpx/issues/914#issuecomment-622586610
if sys.version_info[0] == 3 and sys.version_info[1] >= 8 and sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _read_file(filepath):
    codecs = ['utf-8', 'gbk']
    for i, codec in enumerate(codecs):
        try:
            return Path(filepath).read_text(encoding=codec)
        except UnicodeDecodeError:
            if i == len(codecs) - 1:
                raise Exception(f'文件：\'{filepath}\' 解码失败。只支持文件编码：{"、".join(codecs)}')


def _calc_md5(s):
    data = s.encode('utf-8') if type(s) == str else s
    return hashlib.md5(data).hexdigest()


def _unique_filepath(filepath: Union[str, Path], isfile=True):
    filepath = Path(filepath)
    seq = 2
    new_filepath = filepath
    while new_filepath.exists():
        if isfile:
            new_filepath = filepath.with_name(f'{filepath.stem} ({seq}){filepath.suffix}')
        else:
            new_filepath = filepath.with_name(f'{filepath.name} ({seq})')
        seq += 1
    return new_filepath


def _runcmd(cmd: str, shell=False, show_window=False) -> Tuple[str, int]:
    try:
        import shlex
        import subprocess
        args = cmd if shell else shlex.split(cmd)
        startupinfo = None
        if os.name == 'nt' and not shell and not show_window:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        proc = subprocess.Popen(args, startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=shell)
        stdout, _ = proc.communicate()
        stdout = stdout.rstrip(b'\r\n')
        output = None
        try:
            output = stdout.decode('UTF-8')
        except Exception:
            output = stdout.decode('GBK')
        finally:
            if output is None:
                output = stdout.decode('UTF-8', errors='ignore')
        returncode = proc.returncode
    except Exception as e:
        output = str(e)
        returncode = 2
    return output, returncode


class M3U8Downloader:

    def __init__(
        self,
        pool_size: int = 10,
        headers: dict = {},
        download_m3u8_headers: dict = {},
        download_segment_headers: dict = {},
        segment_auto_referer: bool = False,
        max_retries: int = 3,
        proxy=None,
        concurrency: int = 1,
    ):
        self.pool_size = max(1, pool_size)
        self.headers = headers
        self.max_retries = max(0, max_retries)
        self.retries = 0
        if proxy and not proxy.startswith(('https://', 'http://')):
            proxy = f'http://{proxy}'
        self.proxy = proxy
        self.concurrency = concurrency
        self.download_m3u8_headers = download_m3u8_headers
        self.download_segment_headers = download_segment_headers
        self.segment_auto_referer = segment_auto_referer
        self.cache = {}
        self.succed = {}

    def _is_fmp4(self):
        return self.m3u8_obj.segment_map is not None

    def _is_encrypt(self):
        first_segment = self.m3u8_obj.segments[0]
        return hasattr(first_segment.key, 'uri') and first_segment.key.uri

    def _segment_basename(self, seg):
        byterange = self._parse_byterange(seg.byterange)
        url = f'{seg.uri}#{byterange[0]}-{byterange[1]}' if byterange else seg.uri
        return _calc_md5(url)

    def _parse_byterange(self, byterange) -> Optional[Tuple[int, int]]:
        if not byterange:
            return None
        result = re.search(r'(\d+)@(\d+)', byterange)
        if not result:
            return None
        offset = int(result.group(2))
        length = int(result.group(1))
        return offset, offset + length - 1

    def _build_segment_headers(self, url: str):
        headers = self.download_segment_headers if self.download_segment_headers else {}
        if self.segment_auto_referer and 'referer' not in self.session.headers and 'referer' not in headers:
            result = re.search(r'(https?://[^/\n\s]+)', url)
            referer = result.group(1) if result else ''
            headers.update({'referer': referer})
        return headers

    async def _load_m3u8(self, url):

        def resove(m3u8_obj):
            m3u8_obj.base_uri = '/'.join(os.path.dirname(url).split('\\')) + '/'
            for seg in m3u8_obj.segments:
                seg.uri = seg.absolute_uri
                if hasattr(seg.key, 'uri') and seg.key.uri:
                    seg.key.uri = seg.key.absolute_uri
                if seg.init_section:
                    seg.init_section.uri = seg.init_section.absolute_uri

        if not url.startswith(('https://', 'http://')):
            if not Path(url).is_file():
                raise Exception(f'找不到文件：\'{url}\'')
            text = _read_file(url)
            self.m3u8_md5 = _calc_md5(text)
            self.m3u8_obj = m3u8.loads(text)
            self.ts_total = len(self.m3u8_obj.segments)
            resove(self.m3u8_obj)
            return

        async with self.session.get(url, headers=self.download_m3u8_headers, proxy=self.proxy) as resp:
            text = await resp.text()
            assert resp.ok, f'下载："{url}"失败。状态码：{resp.status}'
            self.m3u8_md5 = _calc_md5(text)
            self.m3u8_obj = m3u8.loads(text)
            self.ts_total = len(self.m3u8_obj.segments)
            resove(self.m3u8_obj)

    async def _fetch_key(self, key_uri):
        key_uri = parse.urljoin(self.m3u8_obj.base_uri, key_uri)
        content = self.cache.get(key_uri)
        if not content:
            async with self.session.get(key_uri, headers=self._build_segment_headers(key_uri), proxy=self.proxy) as resp:
                if resp.ok:
                    content = await resp.read()
                    self.cache[key_uri] = content
                else:
                    print(f'无法下载key：{key_uri}')
                    sys.exit(1)
        return content

    async def _fetch_init_section(self, seg):
        if not seg.init_section:
            return b''
        section = seg.init_section
        url = section.uri
        if not url.startswith(('http://', 'https://')):
            filepath = self.download_dir.joinpath(url)
            assert filepath.exists(), f'找不到文件：{filepath}'
            return filepath.read_bytes()
        byterange = self._parse_byterange(section.byterange)
        key = f'{url}#{byterange[0]}-{byterange[1]}' if byterange else url

        content = self.cache.get(key)
        if not content:
            headers = self._build_segment_headers(url)
            if byterange:
                headers.update({'Range': f'bytes={byterange[0]}-{byterange[1]}'})
            async with self.session.get(url, headers=headers, proxy=self.proxy) as resp:
                if resp.ok:
                    content = await resp.read()
                    self.cache[key] = content
                    return content
                else:
                    print(f'无法下载init_section：{url}')
                    sys.exit(1)
        return content

    async def _fetch_segment(self, seg, index: int):
        url = seg.uri
        byterange = self._parse_byterange(seg.byterange)
        target_filepath = self.download_dir.joinpath(self._segment_basename(seg))
        if target_filepath.is_file():
            return
        assert not target_filepath.is_dir(), f'❌文件名已被占用，存在同名目录："{target_filepath}"'

        async def process(data):
            with NamedTemporaryFile(prefix=f'output{index}_', suffix='.raw', dir=self.download_dir, delete=False) as fp:
                fp.write(data)
            src_filepath = Path(fp.name)
            dst_filepath = await self._decrypt_segment(src_filepath, seg)
            self._extract_valid_data(dst_filepath)
            dst_filepath.rename(target_filepath)
            self.succed[index] = target_filepath
            # 更新进度条
            progress = math.floor(len(self.succed) / float(self.ts_total) * 100)
            progress_step = 2.5
            total_step = math.ceil(100.0 / progress_step)
            current_step = int(total_step * (progress / 100.0))
            s = "\r已下载 %d%% |%s%s| [%d/%d] " % (progress, "█" * current_step, " " * (total_step - current_step), len(self.succed), self.ts_total)
            sys.stdout.write(s)
            sys.stdout.flush()

        init_section_data = b''
        data = None
        async with self.lock:
            if not url.startswith(('https://', 'http://')):
                assert Path(url).is_file(), f'找不到文件："{url}"'
                data = Path(url).read_bytes()
            else:
                try:
                    init_section_data = await self._fetch_init_section(seg)
                    headers = self._build_segment_headers(url)
                    if byterange:
                        headers.update({'Range': f'bytes={byterange[0]}-{byterange[1]}'})
                    async with self.session.get(url, headers=headers, proxy=self.proxy) as resp:
                        if resp.ok:
                            data = await resp.read()
                        else:
                            print(f"\n下载失败: {url}")
                except Exception as e:
                    print(f'\'{url}\'下载失败。错误：{e}')
            if data:
                data = init_section_data + data
                await process(data)

    async def _download_segments(self):
        # 统计下载成功的片段
        self.succed = {}
        for index, seg in enumerate(self.m3u8_obj.segments):
            ts_path = self.download_dir.joinpath(self._segment_basename(seg))
            if ts_path.is_file():
                self.succed[index] = ts_path
        pending = len(self.m3u8_obj.segments) - len(self.succed)
        if pending == 0:
            return
        first_segment = self.m3u8_obj.segments[0]
        if self._is_encrypt():
            await self._fetch_key(first_segment.key.uri)
        if self._is_fmp4():
            await self._fetch_init_section(first_segment)
        while pending > 0:
            tasks = []
            for index, seg in enumerate(self.m3u8_obj.segments):
                if not self.succed.get(index):
                    tasks.append(asyncio.create_task(self._fetch_segment(seg, index)))
            await asyncio.wait(tasks)
            pending = len(self.m3u8_obj.segments) - len(self.succed)
            if pending > 0:
                if self.retries >= self.max_retries:
                    if self.retries > 0:
                        print(f'\n经过{self.retries}次尝试，还有{pending}个片段下载失败')
                    else:
                        print(f'\n还有{pending}个片段下载失败')
                    break
                self.retries += 1
                print(f'\n有{pending}个片段下载失败，3秒后开始第{self.retries}次重试..')
                await asyncio.sleep(3)
            else:
                print('')

    def _decrypt(self, in_filepath: Union[str, Path], out_filepath: Union[str, Path], iv, key):
        infile = Path(in_filepath)
        outfile = Path(out_filepath)
        chunk_size = AES.block_size * 1024
        cipher = AES.new(key, AES.MODE_CBC, iv)
        with outfile.open('wb') as outfp:
            with infile.open('rb') as infp:
                for chunk in iter(lambda: infp.read(chunk_size), b''):
                    try:
                        outfp.write(cipher.decrypt(chunk))
                    except Exception as e:
                        print(f'❌解密失败：{str(e)}')
                        sys.exit(1)

    async def _decrypt_segment(self, src_filepath: Union[str, Path], seg):
        src_filepath = Path(src_filepath)
        is_enc = hasattr(seg.key, 'uri') and seg.key.uri
        if not is_enc:
            return src_filepath
        if seg.key.iv:
            iv = '{:032x}'.format(int(str(seg.key.iv), 16))
        else:
            iv = '{:032x}'.format(int(str(self.m3u8_obj.segments.index(seg)), 16))
        iv = bytes.fromhex(iv)
        key_content = await self._fetch_key(seg.key.uri)
        dst_filepath = src_filepath.with_suffix('.dec')
        self._decrypt(src_filepath, dst_filepath, iv, key_content)
        src_filepath.unlink()
        return dst_filepath

    def _merge_segments(self):
        self.output_ts = self.download_dir.joinpath(f'{self.output_mp4.stem}.ts')
        with self.output_ts.open('wb') as fp:
            infiles = [Path(self.succed.get(i, '')) for i in range(self.ts_total)]
            num = 0
            while len(infiles) > 0:
                infile = infiles.pop(0)
                fp.write(infile.read_bytes())
                num += 1
                sys.stdout.write(f"\r合并视频片段 [{num}/{len(self.succed)}] ")
                sys.stdout.flush()
                if infile not in infiles:
                    infile.unlink()

    def _extract_valid_data(self, ts_path: Union[str, Path]):
        if self._is_fmp4():
            return
        ts_path = Path(ts_path)
        '''
        有的TS伪装成图片，下载到本地不能直接播放。根据TS文件格式特点，提取有效数据。
        '''
        with ts_path.open('r+b') as fp:
            data = fp.read()
            byte_list = list(data)
            MP2T_PACKET_LENGTH = 188
            SYNC_BYTE = 0x47
            left_index = 0
            right_index = MP2T_PACKET_LENGTH
            start = -1
            stop = -1
            while right_index < len(byte_list):
                if byte_list[left_index] == SYNC_BYTE and byte_list[right_index] == SYNC_BYTE:
                    if start == -1:
                        start = left_index
                    if right_index + MP2T_PACKET_LENGTH <= len(byte_list):
                        stop = right_index + MP2T_PACKET_LENGTH
                    else:
                        stop = right_index
                    left_index += MP2T_PACKET_LENGTH
                    right_index += MP2T_PACKET_LENGTH
                    continue
                left_index += 1
                right_index += 1
            if start == -1:
                raise Exception(f'发生错误！非法的TS文件：{ts_path}\n')
            fp.truncate(0)
            fp.seek(0)
            fp.write(data[start:stop])

    def _convert_to_mp4(self):
        if _runcmd('ffmpeg -version')[-1] != 0:
            print('检测到未安装ffmpeg，将跳过格式转换')
            return False
        if _runcmd('ffprobe -version')[-1] != 0:
            print('检测到未安装ffprobe，将跳过格式转换')
            return False
        cmd = f'ffprobe "{self.output_ts}"'
        output, returncode = _runcmd(cmd)
        if returncode != 0:
            raise Exception(f'❌检测编码失败：\n{output}')
        bit_stream_filter = '-bsf:a aac_adtstoasc' if 'Audio: aac' in output else ''
        self.output_mp4 = self.output_mp4.with_suffix('.mp4')
        self.output_mp4 = _unique_filepath(self.output_mp4)
        print('\n正在转换成mp4格式...')
        cmd = f'ffmpeg -i "{self.output_ts}" -c copy {bit_stream_filter} "{self.output_mp4}"'
        output, returncode = _runcmd(cmd)
        if returncode != 0:
            print(f'❌"{self.output_ts}" 转换成mp4格式失败。cmd："{cmd}"')
            return False
        return True

    async def _main(self):
        self.lock = asyncio.Semaphore(self.concurrency)
        conn = aiohttp.TCPConnector(limit=self.pool_size)
        timeout = aiohttp.ClientTimeout(total=None, connect=None, sock_connect=30, sock_read=60)
        async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
            self.session = session
            # 默认设置为移动端User-Agent
            self.session.headers.update({'user-agent': 'AppleCoreMedia/1.0.0.17D50 (iPhone; U; CPU OS 13_3_1 like Mac OS X; en_us)'})
            if self.headers:
                self.session.headers.update(self.headers)
            await self._load_m3u8(self.m3u8_url)
            if self.ts_total == 0:
                print('没有任何片段')
                sys.exit(1)
            self.download_dir = self.output_mp4.with_name(self.m3u8_md5)
            if not self.download_dir.is_dir():
                self.download_dir = _unique_filepath(self.download_dir, isfile=False)
                self.download_dir.mkdir(parents=True)
            await self._download_segments()
        self._merge_segments()
        if self._convert_to_mp4():
            shutil.rmtree(self.download_dir)
            print('已保存到：{}\n'.format(self.output_mp4))
        else:
            print('已保存到：{}\n'.format(self.output_ts))

    def run(self, m3u8_url: str, output_file: Union[Path, str]):
        if not m3u8_url:
            print('m3u8_url不能为空')
            sys.exit(1)
        if not output_file:
            print('output_file不能为空')
            sys.exit(1)
        self.m3u8_url = m3u8_url
        self.output_mp4 = Path(output_file).absolute()
        asyncio.run(self._main())


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
    parser.add_argument('input', help='本地文件路径或远程URL。如：./input.m3u8 或 https://example.com/test.m3u8')
    parser.add_argument('output', help='输出文件路径。如：./output.mp4')
    parser.add_argument('--header', action='append', default=[], help='默认请求头。例如：--header "pragma: no-cache"')
    parser.add_argument('--download-m3u8-header', action='append', default=[], help='指定下载m3u8文件时的请求头。例如：--header "referer: https://httpbin.org/"')
    parser.add_argument('--download-segment-header', action='append', default=[], help='指定下载分片时的请求头。例如：--header "referer: https://httpbin.org/"')
    parser.add_argument(
        '--segment-auto-referer', action='store_true', help='指定此选项，下载分片时自动设置referer请求头。如果--header参数或--download-segment-header参数已指定referer，此选项将失效。'
    )
    parser.add_argument('-x', '--proxy', help='设置代理。例如：-x 127.0.0.1:8888 或 --proxy 127.0.0.1:8888')
    parser.add_argument('-N', '--concurrency', type=int, default=3, help='下载并发数，默认：3')
    args = parser.parse_args()
    input_url = args.input
    output = args.output
    header = args.header
    proxy = args.proxy
    download_m3u8_header = args.download_m3u8_header
    download_segment_header = args.download_segment_header
    segment_auto_referer = args.segment_auto_referer
    concurrency = max(args.concurrency, 1)
    downloader = M3U8Downloader(
        pool_size=20,
        headers=parse_headers(header),
        download_m3u8_headers=parse_headers(download_m3u8_header),
        download_segment_headers=parse_headers(download_segment_header),
        segment_auto_referer=segment_auto_referer,
        concurrency=concurrency,
        proxy=proxy,
    )
    print('下载 ' + input_url)
    downloader.run(input_url, output)


def run_test():
    if sys.gettrace():
        # sys.argv.extend(
        #     [
        #         'https://devstreaming-cdn.apple.com/videos/streaming/examples/img_bipbop_adv_example_fmp4/v5/prog_index.m3u8',
        #         r'D:\fallrainy\Downloads\新建文件夹 (3)\output.mp4', '-N', '3'
        #     ]
        # )
        # sys.argv.extend(
        #     [
        #         'https://devstreaming-cdn.apple.com/videos/streaming/examples/img_bipbop_adv_example_ts/v5/prog_index.m3u8',
        #         r'D:\fallrainy\Downloads\新建文件夹 (3)\output.mp4', '-N', '3'
        #     ]
        # )
        # sys.argv.extend(
        #     ['https://cdn.jsdelivr.net/gh/nomeqc/static@main/video/encrypt.m3u8', r'D:\fallrainy\Downloads\新建文件夹 (3)\output2.mp4', '-N', '1']
        # )
        # sys.argv.extend(
        #     [
        #         'https://ccp-bj29-video-preview.oss-enet.aliyuncs.com/lt/0A394CE28A619BFDA16766E0B7865F028038916D_194328959__sha1_bj29/FHD/media.m3u8?di=bj29&dr=2389069&f=633a7672138027e8e9cb44b388c3c352f3795901&security-token=CAIS%2BgF1q6Ft5B2yfSjIr5f7EdL6j6pijvGRan7SjlUfftgZq62Tlzz2IHFPeHJrBeAYt%2FoxmW1X5vwSlq5rR4QAXlDfNSqoWGeFqVHPWZHInuDox55m4cTXNAr%2BIhr%2F29CoEIedZdjBe%2FCrRknZnytou9XTfimjWFrXWv%2Fgy%2BQQDLItUxK%2FcCBNCfpPOwJms7V6D3bKMuu3OROY6Qi5TmgQ41Uh1jgjtPzkkpfFtkGF1GeXkLFF%2B97DRbG%2FdNRpMZtFVNO44fd7bKKp0lQLukMWr%2Fwq3PIdp2ma447NWQlLnzyCMvvJ9OVDFyN0aKEnH7J%2Bq%2FzxhTPrMnpkSlacGoABMy8YHsm0fDZ1H3W5AA3PXtDWFAwiVLlktVaZQcjdnR%2BL6T01CulZw%2FUhpq2Wb3FfbxYJANjIH4GM36GlsYhsbF1Z89JGhEatKHuRefecQ2c4Bi3H3cUpk7Wd%2FG6YHSeYlUgC%2F1vIzg%2BgoKGXBwnDcAYL5OyqeDnDTgUAvjdcMkI%3D&u=27fad97991e046e4b9431eff0831cd3f&x-oss-access-key-id=STS.NTNZhNbuC93zhXcjUJrW5Dh8u&x-oss-additional-headers=referer&x-oss-expires=1664790452&x-oss-process=hls%2Fsign&x-oss-signature=IEE2k4XVdBw%2FyyQuMPmAC6hFqb98x%2FhoeuOYqHqH1ho%3D&x-oss-signature-version=OSS2',
        #         r'D:\fallrainy\Downloads\新建文件夹 (3)\愿某人1.mp4', '-N', '3', '--header', f'Referer: https://www.aliyundrive.com/'
        #     ]
        # )

        sys.argv.extend(
            [
                r'E:\MyDocuments\GitHub\my-mv\playlist\阿木 - 有一种爱叫做放手.m3u8', r'D:\fallrainy\Downloads\新建文件夹 (3)\愿某人1.mp4', '-N', '3', '--header',
                f'Referer: https://www.aliyundrive.com/'
            ]
        )


if __name__ == '__main__':
    # run_test()
    parse_inputs()
