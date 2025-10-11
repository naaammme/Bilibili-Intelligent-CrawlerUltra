#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from contextlib import asynccontextmanager
import clickhouse_connect
from confluent_kafka.admin import AdminClient
from confluent_kafka import Consumer, TopicPartition, KafkaException
import os
import logging
from datetime import datetime

from consumer import KafkaConsumerThread


def env(key: str, default: str = "") -> str:
    value = os.getenv(key, default)
    if not value:
        raise ValueError(f"环境变量 {key} 未设置")
    return value


CH_HOST = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
CH_PORT = int(os.getenv('CLICKHOUSE_PORT', '8123'))
CH_DB = os.getenv('CLICKHOUSE_DB', 'bilibili')
CH_USER = os.getenv('CLICKHOUSE_USER', 'default')
CH_PASSWORD = os.getenv('CLICKHOUSE_PASSWORD', '')

KAFKA_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'bilibili-comments')
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '50000'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

clickhouse_client = None
kafka_consumer_thread = None


def get_clickhouse_client():
    global clickhouse_client
    if clickhouse_client is None:
        clickhouse_client = clickhouse_connect.get_client(
            host=CH_HOST,
            port=CH_PORT,
            database=CH_DB,
            username=CH_USER,
            password=CH_PASSWORD,
            connect_timeout=10,
            send_receive_timeout=300,
        )
        logger.info(f"ClickHouse连接成功: {CH_HOST}:{CH_PORT}")
    return clickhouse_client


def batch_insert_comments(comments: List[dict]):
    if not comments:
        return

    valid_comments = []

    for comment in comments:
        if not all(key in comment for key in ['comment_id', 'user_uid', 'content']):
            continue

        ctime = datetime.fromisoformat(comment['ctime'])

        valid_comments.append([
            int(comment.get('comment_id', 0)),
            str(comment.get('video_bvid', '')),
            int(comment.get('type', 1)),
            int(comment.get('user_uid', 0)),
            str(comment.get('user_name', '')),
            str(comment.get('content', '')),
            ctime,
            int(comment.get('parent_id', 0)),
            int(comment.get('root_id', 0)),
            int(comment.get('comment_type', 1))
        ])

    if not valid_comments:
        logger.warning(f"批次中所有评论都无效")
        return

    client = get_clickhouse_client()
    client.insert(
        'comments',
        valid_comments,
        column_names=[
            'comment_id', 'video_bvid', 'type', 'user_uid',
            'user_name', 'content', 'ctime',
            'parent_id', 'root_id', 'comment_type'
        ]
    )

    logger.info(f"成功插入 {len(valid_comments)} 条评论")


def get_kafka_stats():
    consumer = None
    try:
        admin = AdminClient({'bootstrap.servers': KAFKA_SERVERS})
        metadata = admin.list_topics(timeout=5)

        if KAFKA_TOPIC not in metadata.topics:
            return {
                "kafka_connected": True,
                "topic_exists": False,
                "pending_messages": 0,
                "consumer_lag": 0
            }

        topic_metadata = metadata.topics[KAFKA_TOPIC]
        partitions = list(topic_metadata.partitions.keys())

        if not partitions:
            return {
                "kafka_connected": True,
                "topic_exists": True,
                "pending_messages": 0,
                "consumer_lag": 0,
                "partitions": 0
            }

        consumer = Consumer({
            'bootstrap.servers': KAFKA_SERVERS,
            'group.id': 'bilibili-comment-consumer',
            'enable.auto.commit': False
        })

        topic_partitions = [TopicPartition(KAFKA_TOPIC, p) for p in partitions]

        # 获取watermark和committed offset
        watermarks = {tp.partition: consumer.get_watermark_offsets(tp, timeout=5)[1]
                     for tp in topic_partitions}
        committed = consumer.committed(topic_partitions, timeout=5)

        # 计算lag
        total_lag = sum(
            max(0, watermarks.get(tp.partition, 0) - (tp.offset if tp and tp.offset >= 0 else 0))
            for tp in committed
        )

        return {
            "kafka_connected": True,
            "topic_exists": True,
            "pending_messages": total_lag,
            "consumer_lag": total_lag,
            "partitions": len(partitions)
        }
    except KafkaException as e:
        logger.error(f"获取Kafka统计失败: {e}")
        return {"kafka_connected": False, "error": str(e)}
    except Exception as e:
        logger.error(f"获取Kafka统计失败: {e}")
        return {"kafka_connected": False, "error": str(e)}
    finally:
        if consumer is not None:
            consumer.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global kafka_consumer_thread

    kafka_consumer_thread = KafkaConsumerThread(
        bootstrap_servers=KAFKA_SERVERS,
        topic=KAFKA_TOPIC,
        group_id='bilibili-comment-consumer',
        batch_callback=batch_insert_comments,
        batch_size=BATCH_SIZE
    )
    kafka_consumer_thread.start()
    logger.info("Kafka消费者已启动")

    yield

    if kafka_consumer_thread:
        kafka_consumer_thread.stop()
        kafka_consumer_thread.join(timeout=10)

    global clickhouse_client
    if clickhouse_client:
        clickhouse_client.close()
        clickhouse_client = None


