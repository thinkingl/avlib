import unittest
import os
import json
import tempfile
from database import Database

class TestDatabase(unittest.TestCase):
    """数据库模块测试"""

    def setUp(self):
        """测试前准备"""
        self.db_path = tempfile.mktemp(suffix='.db')
        self.db = Database(db_path=self.db_path)

    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_init_db(self):
        """测试数据库初始化"""
        # 验证数据库文件已创建
        self.assertTrue(os.path.exists(self.db_path))

        # 验证表已创建
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # 检查av_info表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='av_info'")
        self.assertIsNotNone(cursor.fetchone())

        # 检查search_history表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='search_history'")
        self.assertIsNotNone(cursor.fetchone())

        # 检查dokuwiki_submissions表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dokuwiki_submissions'")
        self.assertIsNotNone(cursor.fetchone())

        conn.close()

    def test_insert_av_info(self):
        """测试插入AV信息"""
        av_data = {
            'av_id': 'TEST-001',
            'title': '测试标题',
            'studio': '测试制作商',
            'publisher': '测试发行商',
            'series': '测试系列',
            'release_date': '2024-01-01',
            'duration': '120分钟',
            'director': '测试导演',
            'actresses': ['演员1', '演员2'],
            'genres': ['类型1', '类型2'],
            'cover_url': 'http://example.com/cover.jpg',
            'cover_data': b'fake_image_data',
            'cover_mime': 'image/jpeg',
            'source': 'test',
            'rating': '4.5'
        }

        result = self.db.insert_av_info(av_data)
        self.assertTrue(result)

        # 验证数据已插入
        saved = self.db.get_av_info('TEST-001')
        self.assertIsNotNone(saved)
        self.assertEqual(saved['av_id'], 'TEST-001')
        self.assertEqual(saved['title'], '测试标题')
        self.assertEqual(saved['studio'], '测试制作商')

    def test_insert_av_info_with_image_data(self):
        """测试插入包含图片数据的AV信息"""
        image_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100  # 模拟PNG数据

        av_data = {
            'av_id': 'TEST-IMG-001',
            'title': '测试图片',
            'cover_data': image_data,
            'cover_mime': 'image/png',
            'source': 'test'
        }

        result = self.db.insert_av_info(av_data)
        self.assertTrue(result)

        # 验证图片数据已保存
        cover_data, cover_mime = self.db.get_cover_data('TEST-IMG-001')
        self.assertEqual(cover_data, image_data)
        self.assertEqual(cover_mime, 'image/png')

    def test_get_av_info_not_found(self):
        """测试获取不存在的AV信息"""
        result = self.db.get_av_info('NOT-EXIST')
        self.assertIsNone(result)

    def test_update_av_info(self):
        """测试更新AV信息（INSERT OR REPLACE）"""
        # 首次插入
        av_data1 = {
            'av_id': 'TEST-UPDATE',
            'title': '原始标题',
            'source': 'test'
        }
        self.db.insert_av_info(av_data1)

        # 更新
        av_data2 = {
            'av_id': 'TEST-UPDATE',
            'title': '更新后标题',
            'source': 'test2'
        }
        self.db.insert_av_info(av_data2)

        # 验证已更新
        saved = self.db.get_av_info('TEST-UPDATE')
        self.assertEqual(saved['title'], '更新后标题')
        self.assertEqual(saved['source'], 'test2')

    def test_get_all_av_info(self):
        """测试获取所有AV信息"""
        # 插入多条数据
        for i in range(5):
            av_data = {
                'av_id': f'TEST-LIST-{i:03d}',
                'title': f'标题{i}',
                'source': 'test'
            }
            self.db.insert_av_info(av_data)

        # 获取所有
        result = self.db.get_all_av_info(limit=10)
        self.assertEqual(len(result), 5)

    def test_get_all_av_info_with_limit(self):
        """测试限制获取数量"""
        # 插入多条数据
        for i in range(10):
            av_data = {
                'av_id': f'TEST-LIMIT-{i:03d}',
                'title': f'标题{i}',
                'source': 'test'
            }
            self.db.insert_av_info(av_data)

        # 限制获取3条
        result = self.db.get_all_av_info(limit=3)
        self.assertEqual(len(result), 3)

    def test_add_search_history(self):
        """测试添加搜索历史"""
        self.db.add_search_history('TEST-001', 'javbus', True)
        self.db.add_search_history('TEST-002', 'javdb', False)

        # 验证历史已记录（通过直接查询）
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM search_history')
        count = cursor.fetchone()[0]
        conn.close()

        self.assertEqual(count, 2)

    def test_add_dokuwiki_submission(self):
        """测试添加DokuWiki提交记录"""
        self.db.add_dokuwiki_submission('TEST-001', 'av:TEST-001', 'success')

        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM dokuwiki_submissions WHERE av_id = ?', ('TEST-001',))
        row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row['status'], 'success')

    def test_get_av_count(self):
        """测试获取AV数量"""
        # 初始为0
        self.assertEqual(self.db.get_av_count(), 0)

        # 插入3条
        for i in range(3):
            self.db.insert_av_info({
                'av_id': f'TEST-COUNT-{i:03d}',
                'source': 'test'
            })

        self.assertEqual(self.db.get_av_count(), 3)

    def test_delete_av_info(self):
        """测试删除AV信息"""
        # 插入
        self.db.insert_av_info({
            'av_id': 'TEST-DELETE',
            'title': '待删除',
            'source': 'test'
        })

        # 确认存在
        self.assertIsNotNone(self.db.get_av_info('TEST-DELETE'))

        # 删除
        self.db.delete_av_info('TEST-DELETE')

        # 确认已删除
        self.assertIsNone(self.db.get_av_info('TEST-DELETE'))

    def test_get_cover_data_not_found(self):
        """测试获取不存在的封面数据"""
        cover_data, cover_mime = self.db.get_cover_data('NOT-EXIST')
        self.assertIsNone(cover_data)
        self.assertIsNone(cover_mime)

    def test_insert_av_info_with_json_fields(self):
        """测试插入包含JSON字段的AV信息"""
        av_data = {
            'av_id': 'TEST-JSON',
            'title': 'JSON测试',
            'actresses': '["演员A", "演员B"]',  # 已经是JSON字符串
            'genres': '["类型1", "类型2"]',
            'source': 'test'
        }

        result = self.db.insert_av_info(av_data)
        self.assertTrue(result)

        saved = self.db.get_av_info('TEST-JSON')
        self.assertEqual(saved['actresses'], '["演员A", "演员B"]')
        self.assertEqual(saved['genres'], '["类型1", "类型2"]')


if __name__ == '__main__':
    unittest.main()
