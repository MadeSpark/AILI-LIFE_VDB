import os
import sys
import json
import math
import logging
import sqlite3
import threading
from array import array
from datetime import datetime

import requests
from flask import Flask, request, jsonify

# 屏蔽 Flask/Werkzeug 默认请求日志，用自定义格式替代
logging.getLogger('werkzeug').setLevel(logging.ERROR)


def log(msg):
    """带时间戳的控制台输出"""
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] {msg}", flush=True)


def format_body(text):
    """尝试格式化 JSON 为易读形式（中文不转义）"""
    if not text:
        return ''
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    except Exception:
        return text


def get_base_dir():
    """获取程序所在目录（兼容 PyInstaller 打包后的 exe）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def parse_yes_no(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {'是', 'true', '1', 'yes', 'y', 'on'}:
        return True
    if text in {'否', 'false', '0', 'no', 'n', 'off'}:
        return False
    return default


def resolve_dir_path(value, base_dir, create=False):
    """解析目录路径，空值时回落到base_dir，create=True时自动创建目录。"""
    text = str(value or '').strip()
    if not text:
        return base_dir
    path = text
    if not os.path.isabs(path):
        path = os.path.join(base_dir, path)
    path = os.path.abspath(path)
    if create:
        os.makedirs(path, exist_ok=True)
    elif not os.path.isdir(path):
        return base_dir
    return path


def load_config():
    """读取当前目录下的 config.json，不存在则创建默认配置。"""
    base_dir = get_base_dir()
    config_path = os.path.join(base_dir, 'config.json')
    if not os.path.exists(config_path):
        default_config = {
            "数据目录": base_dir,
            "本地模式": "否",
            "本地模型名称": "BAAI/bge-small-zh-v1.5",
            "本地模型缓存目录": base_dir,
            "HTTP端口": 4321,
            "API地址": "https://api.siliconflow.cn",
            "APIKEY": "",
            "模型名称": "Qwen/Qwen3-Embedding-0.6B"
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=4)
        print(f"未找到配置文件，已生成默认配置: {config_path}")
        print("请填写 APIKEY 等参数后重新启动。")
        input("按回车键退出...")
        sys.exit(0)
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


CONFIG = load_config()
BASE_DIR = get_base_dir()
DATA_DIR = resolve_dir_path(CONFIG.get('数据目录'), BASE_DIR)
HTTP_PORT = int(CONFIG['HTTP端口'])
API_URL = str(CONFIG['API地址']).rstrip('/')
API_KEY = CONFIG['APIKEY']
MODEL_NAME = CONFIG['模型名称']
LOCAL_MODE = parse_yes_no(CONFIG.get('本地模式'), default=False)
LOCAL_MODEL_NAME = str(CONFIG.get('本地模型名称') or "BAAI/bge-small-zh-v1.5")
LOCAL_MODEL_CACHE_DIR = resolve_dir_path(CONFIG.get('本地模型缓存目录'), BASE_DIR, create=True)

os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, 'memory.db')

db_lock = threading.Lock()

EMBEDDER = None
if LOCAL_MODE:
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as e:
        print(f"本地模式启动失败：缺少依赖 sentence-transformers（{e}）")
        print("请先安装依赖：pip install sentence-transformers torch transformers")
        input("按回车键退出...")
        sys.exit(0)
    kwargs = {}
    if LOCAL_MODEL_CACHE_DIR:
        kwargs["cache_folder"] = LOCAL_MODEL_CACHE_DIR
    EMBEDDER = SentenceTransformer(LOCAL_MODEL_NAME, **kwargs)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        '''CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            remark TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            vector BLOB NOT NULL
        )'''
    )
    c.execute(
        '''CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )'''
    )
    conn.commit()
    conn.close()


init_db()


def get_meta(key, default=None):
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT value FROM meta WHERE key = ?', (key,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else default


def set_meta(key, value):
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)', (key, value))
        conn.commit()
        conn.close()


def get_current_model_name():
    return LOCAL_MODEL_NAME if LOCAL_MODE else MODEL_NAME


def rebuild_vectors_if_needed():
    current_model = get_current_model_name()
    saved_model = get_meta('model_name')
    if saved_model == current_model:
        return
    log(f"检测到模型变更：{saved_model or '无'} → {current_model}，开始重建向量...")
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT id, content FROM memories ORDER BY id')
        rows = c.fetchall()
        total = len(rows)
        if total == 0:
            c.execute('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)', ('model_name', current_model))
            conn.commit()
            conn.close()
            log("无记忆数据，跳过重建")
            return
        count = 0
        for mid, content in rows:
            try:
                vector = get_embedding(content)
                vec_bytes = vector.tobytes()
                c.execute('UPDATE memories SET vector = ? WHERE id = ?', (vec_bytes, mid))
                count += 1
                if count % 10 == 0 or count == total:
                    log(f"重建进度: {count}/{total}")
            except Exception as e:
                log(f"重建失败(id={mid}): {e}")
        c.execute('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)', ('model_name', current_model))
        conn.commit()
        conn.close()
    log(f"向量重建完成，共处理 {count}/{total} 条记忆")


rebuild_vectors_if_needed()


def get_embedding(text):
    """调用在线嵌入模型获取向量，返回 array('f') 以便序列化为字节"""
    if LOCAL_MODE:
        vec = EMBEDDER.encode([text], normalize_embeddings=True)
        return array('f', [float(x) for x in vec[0]])
    url = f"{API_URL}/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "input": text
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    embedding = data['data'][0]['embedding']
    return array('f', embedding)


def cosine_similarity(vec1, vec2):
    """纯 Python 实现的余弦相似度，vec1/vec2 为 array('f')"""
    dot = 0.0
    norm1 = 0.0
    norm2 = 0.0
    for a, b in zip(vec1, vec2):
        dot += a * b
        norm1 += a * a
        norm2 += b * b
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (math.sqrt(norm1) * math.sqrt(norm2))


app = Flask(__name__)


@app.before_request
def log_request():
    """记录每个请求的方法、路径和请求体"""
    if request.method == 'OPTIONS':
        return
    log(f">>> {request.method} {request.path}")
    body = request.get_data(as_text=True)
    if body and body.strip():
        for line in format_body(body).split('\n'):
            log(f"    {line}")
    else:
        log("    (无请求体)")


@app.after_request
def after_request_hook(response):
    """记录响应状态和返回体，并添加 CORS 头"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    if request.method != 'OPTIONS':
        log(f"<<< {response.status_code} {request.path}")
        body = response.get_data(as_text=True)
        if body and body.strip():
            for line in format_body(body).split('\n'):
                log(f"    {line}")
        log("-" * 56)
    return response


