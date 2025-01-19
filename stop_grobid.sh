#!/bin/bash
# 关闭grobid容器

CONTAINER_NAME="grobid_custom"
IMAGE_NAME="grobid/grobid:0.8.1" # 原始镜像名，或使用您自定义的镜像名

if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker before running Grobid."
    exit 1
fi

# 检查容器是否已经存在
if docker ps -a --format '{{.Names}}' | grep -w "$CONTAINER_NAME" > /dev/null; then
    # 检查容器是否正在运行
    if docker ps --format '{{.Names}}' | grep -w "$CONTAINER_NAME" > /dev/null; then
        docker stop "$CONTAINER_NAME"
    else
        echo "Container $CONTAINER_NAME does not exist."
    fi
else
    echo "Container $CONTAINER_NAME does not exist."
fi
