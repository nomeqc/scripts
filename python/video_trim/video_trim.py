#!/usr/bin/env python3
#coding: utf-8

import os
import math
import shlex
import subprocess
import sys
import chardet
import platform

def runcmd(cmd):
    try:
        if platform.system().lower() == 'windows':
            # print('cmd: {}'.format(cmd))
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        else:
            # 将命令字符串转换为数组
            args = shlex.split(cmd)
            # print('args: {}'.format(args))
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
    output = output.decode(encoding)

    encoding = chardet.detect(error)['encoding']
    encoding = encoding if encoding else 'utf-8'
    error = error.decode(encoding)

    return output, error, returncode

def make_path_unique(path, isfile=True):
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

def ffmpeg_installed():
    cmd = 'ffmpeg -version'
    _,_,exit_code = runcmd(cmd)
    if exit_code == 0:
        return True
    return False

def get_video_duration(video_path):
    cmd = 'ffprobe -i {} -show_entries format=duration -v quiet -of csv="p=0"'.format(video_path)
    output, error, exit_code = runcmd(cmd)
    if exit_code == 0:
        output = output.replace('\n', '')
        return float(output)
    print('error:{}. {} 无法获取时长'.format(error, video_path))
    sys.exit()

def clip_videos(video_files=[], head_duration = 0, tail_duration = 0, output_dir=""):
    if head_duration + tail_duration < 1:
        print('切割的总长度太短')
        return
    if  not os.path.exists(output_dir):
        print('输出目录 "{}" 不存在'.format(output_dir))
        return
    if not os.path.isdir(output_dir):
        print('"{}" 不是目录'.format(output_dir))
        return
    for f in video_files:
        file_path = f

        video_duration = get_video_duration(file_path)
        if(head_duration + tail_duration >= video_duration):
            print('(片头 + 片尾)长度超过总时长，将跳过 ' + file_path)
            continue
        video_start = '{:02d}:{:02d}:{:02d}'.format(int(head_duration) // 3600, int(head_duration) % 3600 // 60, int(head_duration) % 3600 % 60)
        target_duration = video_duration - head_duration - tail_duration
        parts = os.path.splitext(os.path.basename(file_path))
        new_filepath = os.path.join(output_dir, parts[0] + '_trim' + parts[-1])
        new_filepath = make_path_unique(new_filepath)
        _, error, exit_code = runcmd('ffmpeg -ss {} -i "{}" -t {} -c copy "{}"'.format(video_start, file_path, target_duration, new_filepath))
        if not exit_code:
            print('裁剪成功，已保存到：' + new_filepath)
        else:
            print('裁`剪 '+ file_path + ' 失败。\n' + error)


if __name__ == '__main__':
    if not ffmpeg_installed():
        print('请先安装ffmpeg')
        sys.exit()
    '''
     示例：
     将 E:/Downloader/m3u8DL/Downloads 目录下的 "古董局中局2-第31集.mp4" 和 "古董局中局2-第32集.mp4"
     截去开头119秒，截去结尾237秒，保存在 E:/Downloader/m3u8DL/Downloads/trim 目录
    '''
    input_dir = 'E:/Downloader/m3u8DL/Downloads'
    output_dir = 'E:/Downloader/m3u8DL/Downloads/trim'
    head_duration = 119
    tail_duration = 237
    ep_start = 31
    ep_end = 32
    filename_template = '古董局中局2-第{ep_number}集.mp4'

    files = [os.path.join(input_dir, filename_template.format(ep_number=i)) for i in list(range(ep_start, ep_end + 1))]
    clip_videos(video_files=files, head_duration=head_duration, tail_duration=tail_duration, output_dir=output_dir)

    
