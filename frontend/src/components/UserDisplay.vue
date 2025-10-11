<template>
  <div class="wrap">
    <!-- 相关链接 -->
    <div class="card">
      <div class="section-title">相关链接</div>
      <div class="pill-grid">
        <div class="pill-row">
          <a class="pill" href="javascript:;">查弹幕</a>
          <a class="pill" href="javascript:;">查直播弹幕</a>
        </div>

        <div class="pill-row">
          <a class="pill" href="javascript:;">AICU主页</a>
          <a class="pill" href="javascript:;">laplace</a>
          <a class="pill" href="javascript:;">bilibili</a>
          <a class="pill" href="javascript:;">danmakus</a>
        </div>

        <div class="pill-row">
          <a class="pill" href="javascript:;">danmakus分析</a>
          <a class="pill" href="javascript:;">DDHub</a>
        </div>
      </div>
    </div>

    <!-- 用户信息 -->
    <div class="card">
      <div class="section-title">用户信息</div>

      <div class="user-panel">
        <div style="text-align:center;">
          <div
            class="avatar"
            :style="{ backgroundImage: `url(https://i0.hdslb.com/bfs/face/57b605d57dc1df1ac730a81280b560d47a3c9d94.jpg@128w)` }"
          ></div>
          <div style="font-size:14px;color:#d6d6d6;margin-top:8px;">
            {{ userData.user_info.user_names[0] }}
          </div>
        </div>

        <div class="user-meta">
          <div class="user-stats">
            <div><b>UID：</b>{{ userData.user_info.user_uid }}</div>
            <div><b>评论总数：</b>{{ userData.user_info.total_comments.toLocaleString() }}</div>
            <div><b>首次评论：</b>{{ formatTime(userData.user_info.first_comment_time) }}</div>
            <div><b>最后评论：</b>{{ formatTime(userData.user_info.last_comment_time) }}</div>
          </div>

          <div style="height:8px;"></div>

          <div style="color:#dcdcdc;font-size:14px;line-height:1.5;">
            历史用户名：{{ userData.user_info.user_names.join(', ') }}
          </div>

          <div style="margin-top:18px;">
            <!-- 统一使用 .btn 样式 -->
            <a class="btn" href="javascript:;" @click="$emit('back')">查粉丝牌/装扮</a>
          </div>
        </div>
      </div>
    </div>

    <!-- 评论统计 + 搜索 -->
    <div class="card">
      <div class="count-title">评论数 {{ userData.total.toLocaleString() }}</div>

      <div class="controls">
        <!-- 文本匹配输入框 -->
        <div class="input-container">
            <input
            v-model="filters.keyword"
            id="keywordInput"
            class="input-field"
            placeholder="文本匹配"
            />
        </div>

        <!-- 其他筛选 -->
        <div class="input-container">
            <select v-model="filters.commentType" class="input-field">
            <option value="">所有评论</option>
            <option value="1">一级评论</option>
            <option value="2">二级评论</option>
            </select>
        </div>

        <div class="input-container">
            <select v-model="filters.contentType" class="input-field">
            <option value="">所有类型</option>
            <option value="1">视频</option>
            <option value="11">动态</option>
            <option value="12">专栏</option>
            <option value="17">转发</option>
            </select>
        </div>

        <div class="input-container button-container">
            <button @click="applyFilters" class="btn">应用筛选</button>
        </div>
      </div>
    </div>

    <!-- 评论列表 -->
    <div id="comments">
      <div v-if="userData.comments.length === 0" class="card" style="text-align: center; color: var(--muted);">
        暂无评论
      </div>

      <div v-for="comment in userData.comments" :key="comment.comment_id" class="comment">
        <div class="time">
          {{ formatTime(comment.ctime) }} ·
          <span :style="{ color: getTypeColor(comment.type) }">{{ getTypeName(comment.type) }}</span> ·
          {{ comment.comment_type === 2 ? '二级评论' : '一级评论' }}
        </div>
        <div class="msg">{{ comment.content }}</div>
        <div class="meta-right">当前查询uid:{{ userData.uid }} 爱来自bicu.cc</div>
        <div class="actions">
          <a :href="getJumpUrl(comment, 0)" target="_blank" class="btn">方式0</a>
          <a :href="getJumpUrl(comment, 2)" target="_blank" class="btn">方式2</a>
          <a :href="getJumpUrl(comment, 3)" class="btn mobile-only-btn">方式3</a>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="totalPages >= 1" class="pagination-container">
      <div class="pagination">
        <button
          @click="changePage(currentPage - 1)"
          class="page-btn"
          :class="{ disabled: currentPage === 1 }"
        >
          «
        </button>

        <button
          v-for="page in displayPages"
          :key="page"
          @click="changePage(page)"
          class="page-btn"
          :class="{ active: page === currentPage, 'is-dots': page === '...' }"
          :disabled="page === '...'"
        >
          {{ page }}
        </button>

        <button
          @click="changePage(currentPage + 1)"
          class="page-btn"
          :class="{ disabled: currentPage === totalPages }"
        >
          »
        </button>
      </div>
    </div>

    <footer>你所热爱的，就是你的生活。<br>© 1868 bicu
    </footer>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { formatTime } from '../utils/index'

