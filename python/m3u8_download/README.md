# m3u8下载器
### 支持：
- 并发下载m3u8片段
- aes-128-cbc解密
- 自动转换成mp4格式(需要安装`ffmpeg`)
- 兼容python2和python3

# 下载
```bash
wget -O "m3u8-down.py" https://git.io/wl_m3u8down 
```
# 如何使用
```bash
python ./m3u8.py
```
或
```bash
python ./m3u8.py http://example.com/exp.m3u8 /home/video/exp.mp4
```
