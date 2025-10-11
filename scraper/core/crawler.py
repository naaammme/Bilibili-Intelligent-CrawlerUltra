#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import random
import base64
import struct
import gzip
import httpx
import time
import hashlib
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from collections import deque
import logging
import json

try:
    from bilibili.main.community.reply.v1 import reply_pb2
    from bilibili.metadata.device import device_pb2
    from bilibili.metadata.fawkes import fawkes_pb2
    from bilibili.metadata import metadata_pb2
    from bilibili.metadata.network import network_pb2
    from bilibili.metadata.locale import locale_pb2
except ImportError as e:
    raise ImportError(f"导入失败,请检查是否编译proto文件 错误: {e}")

logger = logging.getLogger(__name__)


class DeviceIdentity:

    @staticmethod
    def generate_buvid(device_id: str, prefix: str = "XU") -> str:
        """
        生成 BUVID
        Args:
            device_id: 设备特征码 (如 AndroidID, DrmId 等)
            prefix: BUVID 前缀 (XX=AndroidID, XU=DrmId, XY=MAC, XW=GUID)
        Returns:
            37位大写 BUVID
        """
        id_md5 = hashlib.md5(device_id.encode()).hexdigest().upper()

        try:
            id_e = id_md5[2] + id_md5[12] + id_md5[22]
        except IndexError:
            id_e = "000"

        buvid = f"{prefix}{id_e}{id_md5}"

        return buvid.upper()

    @staticmethod
    def generate_fp(buvid: str, device_model: str, radio_version: str = "") -> str:
        """
        生成设备指纹 fp
        Args:
            buvid: BUVID (通常使用XU前缀)
            device_model: 设备型号 (如 NOH-AN01)
            radio_version: 无线电固件版本
        Returns:
            64位设备指纹
        """
        fp_base = f"{buvid}{device_model}{radio_version}"
        fp_md5 = hashlib.md5(fp_base.encode()).hexdigest()

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        fp_with_time = fp_md5 + timestamp

        random_hex = ''.join(random.choices('0123456789abcdef', k=16))
        fp_raw = fp_with_time + random_hex

        veri_code = 0
        fp_pairs = [fp_raw[i:i + 2] for i in range(0, min(len(fp_raw), 62), 2)]

        for pair in fp_pairs:
            try:
                veri_code += int(pair, 16)
            except ValueError:
                pass

        veri_code_hex = format(veri_code % 256, '02x')

        return fp_raw + veri_code_hex

    @staticmethod
    def generate_trace_id() -> str:
        random_id = ''.join(random.choices('0123456789abcdefghijklmnopqrstuvwxyz', k=32))

        random_trace_id = random_id[:24]

        ts = int(time.time())
        b_arr = [0, 0, 0]

        for i in range(2, -1, -1):
            ts >>= 8
            if (ts // 128) % 2 == 0:
                b_arr[i] = ts % 256
            else:
                b_arr[i] = ts % 256 - 256

        for val in b_arr:
            random_trace_id += format(val & 0xFF, '02x')

        random_trace_id += random_id[30:32]

        return f"{random_trace_id}:{random_trace_id[16:32]}:0:0"


class ProtobufObjectPool:

    def __init__(self, max_size: int = 20):
        self.max_size = max_size
        self.main_req_pool = deque(maxlen=max_size)
        self.detail_req_pool = deque(maxlen=max_size)
        self.cursor_pool = deque(maxlen=max_size)

    def get_main_req(self) -> reply_pb2.MainListReq:
        if self.main_req_pool:
            req = self.main_req_pool.pop()
            req.Clear()
            return req
        return reply_pb2.MainListReq()

    def return_main_req(self, req: reply_pb2.MainListReq):
        if len(self.main_req_pool) < self.max_size:
            self.main_req_pool.append(req)

    def get_detail_req(self) -> reply_pb2.DetailListReq:
        if self.detail_req_pool:
            req = self.detail_req_pool.pop()
            req.Clear()
            return req
        return reply_pb2.DetailListReq()

    def return_detail_req(self, req: reply_pb2.DetailListReq):
        if len(self.detail_req_pool) < self.max_size:
            self.detail_req_pool.append(req)

    def get_cursor(self) -> reply_pb2.CursorReq:
        if self.cursor_pool:
            cursor = self.cursor_pool.pop()
            cursor.Clear()
            return cursor
        return reply_pb2.CursorReq()

    def return_cursor(self, cursor: reply_pb2.CursorReq):
        if len(self.cursor_pool) < self.max_size:
            self.cursor_pool.append(cursor)


class DynamicIDConverter:

    def __init__(self, client: httpx.Client):
        self.client = client

    def get_dynamic_detail(self, dynamic_id: int) -> Dict:
        url = "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/get_dynamic_detail"
        params = {'dynamic_id': dynamic_id}

        response = self.client.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        if data.get('code') != 0:
            raise ValueError(f"API返回错误: {data.get('message')}")

        return data.get('data', {})

    def convert_dynamic_id_to_oid(self, dynamic_id: int) -> Tuple[int, int]:
        dynamic_detail = self.get_dynamic_detail(dynamic_id)

        card_info = dynamic_detail.get('card', {})
        if isinstance(card_info, str):
            card_info = json.loads(card_info)

        desc_info = card_info.get('desc', {})
        oid = desc_info.get('rid', 0) or card_info.get('rid', 0) or dynamic_id
        dynamic_type = desc_info.get('type', 0)

        type_map = {
            1: 17, 2: 11, 4: 17, 8: 1, 16: 11, 64: 12,
            256: 11, 512: 1, 2048: 17, 4200: 17, 4308: 17
        }

        if dynamic_type in [1, 2048, 4, 4200]:
            oid = dynamic_id
            comment_type = 17
        else:
            comment_type = type_map.get(dynamic_type, 17)

        logger.info(f"动态ID转换: {dynamic_id} -> oid={oid}, type={comment_type}")
        return oid, comment_type


class BilibiliCommentCrawler:

    XOR_CODE = 23442827791579
    MAX_CODE = 2251799813685247
    CHARTS = "FcwAPNKTMug3GV5Lj7EJnHpWsx4tb8haYeviqBz6rkCy12mUSDQX9RdoZf"
    PAUL_NUM = 58

    def __init__(self):

        self.client = httpx.Client(
            http2=True,
            timeout=30.0,
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=50,
                keepalive_expiry=300.0
            ),
            follow_redirects=True
        )

        # 设备信息 (模拟小米13)
        self.device_brand = "XIAOMI"
        self.device_model = "2211133C"  # 小米13
        self.device_osver = "13"
        self.app_build = 7420400
        self.app_version = "7.42.0"
        self.mobi_app = "android"
        self.channel = "xiaomi"

        self.user_agent = (
            f"Mozilla/5.0 (Linux; Android {self.device_osver}; {self.device_model} "
            f"Build/TKQ1.220829.002) AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/117.0.5938.132 Mobile Safari/537.36"
        )

        device_id = "1234567890abcdef"  # 模拟DrmId
        self.buvid = DeviceIdentity.generate_buvid(device_id, prefix="XU")
        self.fp = DeviceIdentity.generate_fp(self.buvid, self.device_model, "")

        self.fts = int(time.time()) - (30 * 24 * 3600)

        self._cached_metadata_bin = self.build_metadata()
        self._cached_device_bin = self.build_device()
        self._cached_network_bin = self.build_network()
        self._cached_locale_bin = self.build_locale()

        self.pb_pool = ProtobufObjectPool(max_size=20)

        self.client.headers.update({
            'User-Agent': self.user_agent,
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept': 'application/grpc',
            'Referer': 'https://www.bilibili.com/',
            'bili-http-engine': 'cronet',
        })

        self.dynamic_converter = DynamicIDConverter(self.client)

        logger.info(f"✅ 设备初始化完成 (HTTP/2启用)")
        logger.info(f"   BUVID: {self.buvid}")
        logger.info(f"   FP: {self.fp[:16]}...")
        logger.info(f"   设备: {self.device_brand} {self.device_model}")
        logger.info(f"   系统: Android {self.device_osver}")
        logger.info(f"   APP: {self.app_version} ({self.app_build})")

    def __del__(self):
        if hasattr(self, 'client'):
            self.client.close()

    def get_aurora(self, uid: int = 0) -> str:

        if uid == 0:
            return ""

        mid_bytes = str(uid).encode('utf-8')
        key = b"ad1va46a7lza"
        result = bytearray(b ^ key[i % len(key)] for i, b in enumerate(mid_bytes))
        return base64.b64encode(result).decode('utf-8').rstrip('=')

    def build_metadata(self) -> str:
        metadata = metadata_pb2.Metadata()
        metadata.mobi_app = self.mobi_app
        metadata.build = self.app_build
        metadata.channel = self.channel
        metadata.platform = "android"
        metadata.buvid = ""
        return base64.b64encode(metadata.SerializeToString()).decode()

    def build_device(self) -> str:
        device = device_pb2.Device()
        device.app_id = 1
        device.build = self.app_build
        device.buvid = self.buvid
        device.platform = "android"
        device.mobi_app = self.mobi_app
        device.device = ""
        device.channel = self.channel
        device.brand = self.device_brand
        device.model = self.device_model
        device.osver = self.device_osver
        device.fp_local = self.fp
        device.fp_remote = self.fp
        device.version_name = self.app_version
        device.fp = self.fp
        device.fts = self.fts
        return base64.b64encode(device.SerializeToString()).decode()

    def build_network(self) -> str:
        network = network_pb2.Network()
        network.type = network_pb2.WIFI  # 模拟WIFI环境
        network.tf = network_pb2.TF_UNKNOWN  # 正常计费
        network.oid = "46000"  # 中国联通
        return base64.b64encode(network.SerializeToString()).decode()

    def build_locale(self) -> str:
        locale = locale_pb2.Locale()

        c_locale = locale_pb2.LocaleIds()
        c_locale.language = "zh"
        c_locale.region = "CN"
        locale.c_locale.CopyFrom(c_locale)

        s_locale = locale_pb2.LocaleIds()
        s_locale.language = "zh"
        s_locale.region = "CN"
        locale.s_locale.CopyFrom(s_locale)

        locale.sim_code = ""
        locale.timezone = "Asia/Shanghai"

        return base64.b64encode(locale.SerializeToString()).decode()

    def build_fawkes(self) -> str:
        fawkes = fawkes_pb2.FawkesReq()
        fawkes.appkey = "android"
        fawkes.env = "prod"
        fawkes.session_id = ''.join(random.choices('0123456789abcdef', k=8))
        return base64.b64encode(fawkes.SerializeToString()).decode()

    def get_request_headers(self) -> Dict[str, str]:
        return {
            'accept-encoding': 'identity',
            'grpc-encoding': 'gzip',
            'grpc-accept-encoding': 'gzip',
            'env': 'prod',
            'app-key': 'android',
            'user-agent': self.user_agent,
            'x-bili-aurora-eid': self.get_aurora(0),
            'x-bili-mid': '0',
            'x-bili-aurora-zone': '',
            'x-bili-gaia-vtoken': '',
            'x-bili-ticket': '',
            'x-bili-trace-id': DeviceIdentity.generate_trace_id(),
            'x-bili-metadata-bin': self._cached_metadata_bin,
            'x-bili-device-bin': self._cached_device_bin,
            'x-bili-network-bin': self._cached_network_bin,
            'x-bili-restriction-bin': '',
            'x-bili-locale-bin': self._cached_locale_bin,
            'x-bili-exps-bin': '',
            'buvid': self.buvid,
            'x-bili-fawkes-req-bin': self.build_fawkes(),
            'content-type': 'application/grpc',
            'bili-http-engine': 'cronet',
        }

    def build_grpc_frame(self, data: bytes) -> bytes:
        frame = bytearray(5 + len(data))
        frame[0] = 0x00
        struct.pack_into('>I', frame, 1, len(data))
        frame[5:] = data
        return bytes(frame)

    def parse_grpc_response(self, response_data: bytes) -> bytes:
        if len(response_data) < 5:
            raise ValueError(f"响应数据太短，长度: {len(response_data)}")

        payload = response_data[5:]
        if response_data[0] == 0x01:
            payload = gzip.decompress(payload)
        return payload

    def format_timestamp(self, timestamp: int) -> str:
        try:
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        except:
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def bvid_to_avid(self, bvid: str) -> int:
        def swap(s: str, x: int, y: int) -> str:
            chars = list(s)
            chars[x], chars[y] = chars[y], chars[x]
            return ''.join(chars)

        s = swap(swap(bvid, 3, 9), 4, 7)
        bv1 = s[3:]
        temp = 0

        for c in bv1:
            idx = self.CHARTS.find(c)
            if idx == -1:
                raise ValueError(f"无效的BV号字符: {c}")
            temp = temp * self.PAUL_NUM + idx

        return (temp & self.MAX_CODE) ^ self.XOR_CODE

    def is_dynamic_id(self, input_str: str) -> bool:
        try:
            num = int(input_str)
            return len(input_str) > 15 and num > 0
        except ValueError:
            return False

    def parse_input(self, input_str: str) -> Tuple[int, int, str]:
        input_str = input_str.strip()

        if self.is_dynamic_id(input_str):
            dynamic_id = int(input_str)
            logger.info(f"识别为动态ID: {dynamic_id}")
            oid, comment_type = self.dynamic_converter.convert_dynamic_id_to_oid(dynamic_id)
            return oid, comment_type, input_str

        if input_str.startswith('BV'):
            avid = self.bvid_to_avid(input_str)
            return avid, 1, input_str

        if input_str.startswith('av'):
            avid = int(input_str[2:])
            return avid, 1, input_str

        if input_str.isdigit():
            numeric_id = int(input_str)
            return numeric_id, 11, input_str

        raise ValueError("输入格式错误，支持: BV号、AV号、动态ID(数字)")

    def extract_reply_info(self, reply_info, bvid: str, comment_type: int) -> Dict:
        parent_id = str(reply_info.parent) if reply_info.parent else "0"
        root_id = str(reply_info.root) if reply_info.root else str(reply_info.id)

        if reply_info.root == 0:
            root_id = str(reply_info.id)
            parent_id = "0"

        return {
            'comment_id': str(reply_info.id),
            'video_bvid': bvid,
            'type': comment_type,
            'user_uid': str(reply_info.mid),
            'user_name': reply_info.member.name if reply_info.HasField('member') else '',
            'content': reply_info.content.message if reply_info.HasField('content') else '',
            'ctime': self.format_timestamp(reply_info.ctime),
            'parent_id': parent_id,
            'root_id': root_id,
            'comment_type': 1 if reply_info.root == 0 else 2,
        }

    def get_detail_replies_rpc(self, oid: int, root_id: int, comment_type: int,
                               bvid: str) -> List[Dict]:
        all_replies = []
        current_token = ""

        while True:
            request = self.pb_pool.get_detail_req()
            cursor = self.pb_pool.get_cursor()

            request.oid = oid
            request.type = comment_type
            request.root = root_id
            request.rpid = 0

            cursor.mode = reply_pb2.MAIN_LIST_HOT
            if current_token:
                try:
                    cursor.next = int(current_token)
                except:
                    cursor.next = 0

            request.cursor.CopyFrom(cursor)
            request.scene = reply_pb2.REPLY

            payload = request.SerializeToString()
            grpc_frame = self.build_grpc_frame(payload)

            self.pb_pool.return_cursor(cursor)

            response = self.client.post(
                'https://app.bilibili.com/bilibili.main.community.reply.v1.Reply/DetailList',
                content=grpc_frame,
                headers=self.get_request_headers(),
                timeout=30
            )

            if response.status_code != 200:
                logger.warning(f"DetailList请求失败: {response.status_code}")
                self.pb_pool.return_detail_req(request)
                break

            response_payload = self.parse_grpc_response(response.content)
            detail_reply = reply_pb2.DetailListReply()
            detail_reply.ParseFromString(response_payload)

            if detail_reply.HasField('root') and detail_reply.root.replies:
                for sub_reply in detail_reply.root.replies:
                    reply_data = self.extract_reply_info(sub_reply, bvid, comment_type)
                    all_replies.append(reply_data)

            self.pb_pool.return_detail_req(request)

            if detail_reply.HasField('cursor') and detail_reply.cursor.next > 0:
                current_token = str(detail_reply.cursor.next)
                time.sleep(random.uniform(0.3, 1.4))
            else:
                break

        return all_replies

    def get_main_comments_only(self, oid: int, page_token: str, comment_type: int,
                               sort_mode: str, bvid: str) -> Tuple[List[Dict], str]:
        request = self.pb_pool.get_main_req()
        cursor = self.pb_pool.get_cursor()

        request.oid = oid
        request.type = comment_type
        request.extra = "{}"
        request.ad_extra = ""
        request.filter_tag_name = "全部"

        if sort_mode == "MAIN_LIST_TIME":
            cursor.mode = reply_pb2.MAIN_LIST_TIME
        else:
            cursor.mode = reply_pb2.MAIN_LIST_HOT

        if page_token:
            try:
                cursor.next = int(page_token)
            except:
                cursor.next = 0

        request.cursor.CopyFrom(cursor)
        payload = request.SerializeToString()
        grpc_frame = self.build_grpc_frame(payload)

        self.pb_pool.return_cursor(cursor)

        response = self.client.post(
            'https://app.bilibili.com/bilibili.main.community.reply.v1.Reply/MainList',
            content=grpc_frame,
            headers=self.get_request_headers(),
            timeout=30
        )

        if response.status_code != 200:
            self.pb_pool.return_main_req(request)
            raise Exception(f"请求失败: {response.status_code}")

        response_payload = self.parse_grpc_response(response.content)
        reply = reply_pb2.MainListReply()
        reply.ParseFromString(response_payload)

        main_comments_info = []

        # 只在第一页处理置顶评论
        if not page_token:
            # UP主置顶
            if reply.HasField('up_top') and reply.up_top.id > 0:
                main_comments_info.append({
                    'reply_info': reply.up_top,
                    'reply_count': reply.up_top.count,
                    'is_top': True,
                    'top_type': 'up'
                })
            # 管理员置顶
            if reply.HasField('admin_top') and reply.admin_top.id > 0:
                main_comments_info.append({
                    'reply_info': reply.admin_top,
                    'reply_count': reply.admin_top.count,
                    'is_top': True,
                    'top_type': 'admin'
                })
            # 投票置顶
            if reply.HasField('vote_top') and reply.vote_top.id > 0:
                main_comments_info.append({
                    'reply_info': reply.vote_top,
                    'reply_count': reply.vote_top.count,
                    'is_top': True,
                    'top_type': 'vote'
                })

        # 处理普通评论
        for reply_info in reply.replies:
            main_comments_info.append({
                'reply_info': reply_info,
                'reply_count': reply_info.count,
                'is_top': False,
                'top_type': None
            })

        next_token = ""
        if reply.HasField('cursor') and reply.cursor.next > 0:
            next_token = str(reply.cursor.next)

        self.pb_pool.return_main_req(request)
        return main_comments_info, next_token

    def get_comments_rpc(self, oid: int, page_token: str = "", comment_type: int = 1,
                         sort_mode: str = "MAIN_LIST_HOT", bvid: str = "") -> Tuple[List[Dict], str]:

        #先获取主评论列表
        main_comments_info, next_token = self.get_main_comments_only(
            oid, page_token, comment_type, sort_mode, bvid
        )

        all_comments = []

        #然后批量处理子评论
        for idx, comment_info in enumerate(main_comments_info):
            reply_info = comment_info['reply_info']
            reply_count = comment_info['reply_count']

            #提取主评论
            main_comment = self.extract_reply_info(reply_info, bvid, comment_type)
            all_comments.append(main_comment)

            #如果有子评论，批量获取
            if reply_count > 0:
                try:
                    detail_replies = self.get_detail_replies_rpc(
                        oid, reply_info.id, comment_type, bvid
                    )
                    all_comments.extend(detail_replies)
                except Exception as e:
                    logger.warning(f"获取详细回复失败，使用部分回复: {e}")
                    for sub_reply in reply_info.replies:
                        sub_comment = self.extract_reply_info(sub_reply, bvid, comment_type)
                        all_comments.append(sub_comment)

                # 每处理10条主评论后稍作延迟
                if (idx + 1) % 10 == 0:
                    time.sleep(random.uniform(0.1, 0.5))

        return all_comments, next_token