const props = defineProps({
  userData: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['load-page', 'back'])

const filters = ref({
  keyword: '',
  commentType: '',
  contentType: '',
  orderBy: 'time_desc'
})

const currentPage = computed(() => props.userData.currentPage || 1)
const totalPages = computed(() => Math.ceil(props.userData.total / props.userData.page_size))

// 分页按钮显示逻辑
const displayPages = computed(() => {
  const pages = []
  const maxPagesToShow = 5

  if (totalPages.value <= maxPagesToShow + 2) {
    for (let i = 1; i <= totalPages.value; i++) {
      pages.push(i)
    }
  } else {
    let start = Math.max(2, currentPage.value - 2)
    let end = Math.min(totalPages.value - 1, currentPage.value + 2)

    if (currentPage.value < maxPagesToShow) {
        start = 2;
        end = maxPagesToShow;
    }

    if (currentPage.value > totalPages.value - maxPagesToShow + 1) {
        start = totalPages.value - maxPagesToShow + 1;
        end = totalPages.value - 1;
    }

    pages.push(1)
    if (start > 2) {
      pages.push('...')
    }

    for (let i = start; i <= end; i++) {
      pages.push(i)
    }

    if (end < totalPages.value - 1) {
      pages.push('...')
    }
    pages.push(totalPages.value)
  }

  return pages
})

const contentTypeMap = {
  1: { name: '视频', color: '#6b7280' },
  11: { name: '动态', color: '#6b7280' },
  12: { name: '专栏', color: '#6b7280' },
  17: { name: '转发', color: '#6b7280' }
}

const getTypeName = (type) => {
  return contentTypeMap[type]?.name || '未知'
}

const getTypeColor = (type) => {
  return contentTypeMap[type]?.color || '#6b7280'
}

const getJumpUrl = (comment, mode) => {
  const bvid = comment.video_bvid
  const commentId = comment.comment_id
  const rootId = comment.comment_type === 1 ? comment.comment_id : comment.root_id
  const anchorId = comment.comment_type === 1 ? comment.comment_id : comment.root_id

  switch (mode) {
    case 0:
      return `https://www.bilibili.com/video/${bvid}#reply${commentId}`
    case 2:
      return `https://www.bilibili.com/h5/comment/sub?oid=${bvid}&pageType=1&root=${rootId}`
    case 3:
      return `bilibili://comment/detail/1/${bvid}/${commentId}/?subType=0&anchor=${anchorId}&showEnter=1&extraIntentId=0&scene=1&enterName=查看动态 爱来自bicu.cc&title=你所热爱的就是你的生活`
    default:
      return '#'
  }
}

const changePage = (page) => {
  if (typeof page !== 'number' || page < 1 || page > totalPages.value || page === currentPage.value) return

  const filterParams = {
    keyword: filters.value.keyword,
    comment_type: filters.value.commentType,
    content_type: filters.value.contentType,
    order_by: filters.value.orderBy
  }

  emit('load-page', page, props.userData.uid, filterParams)
  window.scrollTo({top: 0, behavior: 'smooth'})
}

const applyFilters = () => {
  const filterParams = {
    keyword: filters.value.keyword,
    comment_type: filters.value.commentType,
    content_type: filters.value.contentType,
    order_by: filters.value.orderBy
  }

  emit('load-page', 1, props.userData.uid, filterParams)
}
</script>