def get_param(name):
    """从 JSON body 中读取参数（直接 json.loads 解析，不依赖 Content-Type）"""
    raw = request.get_data(as_text=True)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    if isinstance(data, dict):
        return data.get(name)
    return None


@app.route('/', methods=['POST'])
def index():
    return jsonify({
        "success": True,
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
    })


@app.route('/write_memory', methods=['POST'])
def write_memory():
    remark = get_param('备注')
    content = get_param('记忆内容')
    if remark is None or content is None:
        return jsonify({"success": False, "message": "缺少参数：备注 或 记忆内容", "data": None})
    try:
        vector = get_embedding(content)
        vector_bytes = vector.tobytes()
        with db_lock:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                '''INSERT INTO memories (remark, content, vector) VALUES (?, ?, ?)
                   ON CONFLICT(remark) DO UPDATE SET
                       content = excluded.content,
                       vector = excluded.vector''',
                (remark, content, vector_bytes)
            )
            conn.commit()
            conn.close()
        return jsonify({"success": True, "message": f"记忆写入成功：{remark}", "data": None})
    except Exception as e:
        return jsonify({"success": False, "message": f"写入失败：{e}", "data": None})


@app.route('/query_memory', methods=['POST'])
def query_memory():
    message = get_param('消息内容')
    if message is None:
        return jsonify({"success": False, "message": "缺少参数：消息内容", "data": None})
    try:
        query_vector = get_embedding(message)
        with db_lock:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('SELECT remark, content, vector FROM memories')
            rows = c.fetchall()
            conn.close()
        results = []
        for remark, content, vector_bytes in rows:
            vec = array('f')
            vec.frombytes(vector_bytes)
            sim = cosine_similarity(query_vector, vec)
            results.append({
                "备注": remark,
                "记忆内容": content,
                "相似度": round(sim, 4)
            })
        results.sort(key=lambda x: x['相似度'], reverse=True)
        return jsonify({
            "success": True,
            "message": f"查询成功，共 {len(results)} 条记忆",
            "data": results
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"查询失败：{e}", "data": None})


