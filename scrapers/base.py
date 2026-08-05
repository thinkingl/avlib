import requests
import time
import os
import random
from abc import ABC, abstractmethod
from config import Config
from logger import logger

class BaseScraper(ABC):
    def __init__(self):
        self.logger = logger
        self.base_url = ''  # 子类需要设置
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': Config.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        self.timeout = Config.REQUEST_TIMEOUT
        self.delay = Config.REQUEST_DELAY
        self.logger.info(f"初始化爬虫: {self.__class__.__name__}")

    @abstractmethod
    def search(self, av_id):
        pass

    @abstractmethod
    def get_source_name(self):
        pass

    def download_image(self, url, save_path):
        """下载图片"""
        self.logger.debug(f"下载图片: {url} -> {save_path}")
        try:
            # 添加Referer头防止403
            headers = {'Referer': self.base_url + '/'} if self.base_url else {}
            response = self.session.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()

            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            with open(save_path, 'wb') as f:
                f.write(response.content)

            self.logger.info(f"图片下载成功: {len(response.content)} bytes")
            return True
        except Exception as e:
            self.logger.error(f"图片下载失败: {e}")
            return False

    def get_image_data(self, url):
        """获取图片二进制数据"""
        self.logger.debug(f"获取图片数据: {url}")
        try:
            # 添加Referer头防止403
            headers = {'Referer': self.base_url + '/'} if self.base_url else {}
            response = self.session.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()

            content_type = response.headers.get('Content-Type', 'image/jpeg')
            if ';' in content_type:
                content_type = content_type.split(';')[0].strip()

            self.logger.info(f"图片数据获取成功: {len(response.content)} bytes, type={content_type}")
            return response.content, content_type
        except Exception as e:
            self.logger.error(f"图片数据获取失败: {e}")
            return None, None

    def _get_delay(self):
        """带抖动的请求延迟，防止固定节奏被识别为爬虫"""
        return self.delay * random.uniform(0.8, 1.2)

    def make_request(self, url, method='GET', max_retries=2, **kwargs):
        """发送请求，失败时指数退避重试（4xx不重试）"""
        self.logger.debug(f"发送请求: {method} {url}")
        for attempt in range(max_retries + 1):
            try:
                time.sleep(self._get_delay())
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                response.raise_for_status()
                self.logger.debug(f"响应状态: {response.status_code}, URL: {response.url}")
                return response
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else None
                if status is not None and 400 <= status < 500:
                    self.logger.warning(f"请求被拒绝: {status} {url}")
                    return None
                self.logger.warning(f"HTTP错误: {e}")
            except requests.RequestException as e:
                self.logger.error(f"请求失败: {e}")

            if attempt < max_retries:
                wait = (2 ** (attempt + 1)) * self.delay
                self.logger.warning(f"{wait:.1f}秒后重试 ({attempt + 1}/{max_retries}): {url}")
                time.sleep(wait)

        self.logger.error(f"请求最终失败: {url}")
        return None

    def clean_text(self, text):
        """清理文本"""
        if text:
            return text.strip().replace('\n', ' ').replace('\r', ' ')
        return ''
