#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from confluent_kafka import Producer
import json
import os
import logging
import threading
import time
import random
from collections import deque
from datetime import datetime

from core.crawler import BilibiliCommentCrawler

def env(key: str, default: str = "") -> str:
    value = os.getenv(key, default)
    if not value:
        raise ValueError(f"环境变量 {key} 未设置")
    return value


KAFKA_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'bilibili-comments')
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '50000'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
MIN_DELAY = float(os.getenv('DEFAULT_MIN_DELAY', '1.0'))
MAX_DELAY = float(os.getenv('DEFAULT_MAX_DELAY', '3.0'))

import threading

log_buffer = deque(maxlen=1000)
log_buffer_lock = threading.Lock()


class BufferHandler(logging.Handler):
    def emit(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'message': self.format(record),
            'name': record.name
        }
        with log_buffer_lock:
            log_buffer.append(log_entry)


logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)
logging.getLogger().addHandler(BufferHandler())

app = FastAPI(title="Bilibili Scraper API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

crawler = None
kafka_producer = None
crawler_thread = None
crawler_status = {
    "is_running": False,
    "progress": {"total": 0, "processed": 0, "completed": 0, "failed": 0, "remaining": 0},
    "current_task": None
}


def get_crawler():
    """获取全局crawler实例"""
    global crawler
    if crawler is None:
        crawler = BilibiliCommentCrawler()
        logger.info(f"Crawler初始化完成")
    return crawler


def get_kafka_producer():
    global kafka_producer
    if kafka_producer is None:
        kafka_producer = Producer({
            'bootstrap.servers': KAFKA_SERVERS,
            'compression.type': 'gzip'
        })
        logger.info(f"Kafka连接成功: {KAFKA_SERVERS}")
    return kafka_producer


class CrawlerThread(threading.Thread):
    def __init__(self, tasks: List[str], min_delay: float, max_delay: float):
        super().__init__(daemon=True)
        self.tasks = tasks
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.running = True

    def run(self):
        global crawler_status

        crawler_instance = get_crawler()
        producer = get_kafka_producer()

        crawler_status['progress']['total'] = len(self.tasks)
        logger.info(f"爬虫启动: {len(self.tasks)}个任务")

        for idx, task in enumerate(self.tasks):
            if not self.running:
                break

            crawler_status['current_task'] = task
            logger.info(f"[{idx + 1}/{len(self.tasks)}] 处理: {task}")

            try:
                oid, comment_type, bvid = crawler_instance.parse_input(task)
                all_comments = []
                page_token = ""
                page = 1

                while True:
                    comments, next_token = crawler_instance.get_comments_rpc(
                        oid=oid,
                        page_token=page_token,
                        comment_type=comment_type,
                        sort_mode="MAIN_LIST_HOT",
                        bvid=bvid,
                    )

                    if not comments:
                        break

                    all_comments.extend(comments)
                    logger.info(f"第{page}页: {len(comments)}条, 累计{len(all_comments)}条")

                    if not next_token:
                        break

                    page_token = next_token
                    page += 1
                    time.sleep(random.uniform(self.min_delay, self.max_delay))

                # 发送到Kafka
                for comment in all_comments:
                    producer.produce(
                        KAFKA_TOPIC,
                        value=json.dumps(comment).encode('utf-8')
                    )
                producer.flush()

                crawler_status['progress']['completed'] += 1
                logger.info(f"✓ 完成: {task}, 共{len(all_comments)}条")

            except Exception as e:
                logger.error(f"✗ 失败: {task}, 错误: {e}")
                crawler_status['progress']['failed'] += 1

            crawler_status['progress']['processed'] += 1
            crawler_status['progress']['remaining'] = (
                    crawler_status['progress']['total'] - crawler_status['progress']['processed']
            )

            if idx < len(self.tasks) - 1:
                time.sleep(random.uniform(self.min_delay, self.max_delay))

        logger.info(
            f"全部完成: 成功{crawler_status['progress']['completed']}, "
            f"失败{crawler_status['progress']['failed']}"
        )
        crawler_status['is_running'] = False
        crawler_status['current_task'] = None

    def stop(self):
        self.running = False


class StartRequest(BaseModel):
    min_delay: float = MIN_DELAY
    max_delay: float = MAX_DELAY
    tasks: List[str]


@app.get("/")
async def root():
    return {
        "status": "running",
        "config": {
            "kafka": KAFKA_SERVERS,
            "topic": KAFKA_TOPIC,
            "batch_size": BATCH_SIZE,
            "log_level": LOG_LEVEL,
            "defaults": {
                "min_delay": MIN_DELAY,
                "max_delay": MAX_DELAY
            }
        }
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/start")
async def start_crawler(req: StartRequest):
    global crawler_thread, crawler_status

    if crawler_status['is_running']:
        raise HTTPException(status_code=400, detail="爬虫正在运行中")

    if not req.tasks:
        raise HTTPException(status_code=400, detail="任务列表不能为空")

    # 确保crawler已初始化
    crawler_instance = get_crawler()

    crawler_status = {
        "is_running": True,
        "progress": {
            "total": len(req.tasks),
            "processed": 0,
            "completed": 0,
            "failed": 0,
            "remaining": len(req.tasks)
        },
        "current_task": None
    }

    crawler_thread = CrawlerThread(req.tasks, req.min_delay, req.max_delay)
    crawler_thread.start()

    logger.info(f"已启动: {len(req.tasks)}个任务")
    return {"message": "已启动", "task_count": len(req.tasks)}


@app.post("/stop")
async def stop_crawler():
    global crawler_thread, crawler_status

    if not crawler_status['is_running']:
        raise HTTPException(status_code=400, detail="爬虫未运行")

    if crawler_thread:
        crawler_thread.stop()

    crawler_status['is_running'] = False
    logger.info("爬虫已停止")
    return {"message": "已停止"}


@app.get("/status")
async def get_status():
    result = crawler_status.copy()

    # 添加设备信息（如果crawler已初始化）
    if crawler is not None:
        result["device"] = {
            "buvid": crawler.buvid[:16] + '...',
            "device": f"{crawler.device_brand} {crawler.device_model}",
            "fp": crawler.fp[:16] + '...'
        }

    return result


@app.get("/logs")
async def get_logs(limit: int = 100):
    with log_buffer_lock:
        logs = list(log_buffer)
    return {"total": len(logs), "logs": logs[-limit:] if limit > 0 else logs}


@app.delete("/logs")
async def clear_logs():
    with log_buffer_lock:
        log_buffer.clear()
    logger.info("日志已清空")
    return {"message": "已清空"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)