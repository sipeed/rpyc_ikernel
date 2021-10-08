
<p align="center">
    <h1 align="center">💮 RPyC の IPykernel 🐹</h1>
</p>

[![MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![PyPI version](https://badge.fury.io/py/rpyc-ikernel.svg)](https://badge.fury.io/py/rpyc-ikernel)

[English](./readme.md)  | 简体中文

## 内核介绍

继承 IPythonKernel（iPython）类，以更少的占用（16~32M）支持低端硬件（armv7l）进行 Python 编程与实时图像、视频推流。

- 通过 [rpyc](https://github.com/tomerfiliba-org/rpyc) 实现远程调用（RPC）核心。

- 通过 [MaixPy3](https://github.com/sipeed/MaixPy3) 给远程机器建立 RPC 服务，传本地代码给远端（remote）运行。

- 通过 [rtsp+rtp](https://github.com/gabrieljablonski/rtsp-rtp-stream) 实现推流，支持摄像头（camera）与 PIL 图像（display）、文件（path）。

### 特殊函数

|  指令格式   | 指令功能  | 使用方法 |
|  ----  | ----  |  ----  |
| $connect("localhost")  | 连接到远端（remote）的 IP 地址（如："192.168.44.171:18812"） | [usage_display.ipynb](./examples/usage_display.ipynb) |
| $exec("code")  | 该（code）代码会在本地环境（local）下执行。 | [usage_exec.ipynb](./examples/usage_exec.ipynb) |

## 安装方法

按如下顺序说明：

- 给【远端 Python 】配置 rpyc 服务。
- 给【本地 Python 】安装 jupyter 环境。

## 给【远端 Python 】配置 rpyc 服务。

在你远端设备上使用 **ifconfig** 或 **ipconfig** 获取你的 IP 地址，请确保该地址可以 **ping** 通。

确保远端的设备配置为 **Python3** 环境，输入 `pip3 install maixpy3` 安装 **rpyc** 服务，复制下述指令运行即可启动服务。

```shell
maixpy3_rpycs &
```

此时你的 rpyc 服务已经起来了，请记住你的 IP 地址。

> 提示：本机也可以安装该服务，并使用 localhost 的 IP 地址作为远端机器进行连接。

## 给【本地 Python 】安装 jupyter 环境。

以 Python3 为例，请确保已经安装了 python3 和 pip3 基本环境/命令，在命令行下方调用该代码即可。

```shell
pip3 install rpyc_ikernel && python3 -m rpyc_ikernel.install
```

国内下载加速可以使用清华源。

```shell
pip3 install -i https://pypi.tuna.tsinghua.edu.cn/simple rpyc_ikernel && python3 -m rpyc_ikernel.install
```

上述包安装完成后，输入 `jupyter notebook` 会启动服务，启动后会自动打开系统默认浏览器（推荐国外谷歌浏览器或国内360极速浏览器），请选中 rpyc 的内核，新建（new）一个指定内核的代码文件。

![kernels.png](./images/kernels.png)

如果没有看到，则可以输入 `python3 -m rpyc_ikernel.install` 完成内核的安装，此时就可以看到了。

若出现如下找不到模块常见错误，常见于 py2 和 py3 环境不分，请确认系统环境变量是否为 python / pip 命令。

- `/usr/bin/python3: Error while finding module specification for 'rpyc-ikernel.install' (ModuleNotFoundError: No module named 'rpyc-ikernel')`
- `/usr/bin/python: No module named rpyc-ikernel`

> 有些机器环境变量的 python3 为 python ，或是并存多个版本的 python 和 pip ，那么此时就需要使用 python 指令。

可输入 `jupyter kernelspec list` 可以查看当前安装的 jupyter 内核，若是没有 rpyc 则没有安装该内核。

```shell
Available kernels:
  bash           /home/juwan/.local/share/jupyter/kernels/bash
  micropython    /home/juwan/.local/share/jupyter/kernels/micropython
  python3        /home/juwan/.local/share/jupyter/kernels/python3
  rpyc           /home/juwan/.local/share/jupyter/kernels/rpyc
```

## 在 Notebook 中运行 Python 代码

在运行代码前，请配置 IP 地址进行连接，否则默认连接到 "localhost" 的地址请求服务。

```python
$connect("192.168.43.44")
import platform
print(platform.uname())
```

可见返回结果如下：

```shell
uname_result(system='Linux', node='linux-lab', release='5.4.0-56-generic', version='#62-Ubuntu SMP Mon Nov 23 19:20:19 UTC 2020', machine='x86_64', processor='x86_64')
```

## 常见问题

可以通过以下顺序排查问题：

### 环境问题

当发现 Python 代码执行后没有反应，可以按以下步骤排查错误。

- 检查远端设备的 rpyc 服务是否存在/运行。（ps -a）
- 若在代码仍然运行时，按中断按钮未能停止，请刷新代码网页或重启内核，再尝试执行代码。
- 重启 jupyter 服务，重新连接远端设备执行代码。

如果仍然不行，则可能是网络问题，继续往下排查。

### 网络问题

确保本机可以连接到远端机器，使用 Ping 或 socket 等工具进行连接。

- 确定本机所属网络，试图 ping 通从机 IP 地址。
- 确定远端所属网络，试图 ping 通主机 IP 地址。
- 确保上级路由器转发规则没有对服务端口 18811、18812、18813 的限制。

### 其他问题

拔插网线或重启机器、复位硬件等重置操作。

## 设计灵感

该内核设计取自以下 Python 仓库。

- [ipykernel](https://github.com/ipython/ipykernel)
- [rpyc](https://github.com/tomerfiliba-org/rpyc)

参考内核如下。

- [bash_kernel](https://github.com/takluyver/bash_kernel)
- [ubit_kernel](https://github.com/takluyver/ubit_kernel)
- [remote_ikernel](https://github.com/tdaff/remote_ikernel)
- [jupyter_micropython_kernel](https://github.com/goatchurchprime/jupyter_micropython_kernel)

