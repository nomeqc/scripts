#!/bin/bash
IFS=$'\n'
i=0
# 移除所有源
gem source -l | while read -r line
do
	if [ $i -gt 1 ]; then
		gem source -r $line
	fi
    let i++
done
# 添加Ruby China源
gem source -a https://gems.ruby-china.com/