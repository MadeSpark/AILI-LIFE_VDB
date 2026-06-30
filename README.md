# AI记忆数据库

基于向量检索的AI记忆存储服务，支持在线API和本地模型，提供HTTP接口供易语言调用。

## 基本信息

- **服务地址**: `http://localhost:4321`（端口可在 config.json 中配置）
- **请求方法**: 所有接口均为 `POST`
- **请求格式**: `application/json`（body 中传递 JSON 参数）
- **响应格式**: `application/json`

## 快速开始

1. 将 `AI记忆数据库.exe` 和 `config.json` 放在同一目录
2. 修改 `config.json` 配置参数
3. 双击运行 exe，服务即启动

## 响应结构

所有接口返回统一的 JSON 结构：

```json
{
    "success": true,        // 操作是否成功
    "message": "描述信息",   // 操作结果描述
    "data": {}              // 返回数据（成功时有内容，失败时为 null）
}
```

---

## 接口列表

### 1. 服务信息

**接口地址**: `/`

**请求方法**: `POST`

**请求参数**: 无（body 可传空对象 `{}`）

**功能说明**: 获取服务运行状态和接口列表

**响应示例**:

```json
{
    "success": true,
    "message": "AI记忆数据库服务运行中",
    "data": {
        "接口列表": {
            "写入记忆": "POST /write_memory  (body: 备注, 记忆内容)",
            "查询记忆": "POST /query_memory  (body: 消息内容)",
            "删除记忆": "POST /delete_memory (body: 备注)",
            "记忆列表": "POST /list_memory   (body: 无)",
            "重建向量": "POST /rebuild_vectors (body: 无)"
        }
    }
}
```

---

### 2. 写入记忆

**接口地址**: `/write_memory`

**请求方法**: `POST`

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| 备注 | string | 是 | 记忆的唯一标识，相同备注会覆盖原有记忆 |
| 记忆内容 | string | 是 | 要存储的记忆文本内容 |

**请求示例**:

```json
{
    "备注": "user-123-preference",
    "记忆内容": "用户喜欢吃苹果，不喜欢吃香蕉"
}
```

**响应示例（成功）**:

```json
{
    "success": true,
    "message": "记忆写入成功：user-123-preference",
    "data": null
}
```

---

### 3. 查询记忆

**接口地址**: `/query_memory`

**请求方法**: `POST`

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| 消息内容 | string | 是 | 用于检索相关记忆的查询文本 |

**功能说明**: 根据语义相似度返回与查询文本相关的记忆列表，按相似度从高到低排序

**请求示例**:

```json
{
    "消息内容": "这个用户有什么饮食偏好"
}
```

**响应示例**:

```json
{
    "success": true,
    "message": "查询成功，共 3 条记忆",
    "data": [
        {
            "备注": "user-123-preference",
            "记忆内容": "用户喜欢吃苹果，不喜欢吃香蕉",
            "相似度": 0.8523
        },
        {
            "备注": "user-123-hobby",
            "记忆内容": "用户喜欢运动，特别是跑步",
            "相似度": 0.6234
        }
    ]
}
```

**相似度说明**:

| 相似度范围 | 含义 |
|------------|------|
| 0.9 ~ 1.0 | 高度相关，几乎同一件事 |
| 0.7 ~ 0.9 | 强相关，主题相同但细节有差异 |
| 0.5 ~ 0.7 | 中等相关，有一定关联 |
| 0.3 ~ 0.5 | 弱相关，仅有一点联系 |
| 0 ~ 0.3 | 几乎无关 |

---

### 4. 删除记忆

**接口地址**: `/delete_memory`

**请求方法**: `POST`

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| 备注 | string | 是 | 要删除的记忆的唯一标识 |

**请求示例**:

```json
{
    "备注": "user-123-preference"
}
```

**响应示例（成功）**:

```json
{
    "success": true,
    "message": "删除成功，共删除 1 条记忆",
    "data": null
}
```

---

### 5. 获取所有记忆列表

**接口地址**: `/list_memory`

**请求方法**: `POST`

**请求参数**: 无（body 可传空对象 `{}`）

**功能说明**: 获取所有记忆的列表，按写入顺序排列

**请求示例**:

```json
{}
```

**响应示例**:

```json
{
    "success": true,
    "message": "共 3 条记忆",
    "data": [
        {
            "备注": "user-123-preference",
            "记忆内容": "用户喜欢吃苹果，不喜欢吃香蕉"
        },
        {
            "备注": "user-123-hobby",
            "记忆内容": "用户喜欢运动，特别是跑步"
        }
    ]
}
```

---

### 6. 重建向量库

**接口地址**: `/rebuild_vectors`

**请求方法**: `POST`

**请求参数**: 无（body 可传空对象 `{}`）

**功能说明**: 手动触发重建所有记忆的向量。用于以下场景：
- 更换嵌入模型后需要重新生成向量
- 数据迁移后向量可能不一致
- 手动修复向量数据

**请求示例**:

```json
{}
```

**响应示例**:

