import os
import re
import json
import subprocess
from flask import Flask, request, jsonify, render_template, Response
from config import Config
from database import Database
from scrapers import JavBusScraper, JavDBScraper, JavLibraryScraper
from dokuwiki import DokuWikiClient, get_cover_filename
from logger import logger

app = Flask(__name__)
app.config.from_object(Config)

logger.info("=" * 50)
logger.info("AVLib 应用启动")

# 运行时设置文件（保存前端修改的DokuWiki配置）
SETTINGS_PATH = os.environ.get('AVLIB_SETTINGS_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json'))
SETTINGS_KEYS = ['dokuwiki_url', 'dokuwiki_username', 'dokuwiki_password', 'dokuwiki_api_token']

def _load_settings():
    """读取运行时设置"""
    settings = {}
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except Exception as e:
            logger.error(f"读取配置文件失败: {e}")
    return settings

def _apply_settings(settings):
    """将设置应用到Config"""
    for key in SETTINGS_KEYS:
        if settings.get(key):
            setattr(Config, key.upper(), settings[key])

def _save_settings(updates):
    """保存运行时设置"""
    settings = _load_settings()
    settings.update(updates)
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    os.chmod(SETTINGS_PATH, 0o600)  # 含密码，仅所有者可读写

# 加载持久化的设置
_apply_settings(_load_settings())

