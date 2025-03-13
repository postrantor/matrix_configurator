# AF-RED 配置工具

## 功能

1. 解析 DDS 通信矩阵，生成对应的 rosidl 消息定义文件
2. 解析 DDS 通信矩阵，生成对应的 app AF-RED 框架配置文件
3. 读取 AF-RED 配置文件，生成对应的框架代码

---

## How to use

### 1. 安装

```shell
pip install ./
```

![](documents/install.png)
可以将安装路径添加进 PATH，便于使用

---

### 2. 使用

#### 2.1 解析通信矩阵，生成消息定义文件、各个 app 的收发框架代码：

```shell
af_config -i <通信矩阵文件> -o <输出文件夹路径>
```

![](documents/af_config.png)

执行后生成文件目录接口如下：

![](documents/af_config_output.png)

#### 2.2 产物解释：

1. hav_interfaces：rosidl 数据类型定义文件
2. HPC\<x\>\_TDA4：各个 ECU 上的应用框架代码

具体到每个应用目录中：

1. orchestration：AF-RED 编排配置文件
2. include/src：框架代码
3. CMakeLists.txt/package.xml：编译安装配置

---

### 3. 手动调整

用户可修改前一步各个应用的 orchestration.yaml 文件，手动调整 publisher 与各个 Block 的对应关系、类名称、任务名称等，之后使用配置工具重新生成代码

与普通 af-red 编排配置文件相比，为生成代码，该文件有额外两点需求：

1. 需要指定 task 的 type，类型为'compute'、'timer'
2. 需要指定 input_topic/output_topic 的 type，格式为 type: hav_interfaces/msg/<消息类型>

![](documents/app_create_config.png)

#### 3.1 添加定时任务：

在 tasks 下添加一个新的任务，需要下列信息

```yaml
tasks:
-	name: <任务名称>
	block: /app_name/<类名称>
	count: -1 # 执行次数，-1代表永远执行
	interval: 100 # 执行周期，单位ms
	processor: 0 # 在哪个processor上执行
	priority: 0 # 任务在该processor上的优先级
	type: timer # 用于代码生成工具确定Block类型
	# 如果该定时任务有对外发送dds topic需求，使用output_topics
	output_topics:
		- name: <topic名称>
		  type: hav_interfaces/msg/<消息类型>
```

![](documents/timer_block.png)

#### 3.2 修改类型名称：

目前类型名称根据通信矩阵生成，用户可根据需要自行修改

修改方法：更改 task 的 block 字段:

```yaml
block: /app_name/<类名称>
```

![](documents/class_name.png)

#### 3.3 调整 publisher 与 Block 的对应关系：

目前配置文件中，根据通信矩阵定义生成了应用需要收发的 input_topics、output_topics；默认每个 input_topic 对应一个 ComputeBlock，所有的 output_topic 放在了同一个 block 下

用户可修改 output_topics 字段，来更改 publisher 与各个 task 的对应关系

#### 3.4 重新生成框架代码

手动调整 orchestration.yaml 后，可以使用 af red 配置工具重新生成框架代码

```shell
af_app_create -i <app路径>
```

af_app_create 工具会根据`<app路径>/orchestration/orchestration.yaml`文件，重新在 app 路径下生成框架代码(
manifest.yaml、hpp/cpp 框架代码、CMakeLists/package.xml 文件等)

![](documents/app_create.png)

---

### 4. 应用适配说明

#### 4.1 安装 SDK

如果已安装过 SDK，可跳过此步骤。SDK 需至少基于 HLA 迭代 11 版本（>v1.10.4）

1. 安装完后，需要先 `source environment-setup` 脚本再继续使用。

#### 4.2 编译消息定义文件

如果 SDK 中未集成消息定义文件，可手动对消息定义文件进行编译，生成相应数据结构接口。

1. `source environment-setup` 脚本，配置交叉编译环境

2. 进入到 hav_interfaces 目录，cmake config

注意：该步骤中`-DPYTHON_SOABI`和`-DPYTHON_INSTALL_DIR`两个变量需要与板端 python 环境相匹配

```shell
mkdir build
cd build
cmake .. -DPYTHON_EXECUTABLE=${PYTHON_EXECUTABLE} \
				-DPYTHON_SOABI=cpython-310-aarch64-linux-gnu \
				-DPYTHON_INSTALL_DIR=lib/python3.10/site-packages \
				-DCMAKE_INSTALL_PREFIX=/usr
make
```

![](documents/4.2-1.png)
![](documents/4.2-2.png)

3. 安装

```shell
make install DESTDIR=../install
```

![](documents/4.2-3.png)
![](documents/4.2-4.png)

#### 4.3 适配应用接口

以 HPC1_TDA4 上的 hi_lidar_prot_loc_hpcf1 应用为例

##### 4.3.1 接收 DDS 消息

根据通信矩阵 SubscriberConfig 页，HPC1_TDA4 hi_lidar_prot_loc_hpcf1 共订阅 4 个 DDS topic 消息。

![](documents/4.3-1.png)

AF DDS 工具链为每个订阅者生成一个`ComputeBlock`，用于接收 DDS 报文。

以收取 MBStatusInfomation_Event_Topic 报文的 ComputeBlock 为例，**用户需在对应的 Block 源码文件`on_message`函数中，填写收到报文后的处理逻辑**。

注意：该`std::shared_ptr`仅可在`on_message`函数中使用，请不要拷贝该智能指针。若需缓存消息，需要深拷贝实际的消息内容。

![](documents/4.3-2.png)

##### 4.3.2 发送 DDS 消息

根据通信矩阵 PublisherConfig 页，HPC1_TDA4 hi_lidar_prot_loc_hpcf1 共需发送 2 个 DDS topic 消息。

![](documents/4.3-3.png)

AF DDS 工具链会为这些需要发送的 DDS topic 生成对应的 ROS2 `publisher`，用户可调用对应`publisher`的`publish`方法对外发送 DDS 消息。

![](documents/4.3-4.png)

##### 4.3.3 编写每个 Block 的 `init()`/`shutdown()` 函数

每个 Block 都预留了`on_init()`与`on_shutdown()`接口，用于填写对应模块的初始化与反初始化逻辑。每个 Block 的`on_init()`仅会在程序初始化时执行一次，**注意不能执行耗时过长的任务**。每个 Block 的`on_shutdown()`会在程序退出时执行一次。

#### 4.4 编译用户应用

1. `source environment-setup` 脚本，配置交叉编译环境
2. 进入到用户应用目录，cmake config

```shell
mkdir build
cd build
cmake .. -DCMAKE_INSTALL_PREFIX=/usr
```

若 SDK 中未包含消息定义文件，在 cmake config 阶段还需指定 1.2 节编译出的消息库。

```shell
cmake .. -DCMAKE_INSTALL_PREFIX=/usr \
               -Dhav_interfaces_DIR=<消息定义安装目录>/usr/share/hav_interfaces/cmake
```

![](documents/4.4-1.png)

3. 编译&安装

```shell
make install DESTDIR=../install
```

![](documents/4.4-2.png)
