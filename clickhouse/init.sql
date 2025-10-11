-- Bilibili评论数据库初始化脚本,表可以根据需要自行调整
CREATE DATABASE IF NOT EXISTS bilibili;

USE bilibili;
SET allow_experimental_full_text_index = 1;
-- 评论主表
CREATE TABLE IF NOT EXISTS comments (
    comment_id UInt64,                          -- 评论ID
    video_bvid String CODEC(ZSTD(3)),           -- 视频BV号/动态ID
    type UInt8,                                 -- 类型(1=视频,11=动态,12=专栏,17=转发动态)
    user_uid UInt64,                            -- 用户UID
    user_name String CODEC(ZSTD(3)),            -- 用户名
    content String CODEC(ZSTD(3)),              -- 评论内容
    ctime DateTime,                              -- 评论时间
    parent_id UInt64,                            -- 父评论ID
    root_id UInt64,                              -- 根评论ID
    comment_type UInt8,                         -- 评论层级(1=主评论,2=回复)
    -- 二级索引方便查询用户的评论历史
   INDEX idx_content content TYPE text(tokenizer = 'ngram', ngram_size = 3)
)
ENGINE = ReplacingMergeTree()
ORDER BY (user_uid, ctime, comment_id)
SETTINGS
    index_granularity = 8192,
    compress_marks = 1,
    compress_primary_key = 1;

-- 用户名称历史物化视图
CREATE MATERIALIZED VIEW IF NOT EXISTS user_names
ENGINE = ReplacingMergeTree()
ORDER BY (user_uid, user_name)
AS
SELECT DISTINCT
    user_uid,
    user_name
FROM comments;