app = FastAPI(title="Bilibili Comment Query API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserInfo(BaseModel):
    user_uid: str
    user_names: List[str]
    total_comments: int
    first_comment_time: str
    last_comment_time: str


class Comment(BaseModel):
    comment_id: int
    video_bvid: str
    type: int
    user_name: str
    content: str
    ctime: str
    parent_id: int
    root_id: int
    comment_type: int


class UserCommentsResponse(BaseModel):
    user_info: UserInfo
    comments: List[Comment]
    total: int
    page: int
    page_size: int


@app.get("/")
async def root():
    return {
        "message": "Bilibili Comment Query API",
        "status": "running",
        "config": {
            "clickhouse": f"{CH_HOST}:{CH_PORT}/{CH_DB}",
            "kafka": f"{KAFKA_SERVERS}/{KAFKA_TOPIC}",
            "batch_size": BATCH_SIZE
        }
    }


@app.get("/health")
async def health_check():
    client = get_clickhouse_client()
    client.query("SELECT 1")

    return {
        "status": "healthy",
        "database": "connected",
        "kafka_consumer": kafka_consumer_thread.is_alive() if kafka_consumer_thread else False
    }


@app.get("/api/user/{user_uid}", response_model=UserCommentsResponse)
async def get_user_comments(
        user_uid: str,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        keyword: str = Query("", description="关键词搜索"),
        comment_type: Optional[int] = Query(None, ge=1, le=2, description="1=主评论,2=回复"),
        content_type: Optional[int] = Query(None, description="1=视频,11=动态,12=专栏,17=转发"),
        order_by: str = Query("time_desc", description="time_desc/time_asc")
):
    client = get_clickhouse_client()

    user_info_query = """
    SELECT 
        user_uid,
        groupArray(DISTINCT user_name) as user_names,
        count() as total_comments,
        min(ctime) as first_comment_time,
        max(ctime) as last_comment_time
    FROM comments
    WHERE user_uid = {user_uid:UInt64}
    GROUP BY user_uid
    """

    user_info_result = client.query(user_info_query, parameters={'user_uid': int(user_uid)})

    if not user_info_result.result_rows:
        raise HTTPException(status_code=404, detail=f"用户 {user_uid} 不存在")

    user_row = user_info_result.result_rows[0]
    user_info = UserInfo(
        user_uid=str(user_row[0]),
        user_names=user_row[1],
        total_comments=user_row[2],
        first_comment_time=user_row[3].isoformat() if user_row[3] else '',
        last_comment_time=user_row[4].isoformat() if user_row[4] else ''
    )

    where_conditions = ["user_uid = {user_uid:UInt64}"]
    params = {'user_uid': int(user_uid)}

    if keyword:
        where_conditions.append("content LIKE {keyword:String}")
        params['keyword'] = f'%{keyword}%'

    if comment_type is not None:
        where_conditions.append("comment_type = {comment_type:UInt8}")
        params['comment_type'] = comment_type

    if content_type is not None:
        where_conditions.append("type = {content_type:UInt8}")
        params['content_type'] = content_type

    where_clause = " AND ".join(where_conditions)
    order_clause = "ORDER BY ctime DESC" if order_by == "time_desc" else "ORDER BY ctime ASC"

    offset = (page - 1) * page_size
    params.update({'limit': page_size, 'offset': offset})

    comments_query = f"""
    SELECT 
        comment_id, video_bvid, type, user_name, content, 
        ctime, parent_id, root_id, comment_type
    FROM comments
    WHERE {where_clause}
    {order_clause}
    LIMIT {{limit:UInt32}} OFFSET {{offset:UInt32}}
    """

    comments_result = client.query(comments_query, parameters=params)

    comments = [
        Comment(
            comment_id=row[0],
            video_bvid=row[1],
            type=row[2],
            user_name=row[3],
            content=row[4],
            ctime=row[5].isoformat() if row[5] else '',
            parent_id=row[6],
            root_id=row[7],
            comment_type=row[8]
        )
        for row in comments_result.result_rows
    ]

    count_query = f"SELECT count() FROM comments WHERE {where_clause}"
    total = client.query(count_query, parameters=params).result_rows[0][0]

    return UserCommentsResponse(
        user_info=user_info,
        comments=comments,
        total=total,
        page=page,
        page_size=page_size
    )


@app.get("/api/stats")
async def get_stats():
    client = get_clickhouse_client()

    total_comments = client.query("SELECT count() FROM comments").result_rows[0][0]
    total_users = client.query("SELECT count(DISTINCT user_uid) FROM comments").result_rows[0][0]
    latest_comment = client.query("SELECT max(ctime) FROM comments").result_rows[0][0]

    kafka_stats = get_kafka_stats()
    consumer_stats = kafka_consumer_thread.get_stats() if kafka_consumer_thread else {}

    return {
        "clickhouse": {
            "total_comments": total_comments,
            "total_users": total_users,
            "latest_comment_time": latest_comment.isoformat() if latest_comment else None
        },
        "kafka": kafka_stats,
        "consumer": {
            "is_running": kafka_consumer_thread.is_alive() if kafka_consumer_thread else False,
            **consumer_stats
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)