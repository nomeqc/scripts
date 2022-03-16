# m3u8下载器
### 要求
- python3.6+

### 支持：
- 并发下载m3u8片段
- aes-128-cbc解密
- 自动转换成mp4格式(需要安装`ffmpeg`)
- 支持自定义请求头
- 支持设置代理

# 下载
```sh
wget -O m3u8down.py https://git.io/m3u8down 
```
# 如何使用

```sh
python ./m3u8down.py https://cdn.jsdelivr.net/gh/Nomeqc/static@master/video/encrypt.m3u8 ./enc.mp4 --header="pragma: no-cache" --proxy http://127.0.0.1:10809
```
