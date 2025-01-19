#!/bin/bash
# 创建一个固定名称的 Docker 容器，并在需要时启动或创建它

CONTAINER_NAME="grobid_custom"
IMAGE_NAME="grobid/grobid:0.8.1" # 原始镜像名，或使用您自定义的镜像名

if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker before running Grobid."
    exit 1
fi

# 检查容器是否已经存在
if docker ps -a --format '{{.Names}}' | grep -w "$CONTAINER_NAME" > /dev/null; then
    echo "Container $CONTAINER_NAME already exists."

    # 检查容器是否正在运行
    if docker ps --format '{{.Names}}' | grep -w "$CONTAINER_NAME" > /dev/null; then
        echo "Container $CONTAINER_NAME is already running."
    else
        echo "Starting existing container $CONTAINER_NAME..."
        docker start "$CONTAINER_NAME"
    fi
else
    echo "Creating a new container with name $CONTAINER_NAME..."
    machine_arch=$(uname -m)

    if [ "$machine_arch" == "armv7l" ] || [ "$machine_arch" == "aarch64" ]; then
        docker create --name "$CONTAINER_NAME" --gpus all --init --ulimit core=0 -p 8070:8070 "$IMAGE_NAME-arm"
    else
        docker create --name "$CONTAINER_NAME" --gpus all --init --ulimit core=0 -p 8070:8070 "$IMAGE_NAME"
    fi

    echo "Starting the new container $CONTAINER_NAME..."
    docker start "$CONTAINER_NAME"
fi