def get_git_version():
    """获取当前代码的git提交版本信息"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        commit = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=base_dir, stderr=subprocess.DEVNULL
        ).decode().strip()
        commit_time = subprocess.check_output(
            ['git', 'log', '-1', '--format=%cI'],
            cwd=base_dir, stderr=subprocess.DEVNULL
        ).decode().strip()
        return {'commit': commit, 'commit_time': commit_time}
    except Exception:
        return {'commit': 'unknown', 'commit_time': ''}

# 初始化数据库
db = Database()
logger.info("数据库初始化完成")

# 初始化爬虫
scrapers = {
    'javbus': JavBusScraper(),
    'javdb': JavDBScraper(),
    'javlibrary': JavLibraryScraper()
}
logger.info(f"爬虫初始化完成: {list(scrapers.keys())}")

# 初始化DokuWiki客户端
dokuwiki_client = DokuWikiClient()
logger.info("DokuWiki客户端初始化完成")

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def search_av():
    """搜索AV信息"""
    data = request.json
    av_ids = data.get('av_ids', [])
    sources = data.get('sources') or list(Config.SCRAPERS)

    logger.info(f"搜索请求: av_ids={av_ids}, sources={sources}")

    if not av_ids:
        logger.warning("搜索请求缺少番号")
        return jsonify({'error': '请提供番号'}), 400

    # 展开番号列表：支持空格、逗号、换行混合分隔（如 "hnvr-140 kawd-992"）
    expanded_ids = []
    for av_id in av_ids:
        for part in re.split(r'[\s,]+', str(av_id)):
            part = part.strip().upper()
            if part:
                expanded_ids.append(part)

    if not expanded_ids:
        logger.warning("搜索请求番号解析为空")
        return jsonify({'error': '请提供有效的番号'}), 400

    av_ids = expanded_ids
    logger.info(f"解析后番号: {av_ids}")

    results = []

    for av_id in av_ids:
        if not av_id:
            continue

        logger.info(f"搜索番号: {av_id}")

        # 先从数据库查找
        existing = db.get_av_info(av_id)
        if existing:
            logger.info(f"从数据库找到: {av_id}")
            # 排除二进制数据
            response_data = {k: v for k, v in existing.items() if k != 'cover_data'}
            results.append({
                'av_id': av_id,
                'data': response_data,
                'source': 'database',
                'status': 'found',
                'from_database': True
            })
            continue

        # 从各网站搜索
        found = False
        for source_name in sources:
            if source_name not in scrapers:
                logger.warning(f"未知数据源: {source_name}")
                continue

            logger.info(f"从 {source_name} 搜索: {av_id}")
            scraper = scrapers[source_name]
            try:
                av_info = scraper.search(av_id)

                if av_info:
                    logger.info(f"从 {source_name} 找到: {av_id}")

                    # 获取封面图片数据
                    cover_url = av_info.get('cover_url')
                    if cover_url:
                        logger.info(f"获取封面图片: {cover_url}")
                        cover_data, cover_mime = scraper.get_image_data(cover_url)
                        if cover_data:
                            av_info['cover_data'] = cover_data
                            av_info['cover_mime'] = cover_mime or 'image/jpeg'
                            logger.info(f"封面图片获取成功: {len(cover_data)} bytes")
                        else:
                            av_info['cover_data'] = None
                            av_info['cover_mime'] = 'image/jpeg'
                            logger.warning(f"封面图片获取失败")

                    # 保存到数据库
                    db.insert_av_info(av_info)
                    db.add_search_history(av_id, source_name, True)
                    logger.info(f"数据已保存到数据库: {av_id}")

                    # 创建返回数据（排除二进制数据）
                    response_data = {k: v for k, v in av_info.items() if k != 'cover_data'}

                    results.append({
                        'av_id': av_id,
                        'data': response_data,
                        'source': source_name,
                        'status': 'found',
                        'from_database': False
                    })

                    found = True
                    break
                else:
                    logger.warning(f"从 {source_name} 未找到: {av_id}")

            except Exception as e:
                logger.error(f"从 {source_name} 搜索 {av_id} 失败: {e}", exc_info=True)
                db.add_search_history(av_id, source_name, False)
                continue

        if not found:
            logger.warning(f"所有数据源均未找到: {av_id}")
            results.append({
                'av_id': av_id,
                'data': None,
                'source': None,
                'status': 'not_found'
            })

    logger.info(f"搜索完成: {len(results)} 个结果")
    return jsonify({
        'success': True,
        'results': results
    })

@app.route('/api/av', methods=['GET'])
def get_all_av():
    """获取所有AV信息"""
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)

    logger.info(f"获取AV列表: limit={limit}, offset={offset}")
    av_list = db.get_all_av_info(limit, offset)
    total = db.get_av_count()

    # 排除二进制数据
    filtered_list = [{k: v for k, v in item.items() if k != 'cover_data'} for item in av_list]

    return jsonify({
        'success': True,
        'data': filtered_list,
        'total': total,
        'limit': limit,
        'offset': offset
    })

@app.route('/api/av/<av_id>', methods=['GET'])
def get_av(av_id):
    """获取单个AV信息"""
    logger.info(f"获取AV信息: {av_id}")
    av_info = db.get_av_info(av_id)

    if av_info:
        # 排除二进制数据
        response_data = {k: v for k, v in av_info.items() if k != 'cover_data'}
        return jsonify({
            'success': True,
            'data': response_data
        })
    else:
        logger.warning(f"未找到: {av_id}")
        return jsonify({
            'success': False,
            'error': '未找到该番号'
        }), 404

@app.route('/api/av/<av_id>', methods=['DELETE'])
def delete_av(av_id):
    """删除AV信息"""
    logger.info(f"删除AV: {av_id}")
    av_info = db.get_av_info(av_id)

    if not av_info:
        logger.warning(f"删除失败，未找到: {av_id}")
        return jsonify({
            'success': False,
            'error': '未找到该番号'
        }), 404

    # 从数据库删除（图片数据也会一起删除）
    db.delete_av_info(av_id)
    logger.info(f"已删除: {av_id}")

    return jsonify({
        'success': True,
        'message': f'已删除 {av_id}'
    })

@app.route('/api/av/<av_id>/comment', methods=['PUT'])
def update_av_comment(av_id):
    """添加/修改番号评论"""
    av_id = av_id.upper()
    data = request.json or {}
    comment = (data.get('comment') or '').strip()

    logger.info(f"更新评论: {av_id}")

    av_info = db.get_av_info(av_id)
    if not av_info:
        logger.warning(f"更新评论失败，未找到: {av_id}")
        return jsonify({'success': False, 'error': '未找到该番号'}), 404

    db.update_av_comment(av_id, comment)
    logger.info(f"评论已保存: {av_id}")

    return jsonify({
        'success': True,
        'message': '评论已保存'
    })

@app.route('/api/submit-to-wiki', methods=['POST'])
def submit_to_wiki():
    """提交到DokuWiki"""
    data = request.json
    av_ids = data.get('av_ids', [])

    logger.info(f"提交到Wiki: {av_ids}")

    if not av_ids:
        logger.warning("提交请求缺少番号")
        return jsonify({'error': '请提供要提交的番号'}), 400

    results = []

    for av_id in av_ids:
        av_id = av_id.strip().upper()
        logger.info(f"提交: {av_id}")
        av_info = db.get_av_info(av_id)

        if not av_info:
            logger.warning(f"提交失败，未找到: {av_id}")
            results.append({
                'av_id': av_id,
                'status': 'error',
                'message': '未找到该番号信息'
            })
            continue

        try:
            # 解析JSON字段
            if isinstance(av_info.get('actresses'), str):
                av_info['actresses'] = json.loads(av_info['actresses'])
            if isinstance(av_info.get('genres'), str):
                av_info['genres'] = json.loads(av_info['genres'])

            success, message = dokuwiki_client.submit_av_info(av_info)

            # 记录提交状态
            db.add_dokuwiki_submission(av_id, f"av:{av_id}", 'success' if success else 'failed')

            results.append({
                'av_id': av_id,
                'status': 'success' if success else 'error',
                'message': message
            })

            if success:
                logger.info(f"提交成功: {av_id}")
            else:
                logger.error(f"提交失败: {av_id}, {message}")

        except Exception as e:
            logger.error(f"提交异常: {av_id}, {e}", exc_info=True)
            results.append({
                'av_id': av_id,
                'status': 'error',
                'message': str(e)
            })

    logger.info(f"提交完成: {len(results)} 个结果")
    return jsonify({
        'success': True,
        'results': results
    })

@app.route('/api/test-wiki-connection', methods=['GET'])
def test_wiki_connection():
    """测试DokuWiki连接"""
    logger.info("测试DokuWiki连接")
    success = dokuwiki_client.test_connection()

    if success:
        logger.info("DokuWiki连接成功")
    else:
        logger.error("DokuWiki连接失败")

    return jsonify({
        'success': success,
        'message': '连接成功' if success else '连接失败'
    })

@app.route('/api/cover/<av_id>')
def serve_cover(av_id):
    """提供封面图片API（支持?download=1下载）"""
    av_id = av_id.upper()
    av_info = db.get_av_info(av_id)

    if not av_info or not av_info.get('cover_data'):
        return jsonify({'success': False, 'error': '未找到封面图片'}), 404

    cover_data = av_info['cover_data']
    cover_mime = av_info.get('cover_mime') or 'image/jpeg'

    if request.args.get('download'):
        ext = 'png' if cover_mime == 'image/png' else 'jpg'
        filename = get_cover_filename(av_info, ext)
        headers = {'Content-Disposition': f'attachment; filename={filename}'}
        return Response(cover_data, mimetype=cover_mime, headers=headers)

    return Response(cover_data, mimetype=cover_mime)

@app.route('/api/wiki-preview/<av_id>', methods=['GET'])
def wiki_preview(av_id):
    """生成DokuWiki页面内容预览"""
    av_info = db.get_av_info(av_id.upper())

    if not av_info:
        logger.warning(f"Wiki预览失败，未找到: {av_id}")
        return jsonify({'success': False, 'error': '未找到该番号'}), 404

    # 解析JSON字段
    if isinstance(av_info.get('actresses'), str):
        av_info['actresses'] = json.loads(av_info['actresses'])
    if isinstance(av_info.get('genres'), str):
        av_info['genres'] = json.loads(av_info['genres'])

    content = dokuwiki_client.format_av_page(av_info)
    return jsonify({
        'success': True,
        'content': content,
        'page_id': f"av:{av_info['av_id']}"
    })

@app.route('/api/version', methods=['GET'])
def get_version():
    """获取git版本信息"""
    return jsonify({'success': True, **get_git_version()})

@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置信息"""
    return jsonify({
        'dokuwiki_url': Config.DOKUWIKI_URL,
        'dokuwiki_username': Config.DOKUWIKI_USERNAME,
        'images_dir': Config.IMAGES_DIR
    })

@app.route('/api/config', methods=['POST'])
def update_config():
    """更新配置（持久化到settings.json）"""
    data = request.json
    logger.info(f"更新配置: {list(data.keys())}")

    updates = {}

    if 'dokuwiki_url' in data:
        updates['dokuwiki_url'] = data['dokuwiki_url']

    if 'dokuwiki_username' in data:
        updates['dokuwiki_username'] = data['dokuwiki_username']

    if 'dokuwiki_password' in data:
        updates['dokuwiki_password'] = data['dokuwiki_password']

    if 'dokuwiki_api_token' in data:
        updates['dokuwiki_api_token'] = data['dokuwiki_api_token']

    if updates:
        # 应用到Config并同步到DokuWiki客户端
        _apply_settings(updates)
        for key, value in updates.items():
            setattr(dokuwiki_client, key.replace('dokuwiki_', ''), value)
        _save_settings(updates)

    return jsonify({
        'success': True,
        'message': '配置已更新'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    logger.info(f"启动服务器: 0.0.0.0:{port}")
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=port)
