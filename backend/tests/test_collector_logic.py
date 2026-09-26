import hashlib

from app.collectors.base import RawPostData
from app.collectors.facebook.adapter import FacebookPageAdapter
from app.collectors.facebook.collector import FacebookPageCollector
from app.models.crawl_job import CrawlJob, CrawlStatus


def test_collector_url_validation():
    collector = FacebookPageCollector()
    assert collector.validate_target("https://www.facebook.com/tunisfashion")
    assert collector.validate_target("http://facebook.com/pages/123456")
    assert collector.validate_target("https://m.facebook.com/store")
    assert collector.validate_target("https://fb.watch/xyz123")

    # Invalid targets
    assert not collector.validate_target("https://twitter.com/example")
    assert not collector.validate_target("https://instagram.com/example")
    assert not collector.validate_target("not-a-url")
    assert not collector.validate_target("")


def test_post_identifier_extraction_and_deduplication():
    # 1. Deduplication using platform post id from permalink
    p1 = "https://www.facebook.com/tunisfashion/posts/1029384756"
    id1 = FacebookPageAdapter.extract_platform_post_id(p1, "Text of post 1")
    assert id1 == "1029384756"

    # Same permalink with query parameters should yield same platform post id
    p1_with_query = "https://www.facebook.com/tunisfashion/posts/1029384756?mibextid=ZbWKwL"
    id1_query = FacebookPageAdapter.extract_platform_post_id(p1_with_query, "Text of post 1")
    assert id1_query == "1029384756"

    # 2. Permalinks with fbid
    p2 = "https://www.facebook.com/photo.php?fbid=9876543210&set=a.123"
    id2 = FacebookPageAdapter.extract_platform_post_id(p2, "Photo caption")
    assert id2 == "9876543210"

    # 3. Fallback to content hash if no permalink
    id3 = FacebookPageAdapter.extract_platform_post_id(None, "Unique promo text 123")
    assert id3.startswith("gen_")


def test_scroll_stopping_conditions_simulation():
    max_posts = 5
    max_scroll_cycles = 10
    collected_posts: list[RawPostData] = []
    seen_ids = set()

    # Simulate scroll cycles
    scroll_cycles = 0
    stagnant_cycles = 0

    # Mock feed generation per cycle
    mock_feed_per_cycle = [
        [("id_1", "Post 1 text"), ("id_2", "Post 2 text")],
        [("id_2", "Post 2 duplicate"), ("id_3", "Post 3 text")],
        [("id_4", "Post 4 text"), ("id_5", "Post 5 text"), ("id_6", "Post 6 text")],
    ]

    for cycle_posts in mock_feed_per_cycle:
        new_in_cycle = 0
        for p_id, p_text in cycle_posts:
            if len(collected_posts) >= max_posts:
                break
            if p_id in seen_ids:
                continue
            seen_ids.add(p_id)
            collected_posts.append(
                RawPostData(
                    platform_post_id=p_id,
                    permalink=f"https://fb.com/{p_id}",
                    text=p_text,
                    published_at=None,
                    raw_data={},
                    content_hash=hashlib.sha256(p_text.encode()).hexdigest(),
                )
            )
            new_in_cycle += 1

        scroll_cycles += 1
        if len(collected_posts) >= max_posts:
            break
        if new_in_cycle == 0:
            stagnant_cycles += 1
            if stagnant_cycles >= 3:
                break
        else:
            stagnant_cycles = 0

    assert len(collected_posts) == max_posts
    assert scroll_cycles <= max_scroll_cycles


def test_crawl_job_status_transitions():
    job = CrawlJob(
        target_url="https://facebook.com/testpage",
        status=CrawlStatus.PENDING,
    )
    assert job.status == CrawlStatus.PENDING

    # Transition to RUNNING
    job.status = CrawlStatus.RUNNING
    assert job.status == CrawlStatus.RUNNING

    # Transition to SUCCESS
    job.status = CrawlStatus.SUCCESS
    job.posts_collected = 15
    assert job.status == CrawlStatus.SUCCESS
    assert job.posts_collected == 15
