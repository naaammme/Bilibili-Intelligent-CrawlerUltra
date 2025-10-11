/**
 * localStorage 工具函数
 */

const SEARCH_HISTORY_KEY = 'bilibili_search_history'
const MAX_HISTORY_SIZE = 10

/**
 * 获取搜索历史
 * @returns {Array<Object>} 搜索历史数组
 */
export function getSearchHistory() {
  try {
    const history = localStorage.getItem(SEARCH_HISTORY_KEY)
    return history ? JSON.parse(history) : []
  } catch (error) {
    console.error('获取搜索历史失败:', error)
    return []
  }
}

/**
 * 保存搜索记录（去重，相同uid的记录会被覆盖而不是增加）
 * @param {Object} item - 搜索项 {uid: string, name: string}
 */
export function saveSearchHistory(item) {
  try {
    let history = getSearchHistory()

    // 移除已存在的相同uid记录（去重）
    history = history.filter(h => h.uid !== item.uid)

    // 添加到开头
    history.unshift(item)

    // 限制历史记录数量
    if (history.length > MAX_HISTORY_SIZE) {
      history = history.slice(0, MAX_HISTORY_SIZE)
    }

    localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(history))
  } catch (error) {
    console.error('保存搜索历史失败:', error)
  }
}

/**
 * 清除搜索历史
 */
export function clearSearchHistory() {
  try {
    localStorage.removeItem(SEARCH_HISTORY_KEY)
  } catch (error) {
    console.error('清除搜索历史失败:', error)
  }
}