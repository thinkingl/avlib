import re
from bs4 import BeautifulSoup
from .base import BaseScraper

class JavDBScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.base_url = 'https://javdb.com'
        self.logger.info(f"JavDB base_url: {self.base_url}")

    def get_source_name(self):
        return 'javdb'

    def search(self, av_id):
        """从JavDB搜索番号信息"""
        self.logger.info(f"[JavDB] 开始搜索: {av_id}")
        try:
            search_url = f"{self.base_url}/search"
            params = {'q': av_id, 'f': 'all'}
            self.logger.info(f"[JavDB] 搜索URL: {search_url}, 参数: {params}")

            response = self.make_request(search_url, params=params)

            if not response:
                self.logger.warning(f"[JavDB] 搜索请求失败")
                return None

            self.logger.info(f"[JavDB] 搜索响应URL: {response.url}")
            soup = BeautifulSoup(response.text, 'html.parser')

            # 查找匹配的结果 - 使用新的选择器
            movie_list = soup.find('div', class_='movie-list')
            if not movie_list:
                self.logger.warning(f"[JavDB] 未找到movie-list")
                return None

            items = movie_list.find_all('div', class_='item')
            self.logger.info(f"[JavDB] 找到 {len(items)} 个结果")

            target_url = None

            for item in items:
                link = item.find('a', class_='box')
                if link:
                    href = link.get('href', '')
                    # 获取标题中的番号
                    title_div = item.find('div', class_='video-title')
                    if title_div:
                        strong = title_div.find('strong')
                        if strong and av_id.upper() in strong.text.strip().upper():
                            target_url = f"{self.base_url}{href}"
                            self.logger.info(f"[JavDB] 找到匹配链接: {target_url}")
                            break

            if not target_url and items:
                # 使用第一个结果
                first_link = items[0].find('a', class_='box')
                if first_link:
                    target_url = f"{self.base_url}{first_link.get('href', '')}"
                    self.logger.info(f"[JavDB] 使用第一个结果: {target_url}")

            if not target_url:
                self.logger.warning(f"[JavDB] 未找到匹配结果")
                return None

            # 获取详情页
            self.logger.info(f"[JavDB] 请求详情页: {target_url}")
            detail_response = self.make_request(target_url)
            if not detail_response:
                self.logger.warning(f"[JavDB] 详情页请求失败")
                return None

            detail_soup = BeautifulSoup(detail_response.text, 'html.parser')

            av_info = {
                'av_id': av_id,
                'source': self.get_source_name()
            }

            # 获取标题
            title_tag = detail_soup.find('h2', class_='title')
            if title_tag:
                av_info['title'] = self.clean_text(title_tag.text)
                self.logger.info(f"[JavDB] 标题: {av_info['title']}")
            else:
                self.logger.warning(f"[JavDB] 未找到标题")

            # 获取封面图片
            cover_img = detail_soup.find('div', class_='column-video-cover')
            if cover_img:
                img = cover_img.find('img')
                if img:
                    av_info['cover_url'] = img.get('src', '')
                    self.logger.info(f"[JavDB] 封面URL: {av_info['cover_url']}")
            else:
                self.logger.warning(f"[JavDB] 未找到封面")

            # 获取详细信息 - 使用新的选择器 video-meta-panel
            info_section = detail_soup.find('div', class_='video-meta-panel')
            if info_section:
                rows = info_section.find_all('div', class_='panel-block')
                self.logger.debug(f"[JavDB] 找到 {len(rows)} 个信息块")

                for row in rows:
                    label = row.find('strong')
                    value = row.find('span', class_='value')

                    if not label or not value:
                        continue

                    label_text = label.text.strip().rstrip(':')
                    value_text = value.text.strip()

                    if '番號' in label_text or '番号' in label_text:
                        pass  # 已经有av_id
                    elif '日期' in label_text:
                        av_info['release_date'] = value_text
                    elif '時長' in label_text or '时长' in label_text:
                        av_info['duration'] = value_text
                    elif '導演' in label_text or '导演' in label_text:
                        av_info['director'] = value_text
                    elif '片商' in label_text:
                        av_info['studio'] = value_text
                    elif '發行' in label_text or '发行' in label_text:
                        av_info['publisher'] = value_text
                    elif '系列' in label_text:
                        av_info['series'] = value_text
                    elif '評分' in label_text or '评分' in label_text:
                        av_info['rating'] = value_text
                    elif '類別' in label_text or '类别' in label_text:
                        # 获取所有类别链接
                        genres = []
                        for link in value.find_all('a'):
                            genre = self.clean_text(link.text)
                            if genre:
                                genres.append(genre)
                        av_info['genres'] = genres
                    elif '演員' in label_text or '演员' in label_text:
                        # 获取所有演员链接
                        actresses = []
                        for link in value.find_all('a'):
                            actress = self.clean_text(link.text)
                            if actress:
                                actresses.append(actress)
                        av_info['actresses'] = actresses
            else:
                self.logger.warning(f"[JavDB] 未找到信息区域")

            # 如果genres和actresses没有从上面获取到，使用备用方法
            if 'genres' not in av_info:
                av_info['genres'] = []
            if 'actresses' not in av_info:
                av_info['actresses'] = []

            self.logger.info(f"[JavDB] 演员: {av_info['actresses']}")
            self.logger.info(f"[JavDB] 类型: {av_info['genres']}")

            self.logger.info(f"[JavDB] 搜索成功: {av_id}")
            return av_info

        except Exception as e:
            self.logger.error(f"[JavDB] 搜索异常: {e}", exc_info=True)
            return None
