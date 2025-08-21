import scrapy
import os
import re
from datetime import datetime


class ArxivSpider(scrapy.Spider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        categories = os.environ.get("CATEGORIES", "cs.CV")
        categories = categories.split(",")
        # Save target categories list for validation
        self.target_categories = set(map(str.strip, categories))
        self.start_urls = [
            f"https://arxiv.org/list/{cat}/new"
            for cat in self.target_categories
        ]  # 起始URL（计算机科学领域的最新论文）
        # Track seen papers to prevent duplicates across categories
        self.seen_papers = set()
        # Track statistics for deduplication
        self.total_papers_seen = 0
        self.duplicates_skipped = 0

    name = "arxiv"  # 爬虫名称
    allowed_domains = ["arxiv.org"]  # 允许爬取的域名

    def parse(self, response):
        # 提取每篇论文的信息
        anchors = []
        for li in response.css("div[id=dlpage] ul li"):
            href = li.css("a::attr(href)").get()
            if href and "item" in href:
                anchors.append(int(href.split("item")[-1]))

        # 遍历每篇论文的详细信息
        for paper in response.css("dl dt"):
            paper_anchor = paper.css("a[name^='item']::attr(name)").get()
            if not paper_anchor:
                continue

            paper_id = int(paper_anchor.split("item")[-1])
            if anchors and paper_id >= anchors[-1]:
                continue

            # 获取论文ID
            abstract_link = paper.css("a[title='Abstract']::attr(href)").get()
            if not abstract_link:
                continue

            arxiv_id = abstract_link.split("/")[-1]
            self.total_papers_seen += 1

            # Check if we've already seen this paper (deduplication)
            if arxiv_id in self.seen_papers:
                self.duplicates_skipped += 1
                self.logger.debug(
                    f"Skipping duplicate paper {arxiv_id} (already seen)"
                )
                continue

            # 获取对应的论文描述部分 (dd元素)
            paper_dd = paper.xpath("following-sibling::dd[1]")
            if not paper_dd:
                continue

            # 提取论文分类信息 - 在subjects部分
            subjects_text = paper_dd.css(
                ".list-subjects .primary-subject::text"
            ).get()
            if not subjects_text:
                # 如果找不到主分类，尝试其他方式获取分类
                subjects_text = paper_dd.css(".list-subjects::text").get()

            if subjects_text:
                # 解析分类信息，通常格式如 "Computer Vision and Pattern Recognition (cs.CV)"
                # 提取括号中的分类代码
                categories_in_paper = re.findall(r"\(([^)]+)\)", subjects_text)

                # 检查论文分类是否与目标分类有交集
                paper_categories = set(categories_in_paper)
                if paper_categories.intersection(self.target_categories):
                    # Mark this paper as seen to prevent future duplicates
                    self.seen_papers.add(arxiv_id)

                    yield {
                        "id": arxiv_id,
                        "categories": list(
                            paper_categories
                        ),  # 添加分类信息用于调试
                    }
                    self.logger.info(
                        f"Found paper {arxiv_id} with categories {paper_categories}"
                    )
                else:
                    self.logger.debug(
                        f"Skipped paper {arxiv_id} with categories {paper_categories} (not in target {self.target_categories})"
                    )
            else:
                # 如果无法获取分类信息，记录警告但仍然返回论文（保持向后兼容）
                self.logger.warning(
                    f"Could not extract categories for paper {arxiv_id}, including anyway"
                )
                # Mark this paper as seen to prevent future duplicates
                self.seen_papers.add(arxiv_id)

                yield {
                    "id": arxiv_id,
                    "categories": [],
                }

    def closed(self, reason):
        """Called when the spider is closed. Log deduplication statistics."""
        unique_papers = len(self.seen_papers)
        self.logger.info(f"Deduplication Summary:")
        self.logger.info(
            f"  Total papers encountered: {self.total_papers_seen}"
        )
        self.logger.info(f"  Duplicates skipped: {self.duplicates_skipped}")
        self.logger.info(f"  Unique papers yielded: {unique_papers}")
        if self.total_papers_seen > 0:
            dedup_rate = (
                self.duplicates_skipped / self.total_papers_seen
            ) * 100
            self.logger.info(f"  Deduplication rate: {dedup_rate:.1f}%")
