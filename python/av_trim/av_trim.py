#!/usr/bin/env python3
#coding: utf-8

import os
import sys
import glob


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
    _, exit_code = runcmd(cmd)
    return exit_code == 0

def get_video_duration(video_path):
    cmd = 'ffprobe -i "{}" -show_entries format=duration -v quiet -of csv="p=0"'.format(video_path)
    output, returncode = runcmd(cmd)
    if returncode == 0:
        return float(output.strip())
    print('error:{}. {} 无法获取时长'.format(output, video_path))
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
        new_filepath = os.path.join(output_dir, parts[0] + '' + parts[-1])
        new_filepath = make_path_unique(new_filepath)
        output, returncode = runcmd('ffmpeg -ss {} -i "{}" -t {} -c copy "{}"'.format(video_start, file_path, target_duration, new_filepath))
        if not returncode:
            print('裁剪成功，已保存到：' + new_filepath)
        else:
            print('裁剪 '+ file_path + ' 失败。\n' + output)


if __name__ == '__main__':
    if not ffmpeg_installed():
        print('请先安装ffmpeg')
        sys.exit()
    dir = '/Users/fallrainy/Home/python/ting55/album/大漠苍狼（王南）'
    files = glob.glob(os.path.join(dir, '*.m4a'))
    files =['/Users/fallrainy/Home/python/ting55/album/大漠苍狼（王南）/大漠苍狼（王南）第1集.m4a']
    clip_videos(video_files=files, head_duration=89, tail_duration=16, output_dir='/Users/fallrainy/Home/python/ting55/album/trim')

