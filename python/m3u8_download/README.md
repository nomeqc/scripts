# m3u8下载器
### 要求
- python3.6+

### 支持：
- 并发下载m3u8片段
- aes-128-cbc解密
- 自动转换成mp4格式(需要安装`ffmpeg`)

# 下载
```bash
wget -O m3u8down.py https://git.io/m3u8down 
```
# 如何使用
```bash
python ./m3u8down.py
```
或
```bash
python ./m3u8down.py https://cdn.jsdelivr.net/gh/Nomeqc/static/video/%E4%BA%BA%E7%94%9F%E6%B0%B8%E8%BF%9C%E6%B2%A1%E6%9C%89%E5%A4%AA%E6%99%9A%E7%9A%84%E5%BC%80%E5%A7%8B.m3u8 人生永远没有太晚的开始.m3u8
```
