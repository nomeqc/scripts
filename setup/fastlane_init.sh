#!/bin/bash
if [ -d "./fastlane" ]; then
  read -p "fastlane目录已存在，需要删除才可继续，是否删除？(yes/no):"
  if [ "$REPLY" != "yes" ]; then
  	exit
  fi
  rm -rf ./fastlane
fi

if [ -f "./Gemfile" ]; then
  read -p "Gemfile文件已存在，需要删除才可继续，是否删除？(yes/no):"
  if [ "$REPLY" != "yes" ]; then
  	exit
  fi
  rm -rf ./Gemfile
fi

mkdir ./fastlane
git clone https://github.com/Nomeqc/FastlaneTemplate.git ./fastlane
rm -rf ./fastlane/.git

curl -o ./Gemfile https://raw.githubusercontent.com/Nomeqc/Gemfiles/master/Gemfile