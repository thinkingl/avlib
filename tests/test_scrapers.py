import unittest
import os
import tempfile
from unittest.mock import patch, MagicMock
from scrapers.base import BaseScraper
from scrapers.javbus import JavBusScraper
from scrapers.javdb import JavDBScraper
from scrapers.javlibrary import JavLibraryScraper
from scrapers.dokuwiki import DokuWikiScraper

class TestBaseScraper(unittest.TestCase):
    """爬虫基类测试"""

    def setUp(self):
        """测试前准备"""
        # 创建一个具体的子类用于测试
        class ConcreteScraper(BaseScraper):
            def search(self, av_id):
                return {'av_id': av_id}
            def get_source_name(self):
                return 'test'

        self.scraper = ConcreteScraper()

    def test_init(self):
        """测试初始化"""
        self.assertIsNotNone(self.scraper.session)
        self.assertIsNotNone(self.scraper.timeout)
        self.assertIsNotNone(self.scraper.delay)

    def test_clean_text(self):
        """测试文本清理"""
        # 正常文本
        self.assertEqual(self.scraper.clean_text('  hello  '), 'hello')

        # 带换行的文本
        self.assertEqual(self.scraper.clean_text('hello\nworld'), 'hello world')

        # 带回车的文本
        self.assertEqual(self.scraper.clean_text('hello\rworld'), 'hello world')

        # None
        self.assertEqual(self.scraper.clean_text(None), '')

        # 空字符串
        self.assertEqual(self.scraper.clean_text(''), '')

    @patch('requests.Session.get')
    def test_get_image_data_success(self, mock_get):
        """测试成功获取图片数据"""
        # 模拟响应
        mock_response = MagicMock()
        mock_response.content = b'fake_image_data'
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        data, mime = self.scraper.get_image_data('http://example.com/image.jpg')

        self.assertEqual(data, b'fake_image_data')
        self.assertEqual(mime, 'image/jpeg')

    @patch('requests.Session.get')
    def test_get_image_data_with_content_type_params(self, mock_get):
        """测试获取图片数据时Content-Type包含参数"""
        mock_response = MagicMock()
        mock_response.content = b'fake_image_data'
        mock_response.headers = {'Content-Type': 'image/jpeg; charset=utf-8'}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        data, mime = self.scraper.get_image_data('http://example.com/image.jpg')

        self.assertEqual(mime, 'image/jpeg')

    @patch('requests.Session.get')
    def test_get_image_data_failure(self, mock_get):
        """测试获取图片数据失败"""
        mock_get.side_effect = Exception('Network error')

        data, mime = self.scraper.get_image_data('http://example.com/image.jpg')

        self.assertIsNone(data)
        self.assertIsNone(mime)

    @patch('requests.Session.get')
    def test_download_image_success(self, mock_get):
        """测试成功下载图片"""
        mock_response = MagicMock()
        mock_response.content = b'fake_image_data'
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # 使用临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as f:
            save_path = f.name

        try:
            result = self.scraper.download_image('http://example.com/image.jpg', save_path)
            self.assertTrue(result)

            # 验证文件已写入
            with open(save_path, 'rb') as f:
                self.assertEqual(f.read(), b'fake_image_data')
        finally:
            if os.path.exists(save_path):
                os.remove(save_path)

    @patch('requests.Session.get')
    def test_download_image_failure(self, mock_get):
        """测试下载图片失败"""
        mock_get.side_effect = Exception('Network error')

        result = self.scraper.download_image('http://example.com/image.jpg', '/tmp/test.jpg')
        self.assertFalse(result)

    @patch('requests.Session.request')
    def test_make_request_success(self, mock_request):
        """测试成功发送请求"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        response = self.scraper.make_request('http://example.com')

        self.assertIsNotNone(response)
        mock_request.assert_called_once()

    @patch('requests.Session.request')
    def test_make_request_failure(self, mock_request):
        """测试发送请求失败"""
        import requests
        mock_request.side_effect = requests.RequestException('Request failed')

        response = self.scraper.make_request('http://example.com')

        self.assertIsNone(response)


class TestJavBusScraper(unittest.TestCase):
    """JavBus爬虫测试"""

    def setUp(self):
        self.scraper = JavBusScraper()

    def test_get_source_name(self):
        """测试获取数据源名称"""
        self.assertEqual(self.scraper.get_source_name(), 'javbus')

    @patch.object(JavBusScraper, 'make_request')
    def test_search_not_found(self, mock_request):
        """测试搜索未找到结果"""
        mock_request.return_value = None

        result = self.scraper.search('NOT-EXIST')
        self.assertIsNone(result)

    @patch.object(JavBusScraper, 'make_request')
    def test_search_redirected_to_verify_page(self, mock_request):
        """测试被重定向到年龄验证页时返回None"""
        mock_response = MagicMock()
        mock_response.text = '<html><title>Age Verification</title></html>'
        mock_response.url = 'https://www.javbus.com/doc/driver-verify?referer=TEST-001'
        mock_request.return_value = mock_response

        result = self.scraper.search('TEST-001')
        self.assertIsNone(result)

    @patch.object(JavBusScraper, 'make_request')
    def test_search_success(self, mock_request):
        """测试搜索成功"""
        # 模拟HTML响应
        html_content = '''
        <html>
        <head><title>TEST-001</title></head>
        <body>
            <h3>TEST-001 测试标题</h3>
            <a class="bigImage" href="/images/cover.jpg">
                <img src="/images/thumb.jpg">
            </a>
            <div class="col-md-3 info">
                <p><span class="header">識別碼:</span> TEST-001</p>
                <p><span class="header">發行日期:</span> 2024-01-01</p>
                <p><span class="header">長度:</span> 120分鐘</p>
                <p><span class="header">導演:</span> <a>測試導演</a></p>
                <p><span class="header">製作商:</span> <a>測試製作商</a></p>
                <p><span class="header">發行商:</span> <a>測試發行商</a></p>
                <p><span class="header">系列:</span> <a>測試系列</a></p>
            </div>
            <div id="star-list">
                <a>演員1</a>
                <a>演員2</a>
            </div>
            <span class="genre">
                <a>類型1</a>
                <a>類型2</a>
            </span>
        </body>
        </html>
        '''

        mock_response = MagicMock()
        mock_response.text = html_content
        mock_response.url = 'http://javbus.com/TEST-001'
        mock_request.return_value = mock_response

        result = self.scraper.search('TEST-001')

        self.assertIsNotNone(result)
        self.assertEqual(result['av_id'], 'TEST-001')
        self.assertIn('测试标题', result['title'])
        self.assertEqual(result['release_date'], '2024-01-01')
        self.assertEqual(result['duration'], '120分鐘')


class TestJavDBScraper(unittest.TestCase):
    """JavDB爬虫测试"""

    def setUp(self):
        self.scraper = JavDBScraper()

    def test_get_source_name(self):
        """测试获取数据源名称"""
        self.assertEqual(self.scraper.get_source_name(), 'javdb')

    @patch.object(JavDBScraper, 'make_request')
    def test_search_not_found(self, mock_request):
        """测试搜索未找到结果"""
        mock_request.return_value = None

        result = self.scraper.search('NOT-EXIST')
        self.assertIsNone(result)


class TestJavLibraryScraper(unittest.TestCase):
    """JAV Library爬虫测试"""

    def setUp(self):
        self.scraper = JavLibraryScraper()

    def test_get_source_name(self):
        """测试获取数据源名称"""
        self.assertEqual(self.scraper.get_source_name(), 'javlibrary')

    @patch.object(JavLibraryScraper, 'make_request')
    def test_search_not_found(self, mock_request):
        """测试搜索未找到结果"""
        mock_request.return_value = None

        result = self.scraper.search('NOT-EXIST')
        self.assertIsNone(result)


class TestDokuWikiScraper(unittest.TestCase):
    """DokuWiki搜索源测试"""

    def setUp(self):
        self.scraper = DokuWikiScraper()
        self.scraper.base_url = 'http://192.168.84.100/dokuwiki'

    def test_get_source_name(self):
        self.assertEqual(self.scraper.get_source_name(), 'dokuwiki')

    @patch.object(DokuWikiScraper, 'make_request')
    def test_search_success(self, mock_request):
        """测试直接命中页面并解析字段"""
        raw = '''====== IPX-782 测试标题 ======

识别码:\tIPX-782  \\\\
发行日期:\t2021-12-14  \\\\
长度:\t120 分鍾  \\\\
导演:\t赤井彗星  \\\\
制作商:\tIDEA POCKET  \\\\
发行商:\tテスト発行  \\\\
系列:\t测试系列  \\\\
网站评分:\t4.5  \\\\
类别:\t單體作品 女上位  \\\\
演员:\t明里つむぎ  \\\\
评论:\t很好看  \\\\

{{:av:2021-12-14-ipx-782.jpg|}}
'''
        mock_resp = MagicMock()
        mock_resp.text = raw
        mock_request.return_value = mock_resp

        result = self.scraper.search('IPX-782')

        self.assertIsNotNone(result)
        self.assertEqual(result['av_id'], 'IPX-782')
        self.assertEqual(result['title'], 'IPX-782 测试标题')
        self.assertEqual(result['release_date'], '2021-12-14')
        self.assertEqual(result['duration'], '120 分鍾')
        self.assertEqual(result['studio'], 'IDEA POCKET')
        self.assertEqual(result['genres'], ['單體作品', '女上位'])
        self.assertEqual(result['actresses'], ['明里つむぎ'])
        self.assertEqual(result['comment'], '很好看')
        self.assertIn('fetch.php?media=av:2021-12-14-ipx-782.jpg', result['cover_url'])

    @patch.object(DokuWikiScraper, 'make_request')
    def test_search_fallback_by_search(self, mock_request):
        """测试直接页面不存在时通过搜索查找"""
        # 第一次：直接页面不存在
        not_found = MagicMock()
        not_found.text = ''
        # 第二次：搜索结果页
        search_resp = MagicMock()
        search_resp.text = '<a href="/dokuwiki/doku.php?id=av%3A2019-08-30-jvr100138" class="wikilink1">JVR100138</a>'
        # 第三次：页面原始内容
        raw_resp = MagicMock()
        raw_resp.text = '''2019-08-30-JVR100138

{{:av:2019-08-30-jvr100138.jpeg|}}
'''
        mock_request.side_effect = [not_found, search_resp, raw_resp]

        result = self.scraper.search('JVR100138')

        self.assertIsNotNone(result)
        self.assertEqual(result['av_id'], 'JVR100138')
        self.assertEqual(result['title'], '2019-08-30-JVR100138')
        self.assertIn('2019-08-30-jvr100138.jpeg', result['cover_url'])

    @patch.object(DokuWikiScraper, 'make_request')
    def test_search_not_found(self, mock_request):
        """测试页面不存在且搜索无结果"""
        mock_request.return_value = None

        result = self.scraper.search('NOT-EXIST')
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
