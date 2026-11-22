import unittest
import json
import base64
import tempfile
import os
from unittest.mock import patch, MagicMock
from app import app, db

class TestFlaskApp(unittest.TestCase):
    """Flask应用测试"""

    def setUp(self):
        """测试前准备"""
        # 配置测试应用
        app.config['TESTING'] = True
        app.config['DEBUG'] = False

        # 使用临时数据库
        self.db_path = tempfile.mktemp(suffix='.db')
        from database import Database
        self.test_db = Database(db_path=self.db_path)

        # 替换全局数据库实例
        import app as app_module
        self.original_db = app_module.db
        app_module.db = self.test_db

        # 创建测试客户端
        self.client = app.test_client()

    def tearDown(self):
        """测试后清理"""
        # 恢复原始数据库实例
        import app as app_module
        app_module.db = self.original_db

        # 清理临时数据库
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_index(self):
        """测试主页"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_search_av_empty_ids(self):
        """测试搜索空番号"""
        response = self.client.post('/api/search',
                                    json={'av_ids': []},
                                    content_type='application/json')

        data = json.loads(response.data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', data)

    def test_search_av_no_ids(self):
        """测试不提供番号"""
        response = self.client.post('/api/search',
                                    json={},
                                    content_type='application/json')

        data = json.loads(response.data)
        self.assertEqual(response.status_code, 400)

    @patch('app.scrapers')
    def test_search_av_from_database(self, mock_scrapers):
        """测试从数据库搜索"""
        # 先插入数据
        self.test_db.insert_av_info({
            'av_id': 'DB-TEST-001',
            'title': '数据库中的标题',
            'source': 'database'
        })

        # 搜索
        response = self.client.post('/api/search',
                                    json={'av_ids': ['DB-TEST-001']},
                                    content_type='application/json')

        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['source'], 'database')
        self.assertTrue(data['results'][0]['from_database'])

    def test_search_av_from_scraper(self):
        """测试从爬虫搜索"""
        # 模拟爬虫
        mock_scraper = MagicMock()
        mock_scraper.search.return_value = {
            'av_id': 'SCRAPER-001',
            'title': '爬虫获取的标题',
            'cover_url': 'http://example.com/cover.jpg',
            'source': 'javbus'
        }
        mock_scraper.get_image_data.return_value = (b'fake_image', 'image/jpeg')

        # 临时替换scrapers
        import app as app_module
        original_scrapers = app_module.scrapers
        app_module.scrapers = {'javbus': mock_scraper}

        try:
            # 搜索
            response = self.client.post('/api/search',
                                        json={'av_ids': ['SCRAPER-001'], 'sources': ['javbus']},
                                        content_type='application/json')

            data = json.loads(response.data)
            self.assertTrue(data['success'])
            self.assertEqual(len(data['results']), 1)
            self.assertEqual(data['results'][0]['status'], 'found')
        finally:
            # 恢复原始scrapers
            app_module.scrapers = original_scrapers

    def test_get_all_av(self):
        """测试获取所有AV信息"""
        # 插入测试数据
        for i in range(3):
            self.test_db.insert_av_info({
                'av_id': f'LIST-{i:03d}',
                'title': f'标题{i}',
                'source': 'test'
            })

        response = self.client.get('/api/av')
        data = json.loads(response.data)

        self.assertTrue(data['success'])
        self.assertEqual(len(data['data']), 3)
        self.assertEqual(data['total'], 3)

    def test_get_av_found(self):
        """测试获取单个AV信息"""
        # 插入测试数据
        self.test_db.insert_av_info({
            'av_id': 'SINGLE-001',
            'title': '单个测试',
            'source': 'test'
        })

        response = self.client.get('/api/av/SINGLE-001')
        data = json.loads(response.data)

        self.assertTrue(data['success'])
        self.assertEqual(data['data']['av_id'], 'SINGLE-001')

    def test_get_av_not_found(self):
        """测试获取不存在的AV信息"""
        response = self.client.get('/api/av/NOT-EXIST')
        data = json.loads(response.data)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(data['success'])

    def test_delete_av(self):
        """测试删除AV信息"""
        # 插入测试数据
        self.test_db.insert_av_info({
            'av_id': 'DELETE-001',
            'title': '待删除',
            'source': 'test'
        })

        # 确认存在
        self.assertIsNotNone(self.test_db.get_av_info('DELETE-001'))

        # 删除
        response = self.client.delete('/api/av/DELETE-001')
        data = json.loads(response.data)

        self.assertTrue(data['success'])

        # 确认已删除
        self.assertIsNone(self.test_db.get_av_info('DELETE-001'))

    def test_delete_av_not_found(self):
        """测试删除不存在的AV信息"""
        response = self.client.delete('/api/av/NOT-EXIST')
        data = json.loads(response.data)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(data['success'])

    def test_serve_cover_from_database(self):
        """测试从数据库获取封面图片"""
        # 插入包含图片数据的测试数据
        image_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        self.test_db.insert_av_info({
            'av_id': 'COVER-001',
            'title': '封面测试',
            'cover_data': image_data,
            'cover_mime': 'image/png',
            'source': 'test'
        })

        response = self.client.get('/api/cover/COVER-001')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'image/png')
        self.assertEqual(response.data, image_data)

    def test_serve_cover_not_found(self):
        """测试获取不存在的封面图片"""
        response = self.client.get('/api/cover/NOT-EXIST')
        self.assertEqual(response.status_code, 404)

    def test_submit_to_wiki_empty_ids(self):
        """测试提交空番号到Wiki"""
        response = self.client.post('/api/submit-to-wiki',
                                    json={'av_ids': []},
                                    content_type='application/json')

        data = json.loads(response.data)
        self.assertEqual(response.status_code, 400)

    @patch('app.dokuwiki_client')
    def test_submit_to_wiki_success(self, mock_wiki_client):
        """测试成功提交到Wiki"""
        # 插入测试数据
        self.test_db.insert_av_info({
            'av_id': 'WIKI-001',
            'title': 'Wiki测试',
            'actresses': '["演员1"]',
            'genres': '["类型1"]',
            'source': 'test'
        })

        # 模拟DokuWiki客户端
        mock_wiki_client.submit_av_info.return_value = (True, 'Success')

        response = self.client.post('/api/submit-to-wiki',
                                    json={'av_ids': ['WIKI-001']},
                                    content_type='application/json')

        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['results'][0]['status'], 'success')

    @patch('app.dokuwiki_client')
    def test_submit_to_wiki_not_found(self, mock_wiki_client):
        """测试提交不存在的番号到Wiki"""
        response = self.client.post('/api/submit-to-wiki',
                                    json={'av_ids': ['NOT-EXIST']},
                                    content_type='application/json')

        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['results'][0]['status'], 'error')

    @patch('app.dokuwiki_client')
    def test_test_wiki_connection_success(self, mock_wiki_client):
        """测试Wiki连接成功"""
        mock_wiki_client.test_connection.return_value = True

        response = self.client.get('/api/test-wiki-connection')
        data = json.loads(response.data)

        self.assertTrue(data['success'])

    @patch('app.dokuwiki_client')
    def test_test_wiki_connection_failure(self, mock_wiki_client):
        """测试Wiki连接失败"""
        mock_wiki_client.test_connection.return_value = False

        response = self.client.get('/api/test-wiki-connection')
        data = json.loads(response.data)

        self.assertFalse(data['success'])

    def test_get_version(self):
        """测试获取版本信息"""
        response = self.client.get('/api/version')
        data = json.loads(response.data)

        self.assertTrue(data['success'])
        self.assertIn('commit', data)
        self.assertIn('commit_time', data)

    def test_get_config(self):
        """测试获取配置"""
        response = self.client.get('/api/config')
        data = json.loads(response.data)

        self.assertIn('dokuwiki_url', data)
        self.assertIn('dokuwiki_username', data)

    def test_update_config(self):
        """测试更新配置"""
        response = self.client.post('/api/config',
                                    json={
                                        'dokuwiki_url': 'http://new-wiki.com',
                                        'dokuwiki_username': 'newuser'
                                    },
                                    content_type='application/json')

        data = json.loads(response.data)
        self.assertTrue(data['success'])

    def test_wiki_preview(self):
        """测试获取Wiki内容预览"""
        self.test_db.insert_av_info({
            'av_id': 'PREVIEW-001',
            'title': '预览测试',
            'actresses': '["演员1"]',
            'genres': '["类型1"]',
            'source': 'test'
        })

        response = self.client.get('/api/wiki-preview/PREVIEW-001')
        data = json.loads(response.data)

        self.assertTrue(data['success'])
        self.assertIn('PREVIEW-001', data['content'])
        self.assertIn('演员1', data['content'])

    def test_wiki_preview_not_found(self):
        """测试获取不存在的Wiki内容预览"""
        response = self.client.get('/api/wiki-preview/NOT-EXIST')
        data = json.loads(response.data)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(data['success'])

    def test_serve_cover_download(self):
        """测试下载封面"""
        image_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        self.test_db.insert_av_info({
            'av_id': 'DL-COVER-001',
            'title': '下载测试',
            'release_date': '2024-12-11',
            'cover_data': image_data,
            'cover_mime': 'image/png',
            'source': 'test'
        })

        response = self.client.get('/api/cover/DL-COVER-001?download=1')

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response.headers.get('Content-Disposition', ''))
        self.assertIn('2024-12-11-dl-cover-001.png', response.headers.get('Content-Disposition', ''))
        self.assertEqual(response.data, image_data)

    def test_update_comment(self):
        """测试添加/修改评论"""
        self.test_db.insert_av_info({
            'av_id': 'CMT-001',
            'title': '评论测试',
            'source': 'test'
        })

        # 添加评论
        response = self.client.put('/api/av/CMT-001/comment',
                                   json={'comment': '第一条评论'},
                                   content_type='application/json')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(self.test_db.get_av_info('CMT-001')['comment'], '第一条评论')

        # 修改评论
        response = self.client.put('/api/av/CMT-001/comment',
                                   json={'comment': '修改后'},
                                   content_type='application/json')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(self.test_db.get_av_info('CMT-001')['comment'], '修改后')

    def test_update_comment_not_found(self):
        """测试更新不存在番号的评论"""
        response = self.client.put('/api/av/NOT-EXIST/comment',
                                   json={'comment': '测试'},
                                   content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(data['success'])

    def test_update_comment_cleared(self):
        """测试清空评论"""
        self.test_db.insert_av_info({
            'av_id': 'CMT-002',
            'title': '清空评论',
            'comment': '旧评论',
            'source': 'test'
        })

        response = self.client.put('/api/av/CMT-002/comment',
                                   json={'comment': ' '},
                                   content_type='application/json')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(self.test_db.get_av_info('CMT-002')['comment'], '')

    def test_import_basic(self):
        """测试基础导入"""
        response = self.client.post('/api/import',
                                    json={
                                        'av_id': 'imp-001',
                                        'title': '导入测试',
                                        'release_date': '2024-12-11',
                                        'actresses': ['演员A'],
                                        'genres': ['类型A'],
                                        'source': 'javlibrary'
                                    },
                                    content_type='application/json')

        data = json.loads(response.data)
        self.assertTrue(data['success'])
        saved = self.test_db.get_av_info('IMP-001')
        self.assertIsNotNone(saved)
        self.assertEqual(saved['title'], '导入测试')
        self.assertEqual(saved['release_date'], '2024-12-11')

    def test_import_with_base64_cover(self):
        """测试导入带base64封面图片"""
        image_data = b'\xff\xd8\xff\xe0fakejpeg'
        cover_b64 = 'data:image/jpeg;base64,' + base64.b64encode(image_data).decode()

        response = self.client.post('/api/import',
                                    json={
                                        'av_id': 'IMP-002',
                                        'title': '带图导入',
                                        'cover_base64': cover_b64
                                    },
                                    content_type='application/json')

        data = json.loads(response.data)
        self.assertTrue(data['success'])
        saved_cover, saved_mime = self.test_db.get_cover_data('IMP-002')
        self.assertEqual(saved_cover, image_data)
        self.assertEqual(saved_mime, 'image/jpeg')

    @patch('app.requests.get')
    def test_import_with_cover_url(self, mock_get):
        """测试导入从URL下载封面"""
        mock_resp = MagicMock()
        mock_resp.content = b'\xff\xd8\xff\xe0image'
        mock_resp.headers = {'Content-Type': 'image/jpeg'}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        response = self.client.post('/api/import',
                                    json={
                                        'av_id': 'IMP-003',
                                        'title': 'URL封面',
                                        'cover_url': 'https://www.javlibrary.com/covers/imp-003.jpg'
                                    },
                                    content_type='application/json')

        data = json.loads(response.data)
        self.assertTrue(data['success'])
        saved_cover, _ = self.test_db.get_cover_data('IMP-003')
        self.assertEqual(saved_cover, b'\xff\xd8\xff\xe0image')
        # 验证带Referer
        call_headers = mock_get.call_args.kwargs.get('headers', {})
        self.assertEqual(call_headers.get('Referer'), 'https://www.javlibrary.com/')

    def test_import_missing_av_id(self):
        """测试导入缺少番号"""
        response = self.client.post('/api/import',
                                    json={'title': '无番号'},
                                    content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(data['success'])

    def test_import_duplicate(self):
        """测试导入已存在的番号"""
        self.test_db.insert_av_info({
            'av_id': 'IMP-DUP',
            'title': '已存在',
            'source': 'test'
        })

        response = self.client.post('/api/import',
                                    json={'av_id': 'IMP-DUP', 'title': '重复'},
                                    content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 409)
        self.assertFalse(data['success'])

    def test_search_av_multiple_ids(self):
        """测试批量搜索多个番号"""
        # 插入测试数据
        self.test_db.insert_av_info({
            'av_id': 'MULTI-001',
            'title': '批量测试1',
            'source': 'test'
        })
        self.test_db.insert_av_info({
            'av_id': 'MULTI-002',
            'title': '批量测试2',
            'source': 'test'
        })

        response = self.client.post('/api/search',
                                    json={'av_ids': ['MULTI-001', 'MULTI-002']},
                                    content_type='application/json')

        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['results']), 2)

    def test_search_av_space_separated(self):
        """测试空格分隔的多个番号"""
        self.test_db.insert_av_info({
            'av_id': 'HNVR-140',
            'title': '测试1',
            'source': 'test'
        })
        self.test_db.insert_av_info({
            'av_id': 'KAWD-992',
            'title': '测试2',
            'source': 'test'
        })

        # 一个字符串包含两个番号（空格分隔）
        response = self.client.post('/api/search',
                                    json={'av_ids': ['hnvr-140 kawd-992']},
                                    content_type='application/json')

        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['results']), 2)
        ids = [r['av_id'] for r in data['results']]
        self.assertEqual(sorted(ids), ['HNVR-140', 'KAWD-992'])

    def test_search_av_mixed_separators(self):
        """测试混合分隔符（空格+逗号+换行）"""
        self.test_db.insert_av_info({
            'av_id': 'A-001',
            'title': '测试A',
            'source': 'test'
        })
        self.test_db.insert_av_info({
            'av_id': 'B-002',
            'title': '测试B',
            'source': 'test'
        })
        self.test_db.insert_av_info({
            'av_id': 'C-003',
            'title': '测试C',
            'source': 'test'
        })

        response = self.client.post('/api/search',
                                    json={'av_ids': ['a-001, b-002\nc-003']},
                                    content_type='application/json')

        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['results']), 3)
        ids = sorted(r['av_id'] for r in data['results'])
        self.assertEqual(ids, ['A-001', 'B-002', 'C-003'])


class TestDokuWikiClient(unittest.TestCase):
    """DokuWiki客户端测试"""

    def setUp(self):
        from dokuwiki import DokuWikiClient
        self.client = DokuWikiClient(
            url='http://localhost/dokuwiki',
            username='testuser',
            password='testpass'
        )

    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.client.url, 'http://localhost/dokuwiki')
        self.assertEqual(self.client.username, 'testuser')
        self.assertEqual(self.client.password, 'testpass')

    def test_cookie_transport_session(self):
        """新版DokuWiki使用会话cookie认证（不再使用token）"""
        from dokuwiki import _CookieTransport
        transport = _CookieTransport()
        self.assertIsNotNone(transport.cookie_jar)
        self.assertEqual(transport.verbose, 0)
        self.assertFalse(hasattr(self.client, '_get_auth_headers'))

    def test_cookie_transport_scheme(self):
        """传输层按URL选择http/https"""
        from dokuwiki import _CookieTransport
        self.assertFalse(_CookieTransport()._use_https)
        self.assertTrue(_CookieTransport(use_https=True)._use_https)

    def test_format_av_page(self):
        """测试格式化AV页面"""
        av_info = {
            'av_id': 'FORMAT-001',
            'title': '格式化测试',
            'studio': '测试制作商',
            'publisher': '测试发行商',
            'series': '测试系列',
            'release_date': '2024-01-01',
            'duration': '120分钟',
            'director': '测试导演',
            'rating': '4.5',
            'source': 'test',
            'actresses': ['演员1', '演员2'],
            'genres': ['类型1', '类型2']
        }

        content = self.client.format_av_page(av_info)

        self.assertIn('FORMAT-001', content)
        self.assertIn('格式化测试', content)
        self.assertIn('测试制作商', content)
        self.assertIn('演员1', content)
        self.assertIn('类型1', content)

    def test_format_av_page_with_json_strings(self):
        """测试格式化包含JSON字符串的AV页面"""
        av_info = {
            'av_id': 'FORMAT-002',
            'title': 'JSON测试',
            'release_date': '2024-12-11',
            'actresses': '["演员A", "演员B"]',
            'genres': '["类型A"]'
        }

        content = self.client.format_av_page(av_info)

        self.assertIn('演员A', content)
        self.assertIn('类型A', content)
        self.assertIn('{{:av:2024-12-11-format-002.jpg|}}', content)

    def test_format_av_page_empty_actresses(self):
        """测试演员为空时仍输出演员字段"""
        av_info = {
            'av_id': 'FORMAT-003',
            'title': '空演员测试',
            'release_date': '2024-12-11'
        }

        content = self.client.format_av_page(av_info)

        self.assertIn('演员:', content)
        self.assertIn('演员:\t-', content)

    def test_format_av_page_with_comment(self):
        """测试格式化包含评论的AV页面"""
        av_info = {
            'av_id': 'FORMAT-004',
            'title': '评论测试',
            'release_date': '2024-12-11',
            'comment': '值得一看\n第二行评论'
        }

        content = self.client.format_av_page(av_info)

        self.assertIn('评论:', content)
        self.assertIn('值得一看', content)
        self.assertIn('第二行评论', content)

    def test_format_av_page_empty_comment(self):
        """测试评论为空时仍输出评论字段"""
        av_info = {
            'av_id': 'FORMAT-005',
            'title': '空评论测试'
        }

        content = self.client.format_av_page(av_info)

        self.assertIn('评论:\t-', content)

    def test_get_cover_filename(self):
        """测试生成封面文件名"""
        from dokuwiki import get_cover_filename

        # 完整日期
        name = get_cover_filename({'av_id': 'HNVR-140', 'release_date': '2024-12-11'})
        self.assertEqual(name, '2024-12-11-hnvr-140.jpg')

        # 带时间后缀的日期
        name = get_cover_filename({'av_id': 'ABC-001', 'release_date': '2024-12-11T00:00:00'})
        self.assertEqual(name, '2024-12-11-abc-001.jpg')

        # 无日期
        name = get_cover_filename({'av_id': 'ABC-001'})
        self.assertEqual(name, 'abc-001.jpg')

        # 自定义扩展名
        name = get_cover_filename({'av_id': 'ABC-001', 'release_date': '2024-12-11'}, 'png')
        self.assertEqual(name, '2024-12-11-abc-001.png')


if __name__ == '__main__':
    unittest.main()