```json
{
    "success": true,
    "message": "向量重建完成，共处理 50/50 条记忆",
    "data": {
        "重建数量": 50
    }
}
```

---

## 易语言调用示例

### 写入记忆

```e
.版本 2

.子程序 写入记忆
.参数 sRemark, 文本型
.参数 sContent, 文本型

.局部变量 hHttp, 整数型
.局部变量 sUrl, 文本型
.局部变量 sBody, 文本型
.局部变量 sResponse, 文本型

sUrl = "http://127.0.0.1:4321/write_memory"
sBody = "{""备注"":""" + sRemark + """, ""记忆内容"":""" + sContent + """}"

hHttp = WinHttp.创建 ()
WinHttp.设置请求头 (hHttp, "Content-Type", "application/json")
sResponse = WinHttp.发送请求 (hHttp, "POST", sUrl, sBody)
WinHttp.销毁 (hHttp)

返回 (sResponse)
```

### 查询记忆

```e
.版本 2

.子程序 查询记忆
.参数 sMessage, 文本型

.局部变量 hHttp, 整数型
.局部变量 sUrl, 文本型
.局部变量 sBody, 文本型
.局部变量 sResponse, 文本型

sUrl = "http://127.0.0.1:4321/query_memory"
sBody = "{""消息内容"":""" + sMessage + """}"

hHttp = WinHttp.创建 ()
WinHttp.设置请求头 (hHttp, "Content-Type", "application/json")
sResponse = WinHttp.发送请求 (hHttp, "POST", sUrl, sBody)
WinHttp.销毁 (hHttp)

返回 (sResponse)
```

---

## 配置说明

### config.json 配置项

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| 数据目录 | string | exe所在目录 | 数据库文件存放位置 |
| 本地模式 | string | "否" | "是"使用本地模型，"否"使用在线API |
| 本地模型名称 | string | "BAAI/bge-small-zh-v1.5" | 本地嵌入模型名称（HuggingFace） |
| 本地模型缓存目录 | string | exe所在目录 | 模型缓存路径 |
| HTTP端口 | number | 4321 | 服务监听端口 |
| API地址 | string | "https://api.siliconflow.cn" | 在线API地址 |
| APIKEY | string | 空 | 在线API密钥 |
| 模型名称 | string | "Qwen/Qwen3-Embedding-0.6B" | 在线模型名称 |

### 配置示例

```json
{
    "数据目录": "D:\\Data\\MemoryDB",
    "本地模式": "否",
    "本地模型名称": "BAAI/bge-small-zh-v1.5",
    "本地模型缓存目录": "",
    "HTTP端口": 4321,
    "API地址": "https://api.siliconflow.cn",
    "APIKEY": "sk-xxxxxxxxxxxxxxxx",
    "模型名称": "Qwen/Qwen3-Embedding-0.6B"
}
```

---

## 安装与运行

### 在线模式（默认）

在线模式使用 SiliconFlow 等 API 服务，无需本地安装大模型。

1. 安装依赖：
   ```bash
   uv sync
   ```
   
2. 运行服务：
   ```bash
   uv run python main.py
   ```
   
3. 编译exe：
   ```bash
   uv run pyinstaller --onefile --name "AI记忆数据库" --console main.py
   ```

### 本地模式

本地模式使用 `sentence-transformers` 加载本地嵌入模型，无需调用外部API。

#### 依赖安装步骤

**方法一：使用 uv 安装（推荐）**

```bash
# 安装本地模式额外依赖
uv sync --extra local
```

**方法二：使用 pip 安装**

```bash
# 安装基础依赖
pip install flask requests pyinstaller

# 安装本地模式依赖
pip install sentence-transformers torch transformers
```

#### 依赖版本要求

| 包名 | 版本要求 | 说明 |
|------|----------|------|
| `sentence-transformers` | >= 3.0.1 | 嵌入模型加载和推理 |
| `torch` | >= 2.0.0 | 深度学习框架 |
| `transformers` | >= 4.30.0 | HuggingFace模型支持 |

#### GPU 加速（可选）

如果有 NVIDIA GPU，可安装 CUDA 版本的 torch 以加速推理：

```bash
# CUDA 11.8
pip install torch --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

#### 运行步骤

1. 安装依赖（参考上方）
2. 修改 config.json：
   ```json
   {
       "本地模式": "是",
       "本地模型名称": "BAAI/bge-small-zh-v1.5",
       "本地模型缓存目录": "D:\\Models"
   }
   ```
3. 运行服务：
   ```bash
   uv run python main.py
   ```

首次运行会自动下载模型（约 100MB），下载完成后模型会缓存到指定目录。

---

## 注意事项

1. **备注唯一性**: 相同备注的记忆会被覆盖，写入前请确认备注是否已存在
2. **向量重建**: 更换模型后启动服务会自动重建向量，大量记忆时可能耗时较长
3. **本地模式**: 需要安装 `sentence-transformers` 和 `torch`，首次加载模型需要下载
4. **端口冲突**: 确保 HTTP端口 未被其他程序占用
5. **数据安全**: config.json 包含 APIKEY，请勿上传到公开仓库