import os

class Config:
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'avlib-secret-key-2024')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    # 数据库配置
    DATABASE_PATH = os.environ.get('DATABASE_PATH', 'avlib.db')

    # 图片存储配置
    IMAGES_DIR = os.environ.get('IMAGES_DIR', 'images')
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB

    # DokuWiki配置
    DOKUWIKI_URL = os.environ.get('DOKUWIKI_URL', 'http://localhost/dokuwiki')
    DOKUWIKI_USERNAME = os.environ.get('DOKUWIKI_USERNAME', 'admin')
    DOKUWIKI_PASSWORD = os.environ.get('DOKUWIKI_PASSWORD', '')
    DOKUWIKI_API_TOKEN = os.environ.get('DOKUWIKI_API_TOKEN', '')

    # 爬虫配置
    SCRAPERS = ['dokuwiki', 'javdb', 'javbus']  # dokuwiki为局域网已有数据源，最可靠
    REQUEST_TIMEOUT = 30
    REQUEST_DELAY = 1  # 请求间隔（秒）

    # 用户代理
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
