import re
import json
from bs4 import BeautifulSoup
from .base import BaseScraper

class JvrPornScraper(BaseScraper):
    """JVRPorn (jvrporn.com) 视频信息源

    番号格式：JVR100166（对应 https://jvrporn.com/video/100166/）
    """

    def __init__(self):
        super().__init__()
        self.base_url = 'https://jvrporn.com'
        self.logger.info(f"JvrPorn base_url: {self.base_url}")

    def get_source_name(self):
        return 'jvrporn'

    def _extract_video_id(self, av_id):
        """从番号提取视频ID：JVR100166 / JVR-100166 / 100166 -> 100166"""
        m = re.match(r'^JVR[-_\s]?(\d+)$', av_id, re.IGNORECASE)
        if m:
            return m.group(1)
        m = re.match(r'^(\d{5,6})$', av_id)
        if m:
            return m.group(1)
        return None

    def search(self, av_id):
        """从JVRPorn搜索番号信息"""
        self.logger.info(f"[JvrPorn] 开始搜索: {av_id}")

        video_id = self._extract_video_id(av_id)
        if not video_id:
            self.logger.info(f"[JvrPorn] 番号格式不匹配，跳过: {av_id}")
            return None

        url = f"{self.base_url}/video/{video_id}/"
        self.logger.info(f"[JvrPorn] 请求URL: {url}")

        try:
            response = self.make_request(url)
            if not response:
                self.logger.warning(f"[JvrPorn] 请求失败: {av_id}")
                return None

            soup = BeautifulSoup(response.text, 'html.parser')

            av_info = {
                'av_id': f"JVR{video_id}",
                'source': self.get_source_name(),
                'studio': 'JVRPorn'
            }

            # 优先解析JSON-LD VideoObject
            video_obj = self._find_video_object(soup)
            if video_obj:
                title = video_obj.get('name')
                if title:
                    av_info['title'] = self.clean_text(title)

                actors = video_obj.get('actor') or []
                actresses = [a.get('name', '').strip() for a in actors
                             if isinstance(a, dict) and a.get('name')]
                if actresses:
                    av_info['actresses'] = actresses

                keywords = video_obj.get('keywords') or ''
                if isinstance(keywords, str):
                    genres = [g.strip() for g in keywords.split(',') if g.strip()]
                    if genres:
                        av_info['genres'] = genres

                upload_date = video_obj.get('uploadDate') or ''
                if upload_date:
                    av_info['release_date'] = upload_date[:10]

                thumb = video_obj.get('thumbnailUrl')
                if isinstance(thumb, list) and thumb:
                    av_info['cover_url'] = thumb[0]
                elif isinstance(thumb, str):
                    av_info['cover_url'] = thumb

            # 兜底：标题
            if not av_info.get('title'):
                h1 = soup.find('h1')
                if h1:
                    av_info['title'] = self.clean_text(h1.text)

            # 兜底：封面
            if not av_info.get('cover_url'):
                og_image = soup.find('meta', property='og:image')
                if og_image:
                    av_info['cover_url'] = og_image.get('content', '')

            # 时长：basic-info 的 Total duration
            for dt in soup.find_all('dt'):
                if dt.text.strip() == 'Total duration':
                    dd = dt.find_next_sibling('dd')
                    if dd:
                        av_info['duration'] = self.clean_text(dd.text)
                    break

            # 兜底：演员/标签（basic-info）
            if not av_info.get('actresses'):
                for dt in soup.find_all('dt'):
                    if dt.text.strip() == 'Actress':
                        dd = dt.find_next_sibling('dd')
                        if dd:
                            av_info['actresses'] = [
                                self.clean_text(a.text) for a in dd.find_all('a') if a.text.strip()
                            ]
                        break

            if not av_info.get('genres'):
                for dt in soup.find_all('dt'):
                    if dt.text.strip() == 'Tags':
                        dd = dt.find_next_sibling('dd')
                        if dd:
                            av_info['genres'] = [
                                self.clean_text(a.text) for a in dd.find_all('a') if a.text.strip()
                            ]
                        break

            if not av_info.get('title') and not av_info.get('cover_url'):
                self.logger.warning(f"[JvrPorn] 页面无有效数据: {av_id}")
                return None

            self.logger.info(f"[JvrPorn] 搜索成功: {av_info['av_id']}")
            return av_info

        except Exception as e:
            self.logger.error(f"[JvrPorn] 搜索异常: {e}", exc_info=True)
            return None

    def _find_video_object(self, soup):
        """从页面JSON-LD中查找VideoObject"""
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.get_text())
            except (json.JSONDecodeError, TypeError):
                continue

            nodes = []
            if isinstance(data, dict):
                nodes = data.get('@graph', [data])
            elif isinstance(data, list):
                nodes = data

            for node in nodes:
                if isinstance(node, dict) and node.get('@type') == 'VideoObject':
                    return node
        return None
