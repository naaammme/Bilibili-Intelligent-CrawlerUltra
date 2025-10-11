<template>
  <div>
    <div v-if="!userData" class="menu-bar">
      <a class="h">查询</a>
      <a href="javascript:;">工具</a>
      <a href="javascript:;" class="about">关于</a>
    </div>

    <!-- 搜索页：当没有用户数据时显示 -->
    <div v-if="!userData" class="kp">
      <!-- 公告 -->
      <div class="blur-bg blur-bg-1">
        <h1 style="padding-top:0px">公告</h1>
        <div id="notice-content">
          <h2>有疑问请telegram或邮箱联系<br/>过阵子会更新评论数据先别急<br/>直播弹幕优化了一下 可以多看看</h2>
        </div>
      </div>

      <!-- 查评论 -->
      <div class="blur-bg" id="ys">
        <h1>查评论</h1>
        <h2>
          如果无法正常使用请使用新版chrome/edge/firefox访问本站<br/>
          数据非实时更新 更新时间随缘<br/>
          <a href="https://www.aicu.cc/help?id=14">没有输入框点这里</a>
        </h2>

        <div class="input-container">
          <label for="uidInput" class="input-label">UID</label>
          <input
            v-model="searchUid"
            @keypress.enter="handleSearch"
            class="input-field"
            id="uidInput"
          />
          <button class="clear-btn" @click="searchUid = ''" title="清除uid">
            <svg t="1721823563342" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6652" width="256" height="256">
              <path d="M844.288 514.56c-52.736-27.392-201.216-35.84-201.216-35.84s152.576-4.352 240.896-33.536c0 0 102.656-40.96 68.864-162.048 0 0-20.736-63.488-132.864-75.264 0 0 9.984-83.968-70.656-132.352 0 0-56.832-34.304-141.056 17.92-71.936 52.224-80.64 234.752-81.152 246.272 0.512-11.008 6.144-177.664-33.792-249.088 0 0-42.752-99.072-164.096-48.128 0 0-102.912 33.024-81.664 128 0 0-150.272-31.744-171.008 111.104 0 0-17.92 116.224 109.568 141.568 41.472 10.24 182.016 32.768 182.016 32.768S79.872 429.312 65.792 569.344c0 0-24.32 131.584 125.184 128.256 0 0-16.128 98.816 79.36 131.328 0.256-0.256 127.232 36.608 187.648-124.928 13.312-37.632 24.576-63.488 30.976-128.256 0 0 2.304 256.512-214.272 387.072l72.192 43.008s157.696-154.88 160-409.6c-0.256-13.568-0.256-21.76-0.256-21.76 0.256 7.424 0.256 14.592 0.256 21.76 1.024 50.176 8.704 173.056 52.992 219.392 0 0 63.232 87.04 172.544 41.984 0 0 65.28-23.808 65.792-109.824 0 0 100.864 15.104 122.88-88.832-0.512 0 29.184-91.648-76.8-144.384z m0 0" fill="#44b702" p-id="6653"></path>
            </svg>
          </button>
        </div>

        <div class="button-container">
          <button class="btn" @click="handleSearch">查评论</button>
          <button class="btn" @click="alert('查弹幕功能开发中')">查弹幕</button>
          <button class="btn" @click="alert('查直播弹幕功能开发中')">查直播弹幕</button>
        </div>

        <div class="history-container" v-if="searchHistory.length > 0">
          <h3>最近搜索</h3>
          <div class="history-list">
            <div
              v-for="item in searchHistory"
              :key="item.uid"
              @click="searchUid = item.uid; handleSearch()"
              class="history-item"
            >
              <span class="name">{{ item.name }}</span>
              <span class="uid">{{ item.uid }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 使用文档 -->
      <div class="blur-bg blur-bg-2" style="max-height: 450px; overflow-y: auto;">
        <h1 style="padding-top:0px; margin-bottom: 33.5px;">使用文档</h1>
        <div class="list-container">
          <div class="list-item">
            <div class="headline">无法输入 UID / 无 UID 输入框怎么解决</div>
            <div class="supporting-text">2024/9/1</div>
          </div>
          <div class="list-item">
            <div class="headline">关于数据更新</div>
            <div class="supporting-text">2025/1/29</div>
          </div>
          <div class="list-item">
            <div class="headline">查评论查成分的法律问题</div>
            <div class="supporting-text">2024/9/1</div>
          </div>
          <div class="list-item">
            <div class="headline">如何查询在 B 站视频中发送的弹幕</div>
            <div class="supporting-text">2024/9/1</div>
          </div>
          <div class="list-item">
            <div class="headline">如何查询在 B 站视频中发送的评论</div>
            <div class="supporting-text">2024/9/1</div>
          </div>
          <div class="list-item">
            <div class="headline">如何查询在 B 站视频中发送的弹幕</div>
            <div class="supporting-text">2024/9/1</div>
          </div>
          <div class="list-item">
            <div class="headline">aicu是如何运作的</div>
            <div class="supporting-text">2024/8/8</div>
          </div>
          <div class="list-item">
            <div class="headline">如何将评论数据保存为execl</div>
            <div class="supporting-text">2024/8/8</div>
          </div>
          <div class="list-item">
            <div class="headline">如何通过装扮编号获取用户uid</div>
            <div class="supporting-text">2024/7/23</div>
          </div>
          <div class="list-item">
            <div class="headline">如何获取用户uid</div>
            <div class="supporting-text">2024/5/19</div>
          </div>

        </div>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <p style="margin-top: 16px;">加载中...</p>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-message">
      {{ error }}
      <button @click="userData = null; error = ''" class="btn" style="margin-top: 12px;">
        返回搜索
      </button>
    </div>

    <!-- 用户数据展示 -->
    <UserDisplay
      v-if="userData && !loading"
      :user-data="userData"
      @load-page="loadUserData"
      @back="userData = null"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import UserDisplay from './components/UserDisplay.vue'
import { getSearchHistory, saveSearchHistory } from './utils/storage'

const searchUid = ref('')
const loading = ref(false)
const error = ref('')
const userData = ref(null)
const searchHistory = ref([])

onMounted(() => {
  searchHistory.value = getSearchHistory()
  // 检查URL中是否带有UID参数
  const urlParams = new URLSearchParams(window.location.search);
  const uidFromUrl = urlParams.get('uid');
  if (uidFromUrl) {
    // 如果URL中有UID，直接加载该用户的数据
    searchUid.value = uidFromUrl;
    loadUserData(1, uidFromUrl);
  }
})

// 从B站URL解析UID
const parseUidFromUrl = (input) => {
  const match = input.match(/space\.bilibili\.com\/(\d+)/)
  return match ? match[1] : input
}

const handleSearch = async () => {
  let uid = searchUid.value.trim()

  if (!uid) {
    alert('请输入UID或B站主页链接')
    return
  }

  // 解析URL
  uid = parseUidFromUrl(uid)

  if (!/^\d+$/.test(uid)) {
    alert('UID必须是纯数字')
    return
  }

  // 构建新的URL并用新标签页打开
  const url = new URL(window.location.href);
  url.searchParams.set('uid', uid);
  window.open(url.toString(), '_blank');
}

const loadUserData = async (page = 1, uid = null, filters = null) => {
  const targetUid = uid || parseUidFromUrl(searchUid.value.trim());

  if (!targetUid) {
      error.value = '无效的UID';
      return;
  }

  loading.value = true
  error.value = ''

  // 仅在加载第一页时清空之前的数据
  if (page === 1) {
    userData.value = null
  }

  try {
    const params = {
      page,
      page_size: 20
    }

    // 添加筛选参数
    if (filters) {
      if (filters.keyword) params.keyword = filters.keyword
      if (filters.comment_type) params.comment_type = filters.comment_type
      if (filters.content_type) params.content_type = filters.content_type
      if (filters.order_by) params.order_by = filters.order_by
    }

    const response = await axios.get(`/api/user/${targetUid}`, { params })

    userData.value = {
      ...response.data,
      currentPage: page,
      uid: targetUid
    }

    // 保存搜索历史（去重）
    if (page === 1 && !filters) {
      saveSearchHistory({
        uid: targetUid,
        name: response.data.user_info.user_names[0] || `用户${targetUid}`
      })
      searchHistory.value = getSearchHistory()
    }
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || '查询失败'
  } finally {
    loading.value = false
  }
}
</script>