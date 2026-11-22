import re
from urllib.parse import quote
from .base import BaseScraper
from config import Config

class DokuWikiScraper(BaseScraper):
    """DokuWiki av 命名空间搜索源"""

    def __init__(self):
        super().__init__()
        self.base_url = (Config.DOKUWIKI_URL or '').rstrip('/')
        self.logger.info(f"DokuWiki base_url: {self.base_url}")

    def get_source_name(self):
        return 'dokuwiki'

    def search(self, av_id):
        """从DokuWiki的av命名空间搜索番号信息"""
        self.logger.info(f"[DokuWiki] 开始搜索: {av_id}")
        base_url = (Config.DOKUWIKI_URL or '').rstrip('/')
        if base_url:
            self.base_url = base_url

        try:
            page_id = f"av:{av_id.lower()}"
            raw = self._fetch_raw(page_id)

            if not raw:
                # 页面名可能带日期前缀等，通过搜索查找
                page_id = self._find_page_id(av_id)
                if not page_id:
                    self.logger.warning(f"[DokuWiki] 未找到页面: {av_id}")
                    return None
                self.logger.info(f"[DokuWiki] 搜索结果页面: {page_id}")
                raw = self._fetch_raw(page_id)
                if not raw:
                    return None

            av_info = self._parse_page(raw, av_id)
            if av_info:
                self.logger.info(f"[DokuWiki] 搜索成功: {av_id}")
            return av_info

        except Exception as e:
            self.logger.error(f"[DokuWiki] 搜索异常: {e}", exc_info=True)
            return None

    def _fetch_raw(self, page_id):
        """获取页面原始wiki文本"""
        url = f"{self.base_url}/doku.php"
        resp = self.make_request(url, params={'id': page_id, 'do': 'export_raw'})
        if not resp:
            return None

        text = resp.text.strip()
        if not text or '该主题尚不存在' in text or 'This topic does not exist' in text:
            return None
        return text

    def _find_page_id(self, av_id):
        """通过DokuWiki搜索查找页面ID（处理日期前缀等命名）"""
        url = f"{self.base_url}/doku.php"
        resp = self.make_request(url, params={'do': 'search', 'q': av_id})
        if not resp:
            return None

        # 从搜索结果链接提取av命名空间页面id
        pattern = re.compile(r'id=(av(?:%3A|:)[A-Za-z0-9_\-.]+)', re.IGNORECASE)
        for m in pattern.finditer(resp.text):
            page_id = m.group(1).replace('%3A', ':').replace('%3a', ':')
            if av_id.lower() in page_id.lower():
                return page_id
        return None

    def _parse_page(self, raw, search_id):
        """解析页面wiki文本"""
        lines = raw.split('\n')

        av_info = {
            'av_id': search_id.upper(),
            'source': self.get_source_name()
        }

        # 标题：====== 标题 ====== 或第一行纯文本
        for line in lines:
            line = line.strip()
            if not line:
                continue
            m = re.match(r'^={2,}\s*(.+?)\s*={2,}$', line)
            av_info['title'] = m.group(1) if m else line
            break

        field_map = {
            '番号': 'av_id',
            '识别码': 'av_id',
            '发行日期': 'release_date',
            '长度': 'duration',
            '导演': 'director',
            '制作商': 'studio',
            '发行商': 'publisher',
            '系列': 'series',
            '网站评分': 'rating',
            '评分': 'rating',
        }
        multi_map = {
            '类别': 'genres',
            '演员': 'actresses',
        }

        for line in lines:
            if ':' not in line and '：' not in line:
                continue

            sep = ':' if ':' in line else '：'
            label, _, value = line.partition(sep)
            label = label.strip()
            value = value.strip().rstrip('\\').strip()

            if not value:
                continue

            key = field_map.get(label)
            if key:
                av_info[key] = value.upper() if key == 'av_id' else value
                continue

            key = multi_map.get(label)
            if key:
                av_info[key] = [v for v in value.split() if v]

        # 评论（值可能含空格/冒号，独立处理）
        m = re.search(r'^评论[:：]\s*(.*?)\s*(?:\\\\)?\s*$', raw, re.MULTILINE)
        if m:
            comment = m.group(1).strip().rstrip('\\').strip()
            if comment and comment != '-':
                av_info['comment'] = comment

        # 封面：{{:av:文件名|}}
        m = re.search(r'\{\{:av:([^|}]+)', raw)
        if m:
            filename = m.group(1).strip()
            av_info['cover_url'] = f"{self.base_url}/lib/exe/fetch.php?media=av:{quote(filename)}"
            self.logger.info(f"[DokuWiki] 封面URL: {av_info['cover_url']}")

        # 没有任何结构化字段且没有封面，视为无效页面
        if len(av_info) <= 3 and 'cover_url' not in av_info:
            return None

        return av_info