@app.route('/delete_memory', methods=['POST'])
def delete_memory():
    remark = get_param('备注')
    if remark is None:
        return jsonify({"success": False, "message": "缺少参数：备注", "data": None})
    try:
        with db_lock:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('DELETE FROM memories WHERE remark = ?', (remark,))
            deleted = c.rowcount
            conn.commit()
            conn.close()
        if deleted > 0:
            return jsonify({
                "success": True,
                "message": f"删除成功，共删除 {deleted} 条记忆",
                "data": None
            })
        return jsonify({"success": False, "message": f"未找到备注为 {remark} 的记忆", "data": None})
    except Exception as e:
        return jsonify({"success": False, "message": f"删除失败：{e}", "data": None})


@app.route('/list_memory', methods=['POST'])
def list_memory():
    try:
        with db_lock:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('SELECT remark, content FROM memories ORDER BY id')
            rows = c.fetchall()
            conn.close()
        results = [{"备注": r[0], "记忆内容": r[1]} for r in rows]
        return jsonify({
            "success": True,
            "message": f"共 {len(results)} 条记忆",
            "data": results
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"获取列表失败：{e}", "data": None})


@app.route('/rebuild_vectors', methods=['POST'])
def rebuild_vectors():
    try:
        current_model = get_current_model_name()
        log(f"手动重建向量开始，模型: {current_model}")
        with db_lock:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('SELECT id, content FROM memories ORDER BY id')
            rows = c.fetchall()
            total = len(rows)
            if total == 0:
                c.execute('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)', ('model_name', current_model))
                conn.commit()
                conn.close()
                return jsonify({
                    "success": True,
                    "message": "无记忆数据，无需重建",
                    "data": {"重建数量": 0}
                })
            count = 0
            for mid, content in rows:
                vector = get_embedding(content)
                vec_bytes = vector.tobytes()
                c.execute('UPDATE memories SET vector = ? WHERE id = ?', (vec_bytes, mid))
                count += 1
                if count % 10 == 0 or count == total:
                    log(f"重建进度: {count}/{total}")
            c.execute('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)', ('model_name', current_model))
            conn.commit()
            conn.close()
        log(f"手动重建向量完成，共处理 {count}/{total} 条记忆")
        return jsonify({
            "success": True,
            "message": f"向量重建完成，共处理 {count}/{total} 条记忆",
            "data": {"重建数量": count}
        })
    except Exception as e:
        log(f"手动重建向量失败: {e}")
        return jsonify({"success": False, "message": f"重建失败：{e}", "data": None})


if __name__ == '__main__':
    print("=" * 56)
    print("                    AI 记忆数据库服务")
    print("=" * 56)
    print(f"数据目录: {DATA_DIR}")
    print(f"本地模式: {'是' if LOCAL_MODE else '否'}")
    if LOCAL_MODE:
        print(f"本地模型: {LOCAL_MODEL_NAME}")
        print(f"模型缓存: {LOCAL_MODEL_CACHE_DIR}")
    print(f"HTTP端口: {HTTP_PORT}")
    if not LOCAL_MODE:
        print(f"API地址 : {API_URL}")
        print(f"模型名称: {MODEL_NAME}")
    print("-" * 56)
    print("接口列表:")
    print("  写入记忆: POST /write_memory   body: 备注, 记忆内容")
    print("  查询记忆: POST /query_memory   body: 消息内容")
    print("  删除记忆: POST /delete_memory  body: 备注")
    print("  记忆列表: POST /list_memory    body: 无")
    print("  重建向量: POST /rebuild_vectors body: 无")
    print("=" * 56)
    app.run(host='0.0.0.0', port=HTTP_PORT, threaded=True)
