#!/bin/bash
video=$1
audio=$2
output=$3
ffmpeg -i "${video}" -i "${audio}" -vcodec copy -acodec copy "${output}"