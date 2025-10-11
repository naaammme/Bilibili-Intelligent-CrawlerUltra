#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import threading
import logging
from typing import Callable, List
from datetime import datetime
from dataclasses import dataclass
from confluent_kafka import Consumer, KafkaError
import json

logger = logging.getLogger(__name__)


@dataclass
class ConsumerStats:
    total_consumed: int = 0
    total_inserted: int = 0
    total_failed: int = 0
    last_insert_time: str = ""
    last_error: str = ""

    def to_dict(self) -> dict:
        return {
            "total_consumed": self.total_consumed,
            "total_inserted": self.total_inserted,
            "total_failed": self.total_failed,
            "last_insert_time": self.last_insert_time,
            "last_error": self.last_error
        }


class KafkaConsumerThread(threading.Thread):

    def __init__(
            self,
            bootstrap_servers: str,
            topic: str,
            group_id: str,
            batch_callback: Callable[[List[dict]], None],
            batch_size: int = 50000,
            poll_timeout: float = 1.0
    ):
        super().__init__(daemon=True)
        self.topic = topic
        self.batch_callback = batch_callback
        self.batch_size = batch_size
        self.poll_timeout = poll_timeout
        self.running = True

        self.config = {
            'bootstrap.servers': bootstrap_servers,
            'group.id': group_id,
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False,
            'max.poll.interval.ms': 300000,
            'session.timeout.ms': 45000,
            'fetch.min.bytes': 1,
            'fetch.wait.max.ms': 500
        }

        self.consumer = None
        self.batch = []
        self.stats = ConsumerStats()
        self._lock = threading.Lock()

    def get_stats(self) -> dict:
        with self._lock:
            return self.stats.to_dict()

    def _update_stats(self, **kwargs):
        """线程安全地更新统计信息"""
        with self._lock:
            for key, value in kwargs.items():
                setattr(self.stats, key, value)

    def _create_consumer(self) -> Consumer:
        consumer = Consumer(self.config)
        consumer.subscribe([self.topic])
        logger.info(f"Kafka连接成功: {self.config['bootstrap.servers']}")
        logger.info(f"订阅主题: {self.topic}, 批量大小: {self.batch_size}")
        return consumer

    def _process_batch(self):
        if not self.batch:
            return

        batch_size = len(self.batch)
        logger.info(f"开始处理批次: {batch_size} 条")

        self.batch_callback(self.batch)

        new_total = self.stats.total_inserted + batch_size
        self._update_stats(
            total_inserted=new_total,
            last_insert_time=datetime.now().isoformat()
        )

        logger.info(f"批次处理成功，累计插入: {new_total}")

    def _commit_offset(self):
        if self.consumer:
            self.consumer.commit(asynchronous=False)
            logger.debug("Offset已提交")

    def run(self):
        """主消费循环"""
        logger.info("Kafka消费者启动")

        try:
            self.consumer = self._create_consumer()
        except Exception as e:
            logger.error(f"无法创建消费者: {e}")
            return

        while self.running:
            try:
                msg = self.consumer.poll(timeout=self.poll_timeout)

                if msg is None:
                    # 没有新消息,继续等待,不插入未满的batch
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.debug(f"分区末尾: {msg.topic()} [{msg.partition()}]")
                    else:
                        error_msg = f"Kafka错误: {msg.error()}"
                        logger.error(error_msg)
                        self._update_stats(last_error=error_msg)
                    continue

                value = json.loads(msg.value().decode('utf-8'))
                self.batch.append(value)
                self._update_stats(total_consumed=self.stats.total_consumed + 1)

                if len(self.batch) >= self.batch_size:
                    self._process_batch()
                    self._commit_offset()
                    self.batch = []

            except json.JSONDecodeError as e:
                logger.warning(f"JSON解析失败: {e}")
                continue

            except Exception as e:
                error_msg = f"处理消息异常: {e}"
                logger.error(error_msg, exc_info=True)
                self._update_stats(
                    total_failed=self.stats.total_failed + len(self.batch),
                    last_error=error_msg
                )
                self.batch = []

        self._cleanup()

    def _cleanup(self):
        if self.batch:
            logger.info(f"处理剩余 {len(self.batch)} 条消息")
            try:
                self._process_batch()
                self._commit_offset()
            except Exception as e:
                logger.error(f"清理失败: {e}")

        if self.consumer:
            self.consumer.close()
            logger.info("Kafka消费者已关闭")

    def stop(self):
        logger.info("停止Kafka消费者")
        self.running = False