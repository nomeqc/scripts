import base64
import datetime
import hashlib
import hmac
import json
import math
import mimetypes
import os
import sys
from random import choice

import requests
import xmltodict


class MuseUploader():

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.session = self.create_session()
        self.device_id = ''.join([choice("0123456789abcdef") for i in range(11)])
        self.create_info = {}
        self.token_info = {}
        self.oss_user_agent = 'aliyun-sdk-js/6.16.0 Chrome 98.0.4758.82 on Windows 10 64-bit'
        self.init_multipart_result = {}
        self.multipart_upload_record = {}
        self.debug = False

    def create_session(self):
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=3, pool_maxsize=3, max_retries=3)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def run(self):
        self.create()
        self.get_upload_token()
        self.upload()
        self.add()
        self.finish()
        self.get_share_info()
        return self.create_info.get('code')

    def check_response(self, resp):
        resp.raise_for_status()
        data = resp.json()
        if int(data.get('code')) != 0:
            message = data.get('message')
            raise Exception(f'出错了！"{message}"')

    def create(self):
        url = "https://service.tezign.com/transfer/share/create"
        payload = {
            "title": f'无主题 - {os.path.basename(self.filepath)}',
            "titleType": 0,
            "expire": "7",
            "customBackground": 0
        }
        headers = {
            'Connection': 'keep-alive',
            'sec-ch-ua': '"(Not(A:Brand";v="8", "Chromium";v="98", "Google Chrome";v="98"',
            'Accept': 'application/json',
            'x-transfer-device': self.device_id,
            'sec-ch-ua-mobile': '?0',
            'Content-Type': 'application/json;charset=UTF-8',
            'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82 Safari/537.36',
            'sec-ch-ua-platform': '"Windows"',
            'Origin': 'https://musetransfer.com',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://musetransfer.com/',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }
        response = self.session.request("POST", url, headers=headers, data=json.dumps(payload))
        self.check_response(response)
        data = response.json()
        self.create_info = data.get('result')
        if self.debug:
            print(response.text)

    def make_digest(self, message, key):
        key = bytes(key, 'UTF-8')
        message = bytes(message, 'UTF-8')

        digester = hmac.new(key, message, hashlib.sha1)
        signature1 = digester.digest()

        signature2 = base64.b64encode(signature1)

        return str(signature2, 'UTF-8')

    def get_upload_token(self):
        url = "https://service.tezign.com/transfer/asset/getUploadToken"
        payload = {}
        headers = {
            'Connection': 'keep-alive',
            'sec-ch-ua': '"(Not(A:Brand";v="8", "Chromium";v="98", "Google Chrome";v="98"',
            'x-transfer-device': self.device_id,
            'sec-ch-ua-mobile': '?0',
            'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82 Safari/537.36',
            'sec-ch-ua-platform': '"Windows"',
            'Accept': '*/*',
            'Origin': 'https://musetransfer.com',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://musetransfer.com/',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }

        response = self.session.request("GET", url, headers=headers, data=payload)
        self.check_response(response)
        data = response.json()
        self.token_info = data.get('result', {})
        if self.debug:
            print(response.text)

    def build_auth_headers(self, method: str, request_uri: str, content_md5: str = None, content_type: str = None):
        access_key_id = self.token_info.get('accessKeyId')
        security_token = self.token_info.get('securityToken')
        GMT_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'
        gmt_datetime_str = datetime.datetime.utcnow().strftime(GMT_FORMAT)
        arr = [
            f'{method.upper()}',
        ]
        if content_md5:
            arr.append(content_md5)
        else:
            arr.append('')
        if content_type:
            arr.append(content_type.lower())
        else:
            arr.append('')
        arr.append(gmt_datetime_str)
        arr.append(f'x-oss-date:{gmt_datetime_str}')
        arr.append(f'x-oss-security-token:{security_token}')
        arr.append(f'x-oss-user-agent:{self.oss_user_agent}')
        arr.append(f'/transfer-private{request_uri}'.rstrip('='))
        message = '\n'.join(arr)
        if self.debug:
            print('------------------------------------')
            print(message)
            print('------------------------------------')
        signature = self.make_digest(message, self.token_info.get('accessKeySecret'))
        headers = {
            'x-oss-user-agent': self.oss_user_agent,
            'x-oss-date': gmt_datetime_str,
            'x-oss-security-token': security_token,
            'authorization': f'OSS {access_key_id}:{signature}'
        }
        return headers

    def upload(self):
        filesize = os.path.getsize(self.filepath)
        trunk_size = int(1024 * 1024 * 3)
        n = math.ceil(filesize / trunk_size)
        if n > 1:
            self.initiate_multipart_upload()
            with open(self.filepath, 'rb') as fp:
                i = 0
                for chunk in iter(lambda: fp.read(trunk_size), b''):
                    i += 1
                    self.upload_part(chunk, i)
                    sys.stdout.write('\r已上传分片：{}/{}  '.format(i, n))
                    sys.stdout.flush()
            print('')
            if self.debug:
                print(self.multipart_upload_record)
            self.submit_parts()
        else:
            self.upload_single()

    def upload_single(self):
        headers = {
            'Connection': 'keep-alive',
            'sec-ch-ua-mobile': '?0',
            'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82 Safari/537.36',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua': '"(Not(A:Brand";v="8", "Chromium";v="98", "Google Chrome";v="98"',
            'Accept': '*/*',
            'Origin': 'https://musetransfer.com',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://musetransfer.com/',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        with open(self.filepath, 'rb') as fp:
            data = fp.read()
        upload_path = self.create_info.get('uploadPath')
        request_uri = f'/{upload_path}{os.path.basename(self.filepath)}'
        auth_headers = self.build_auth_headers(method='PUT', request_uri=request_uri)
        headers.update(auth_headers)
        response = self.session.put(f'https://share-file.tezign.com{request_uri}', headers=headers, data=data)
        # self.check_response(response)
        etag = response.headers.get('ETag')
        if not etag:
            raise Exception(f'上传文件异常')

    def initiate_multipart_upload(self):
        upload_path = self.create_info.get('uploadPath')
        basename = os.path.basename(self.filepath)
        request_uri = f'/{upload_path}{basename}?uploads='
        url = f"https://share-file.tezign.com{request_uri}"
        headers = {
            'Connection': 'keep-alive',
            'Content-Length': '0',
            'sec-ch-ua-mobile': '?0',
            'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82 Safari/537.36',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua': '"(Not(A:Brand";v="8", "Chromium";v="98", "Google Chrome";v="98"',
            'Accept': '*/*',
            'Origin': 'https://musetransfer.com',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://musetransfer.com/',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }
        auth_headers = self.build_auth_headers(method='POST', request_uri=request_uri)
        headers.update(auth_headers)
        response = self.session.request("POST", url, headers=headers)
        result = xmltodict.parse(response.text)
        upload_result = result['InitiateMultipartUploadResult']
        self.init_multipart_result['Bucket'] = upload_result['Bucket']
        self.init_multipart_result['Key'] = upload_result['Key']
        self.init_multipart_result['UploadId'] = upload_result['UploadId']
        if self.debug:
            print(response.text)

    def upload_part(self, data, part_number):
        headers = {
            'Connection': 'keep-alive',
            'sec-ch-ua-mobile': '?0',
            'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82 Safari/537.36',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua': '"(Not(A:Brand";v="8", "Chromium";v="98", "Google Chrome";v="98"',
            'Accept': '*/*',
            'Origin': 'https://musetransfer.com',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://musetransfer.com/',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        key = self.init_multipart_result.get('Key')
        upload_id = self.init_multipart_result.get('UploadId')
        request_uri = f'/{key}?partNumber={part_number}&uploadId={upload_id}'
        url = f'https://share-file.tezign.com{request_uri}'
        content_type, _ = mimetypes.guess_type(request_uri)
        content_type = content_type if content_type else 'application/octet-stream'
        auth_headers = self.build_auth_headers(method='PUT', content_type=content_type, request_uri=request_uri)
        headers['Content-Type'] = content_type
        headers.update(auth_headers)
        response = self.session.put(url, headers=headers, data=data)
        response.raise_for_status()
        etag = response.headers.get('ETag', '')
        if not etag:
            raise Exception(f'上传文件异常：partNumber:{part_number}')
        self.multipart_upload_record[str(part_number)] = etag

    def submit_parts(self):
        headers = {
            'Connection': 'keep-alive',
            'sec-ch-ua-mobile': '?0',
            'Content-Type': 'application/xml',
            'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82 Safari/537.36',
            'sec-ch-ua': '"(Not(A:Brand";v="8", "Chromium";v="98", "Google Chrome";v="98"',
            'sec-ch-ua-platform': '"Windows"',
            'Accept': '*/*',
            'Origin': 'https://musetransfer.com',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://musetransfer.com/',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        key = self.init_multipart_result.get('Key')
        upload_id = self.init_multipart_result.get('UploadId')
        request_uri = f'/{key}?uploadId={upload_id}'
        url = f'https://share-file.tezign.com{request_uri}'
        content_type = 'application/xml'
        payload_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<CompleteMultipartUpload>']
        for i in range(1, len(self.multipart_upload_record) + 1):
            etag = self.multipart_upload_record.get(str(i))
            payload_lines.extend(['<Part>', f'<PartNumber>{i}</PartNumber>', f'<ETag>{etag}</ETag>', '</Part>'])
        payload_lines.append('</CompleteMultipartUpload>')
        data = '\n'.join(payload_lines)
        if self.debug:
            print('submit:' + data)
        md5 = hashlib.md5()
        md5.update(data.encode('utf-8'))
        md5_b64 = base64.b64encode(md5.digest()).decode('ascii')
        auth_headers = self.build_auth_headers(
            method='POST', content_md5=md5_b64, content_type=content_type, request_uri=request_uri
        )
        headers['Content-MD5'] = md5_b64
        headers.update(auth_headers)
        response = self.session.post(url, headers=headers, data=data)
        if self.debug:
            print(response.text)

    def add(self):
        headers = {
            'Connection': 'keep-alive',
            'sec-ch-ua': '"(Not(A:Brand";v="8", "Chromium";v="98", "Google Chrome";v="98"',
            'Accept': 'application/json',
            'x-transfer-device': self.device_id,
            'sec-ch-ua-mobile': '?0',
            'Content-Type': 'application/json;charset=UTF-8',
            'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82 Safari/537.36',
            'sec-ch-ua-platform': '"Windows"',
            'Origin': 'https://musetransfer.com',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://musetransfer.com/',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        code = self.create_info.get('code')
        path = self.create_info.get('uploadPath', '') + os.path.basename(self.filepath)
        basename = os.path.basename(path)
        ext = os.path.splitext(basename)[-1][1:]
        ext = ext if ext else basename
        data = {'code': code, 'path': path, 'name': basename, 'type': ext, 'size': os.path.getsize(self.filepath)}
        response = self.session.post(
            'https://service.tezign.com/transfer/asset/add', headers=headers, data=json.dumps(data)
        )
        self.check_response(response)
        resp_data = response.json()
        self.asset_id = resp_data.get('result', {}).get('id', 0)
        assert self.asset_id > 0

    def finish(self):
        headers = {
            'Connection': 'keep-alive',
            'sec-ch-ua': '"(Not(A:Brand";v="8", "Chromium";v="98", "Google Chrome";v="98"',
            'Accept': 'application/json',
            'x-transfer-device': self.device_id,
            'sec-ch-ua-mobile': '?0',
            'Content-Type': 'application/json;charset=UTF-8',
            'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82 Safari/537.36',
            'sec-ch-ua-platform': '"Windows"',
            'Origin': 'https://musetransfer.com',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://musetransfer.com/',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        code = self.create_info.get('code')
        data = {'code': code, 'assetIds': [self.asset_id]}
        response = self.session.post(
            'https://service.tezign.com/transfer/share/finish', headers=headers, data=json.dumps(data)
        )
        self.check_response(response)

    def get_share_info(self):
        headers = {
            'Connection': 'keep-alive',
            'sec-ch-ua': '"(Not(A:Brand";v="8", "Chromium";v="98", "Google Chrome";v="98"',
            'Accept': 'application/json',
            'x-transfer-device': self.device_id,
            'sec-ch-ua-mobile': '?0',
            'Content-Type': 'application/json;charset=UTF-8',
            'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82 Safari/537.36',
            'sec-ch-ua-platform': '"Windows"',
            'Origin': 'https://musetransfer.com',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://musetransfer.com/',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        code = self.create_info.get('code')
        data = {'code': code}
        response = self.session.post(
            'https://service.tezign.com/transfer/share/get', headers=headers, data=json.dumps(data)
        )
        self.check_response(response)
        if self.debug:
            print(response.json())


def get_download_url(code):
    url = "https://service.tezign.com/transfer/share/download"
    device_id = ''.join([choice("0123456789abcdef") for i in range(11)])
    payload = {'code': code}
    headers = {
        'Connection': 'keep-alive',
        'sec-ch-ua': '"(Not(A:Brand";v="8", "Chromium";v="98", "Google Chrome";v="98"',
        'Accept': 'application/json',
        'x-transfer-device': device_id,
        'sec-ch-ua-mobile': '?0',
        'Content-Type': 'application/json;charset=UTF-8',
        'User-Agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82 Safari/537.36',
        'sec-ch-ua-platform': '"Windows"',
        'Origin': 'https://musetransfer.com',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'Referer': 'https://musetransfer.com/',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
    }
    response = requests.request("POST", url, headers=headers, data=json.dumps(payload))
    print(response.text)


def upload(filepath='', debug=False):
    uploader = MuseUploader(filepath=filepath)
    uploader.debug = debug
    return uploader.run()


if __name__ == '__main__':
    filepath = r'F:\Developer\Python\Test\a_cake\tts\parse\my_work (11)\output.mp4'
    code = upload(filepath=filepath, debug=False)
    print(f'上传成功！文件下载地址：https://musetransfer.com/s/{code}')
