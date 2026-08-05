import os
import tempfile

class TestConfig:
    """测试配置"""
    TESTING = True
    DEBUG = False

    # 使用临时数据库
    DATABASE_PATH = tempfile.mktemp(suffix='.db')

    # 图片存储
    IMAGES_DIR = tempfile.mkdtemp()

    # DokuWiki配置（测试用）
    DOKUWIKI_URL = 'http://localhost/dokuwiki'
    DOKUWIKI_USERNAME = 'testuser'
    DOKUWIKI_PASSWORD = 'testpass'
    DOKUWIKI_API_TOKEN = ''

    # 爬虫配置
    SCRAPERS = ['javbus', 'javdb', 'javlibrary']
    REQUEST_TIMEOUT = 5
    REQUEST_DELAY = 0  # 测试时不需要延迟

    SECRET_KEY = 'test-secret-key'
